import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import base64
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Parque Aliança Pro", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO PROFISSIONAL ---
st.markdown("""
    <style>
    .main { background-color: #f1f5f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .sidebar-info { font-size: 0.85rem; color: #64748b; margin-top: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def gerar_pdf_registro_s21(row, mes_sel):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle('Title', fontSize=16, alignment=1, spaceAfter=20, fontName='Helvetica-Bold')
    elements.append(Paragraph("REGISTRO DE PUBLICADOR DE CONGREGAÇÃO", title_style))
    
    # Cabeçalho
    data_cabecalho = [
        [Paragraph(f"<b>Nome:</b> {row['nome_oficial']}", styles['Normal']), ""],
        [f"Mês: {mes_sel}", "Ano de serviço: 2026"]
    ]
    t_cabecalho = Table(data_cabecalho, colWidths=[350, 150])
    elements.append(t_cabecalho)
    elements.append(Spacer(1, 15))
    
    # Tabela de Dados (Layout S-21)
    header = ["Participou no\nministério", "Estudos\nbíblicos", "Pioneiro\nauxiliar", "Horas", "Observações"]
    check_min = "X" if row['horas'] > 0 else ""
    check_pion = "X" if row['cat_oficial'] == "PIONEIRO AUXILIAR" else ""
    corpo = [[f"[{check_min}]", str(int(row['estudos_biblicos'])), f"[{check_pion}]", str(int(row['horas'])), row.get('observacoes', '')]]
    
    t_dados = Table([header] + corpo, colWidths=[100, 80, 80, 70, 160])
    t_dados.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)
    ]))
    elements.append(t_dados)
    doc.build(elements)
    return buffer.getvalue()

# --- FUNÇÕES DE BANCO (CONECTIVIDADE) ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro Crítico de Conexão: {e}")
            return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    if not db: return {}
    docs = db.collection("membros_v2").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def validar_e_gravar_novo_membro(relatorio_id, nome_correto, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome_correto).set({"categoria": categoria}, merge=True)
        db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_correto})
        st.toast(f"✅ {nome_correto} validado!")

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        if entrada_norm == oficial_norm: return nome_oficial
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.82 else None

# --- MAIN ---
def main():
    st.title("🚀 Gestão Parque Aliança Pro")
    
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    
    # Processamento Robusto de Dados
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        
        # Correção do KeyError com verificação segura (get)
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial and nome_oficial in membros_db:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    # Sidebar: Controle de Mês
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["MARÇO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    # ABAS PRINCIPAIS
    tab_rel, tab_triage, tab_inat, tab_cfg = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "💤 INATIVOS", "⚙️ CONFIGURAÇÃO"])

    with tab_rel:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        
        # Totais Mágicos
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Relatórios", len(df_ok))
        c2.metric("Horas Totais", f"{int(df_ok['horas'].sum() if not df_ok.empty else 0)}h")
        c3.metric("Estudos Bíblicos", int(df_ok['estudos_biblicos'].sum() if not df_ok.empty else 0))

        st.divider()
        
        sub_rel = st.tabs(["PUBLICADOR", "PIONEIROS", "⏳ PENDÊNCIAS"])
        
        with sub_rel[0]:
            df_pub = df_ok[df_ok['cat_oficial'] == "PUBLICADOR"]
            if df_pub.empty: st.info("Nenhum relatório.")
            else:
                for _, r in df_pub.iterrows():
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                        col1.write(f"**{r['nome_oficial']}** | ⏱️ {int(r['horas'])}h | 📚 {int(r['estudos_biblicos'])}")
                        col2.download_button("PDF", gerar_pdf_registro_s21(r, mes_sel), f"S21_{r['nome_oficial']}.pdf", key=f"p_{r['id']}")

        with sub_rel[1]:
            df_pion = df_ok[df_ok['cat_oficial'].str.contains("PIONEIRO", na=False)]
            if df_pion.empty: st.info("Nenhum pioneiro entregou ainda.")
            else:
                for _, r in df_pion.iterrows():
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                        col1.write(f"**{r['nome_oficial']}** ({r['cat_oficial']}) | ⏱️ {int(r['horas'])}h")
                        col2.download_button("PDF", gerar_pdf_registro_s21(r, mes_sel), f"S21_{r['nome_oficial']}.pdf", key=f"pi_{r['id']}")

        with sub_rel[2]:
            entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
            ativos = [n for n, d in membros_db.items() if d.get('categoria') != "INATIVO"]
            faltantes = sorted([n for n in ativos if n not in entregaram])
            
            if faltantes:
                st.warning(f"Existem {len(faltantes)} pessoas que ainda não entregaram.")
                for p in faltantes:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"• {p}")
                    if c2.button("Inativar", key=f"ina_{p}"):
                        atualizar_membro(p, "INATIVO"); st.rerun()
            else:
                st.success("Tudo em dia! 100% de entrega.")

    with tab_triage:
        df_tri = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_tri.empty: st.success("Nenhum nome para triagem.")
        else:
            for _, r in df_tri.iterrows():
                with st.container(border=True):
                    st.write(f"Digitado: `{r['nome']}`")
                    sel_nome = st.selectbox("Quem é?", ["-- Novo Cadastro --"] + sorted(list(membros_db.keys())), key=f"t_{r['id']}")
                    if st.button("Confirmar", key=f"b_{r['id']}"):
                        validar_e_gravar_novo_membro(r['id'], r['nome'] if sel_nome == "-- Novo Cadastro --" else sel_nome, "PUBLICADOR")
                        st.rerun()

    with tab_inat:
        st.subheader("Publicadores Inativos")
        inativos = [n for n, d in membros_db.items() if d.get('categoria') == "INATIVO"]
        if not inativos: st.info("Não há inativos.")
        else:
            for n in sorted(inativos):
                c1, c2 = st.columns([4, 1])
                c1.write(f"👤 {n}")
                if c2.button("Reativar", key=f"re_{n}"):
                    atualizar_membro(n, "PUBLICADOR"); st.rerun()

    with tab_cfg:
        # Espaço para exportação massiva e gestão de nomes
        st.subheader("Ferramentas Administrativas")
        if not df_ok.empty:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a") as zf:
                for _, r in df_ok.iterrows():
                    zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_registro_s21(r, mes_sel))
            st.download_button("📥 BAIXAR TUDO EM ZIP", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", use_container_width=True)

    st.sidebar.markdown(f"---")
    st.sidebar.markdown(f"**Membros Cadastrados:** {len(membros_db)}")
    st.sidebar.caption("Parque Aliança - Gestão v3.0")

if __name__ == "__main__":
    main()
