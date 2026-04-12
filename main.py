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
st.set_page_config(page_title="Admin Parque Aliança Pro", layout="wide", page_icon="🚀")

# --- ESTILIZAÇÃO CUSTOMIZADA ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #002366; }
    .stButton>button { border-radius: 5px; height: 3em; width: 100%; }
    .status-card { 
        padding: 20px; border-radius: 10px; border-left: 5px solid #002366; 
        background: white; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE NÚCLEO (DB & LOGIC) ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error("Erro na conexão com o Banco de Dados."); return None
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

def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.85 else None

# --- GERADOR DE PDF (S-21 PROFESSIONAL) ---
def gerar_pdf_s21(row, mes_sel):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Cabeçalho Estilizado
    elements.append(Paragraph("REGISTRO DE PUBLICADOR DE CONGREGAÇÃO", styles['Title']))
    elements.append(Spacer(1, 12))
    
    data_info = [
        [Paragraph(f"<b>Nome:</b> {row['nome_oficial'].upper()}", styles['Normal']), ""],
        [f"Mês de Referência: {mes_sel}", "Ano de Serviço: 2026"]
    ]
    elements.append(Table(data_info, colWidths=[350, 150]))
    elements.append(Spacer(1, 20))
    
    # Tabela de Dados
    headers = ["Participou", "Estudos", "Pioneiro Aux.", "Horas", "Observações"]
    part = "Sim" if row['horas'] > 0 else "Não"
    pion = "X" if row['cat_oficial'] == "PIONEIRO AUXILIAR" else ""
    
    data_tabela = [headers, [part, str(int(row['estudos_biblicos'])), pion, str(int(row['horas'])), row.get('observacoes', '')]]
    
    t = Table(data_tabela, colWidths=[80, 70, 80, 60, 180])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# --- INTERFACE PRINCIPAL ---
def main():
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3208/3208726.png", width=100)
    st.sidebar.title("Painel de Controle")
    
    membros_db = carregar_membros()
    relatorios_raw = carregar_relatorios()
    
    # Processamento de DF
    if relatorios_raw:
        df = pd.DataFrame(relatorios_raw)
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        df['mes_referencia'] = df['mes_referencia'].str.upper()
    else:
        df = pd.DataFrame(columns=['nome', 'horas', 'estudos_biblicos', 'mes_referencia'])

    meses = sorted(df['mes_referencia'].unique()) if not df.empty else ["MARÇO 2026"]
    mes_sel = st.sidebar.selectbox("Selecionar Mês", meses)

    # Identificação de nomes
    if not df.empty:
        df['nome_oficial'] = df['nome'].apply(lambda x: normalizar_nome_no_banco(x, membros_db.keys()))
        df['cat_oficial'] = df['nome_oficial'].apply(lambda x: membros_db[x].get('categoria', 'PUBLICADOR') if x else 'TRIAGEM')
        df_mes = df[df['mes_referencia'] == mes_sel]
    else:
        df_mes = pd.DataFrame()

    # ABAS
    t1, t2, t3, t4 = st.tabs(["📈 DASHBOARD", "📑 RELATÓRIOS", "👥 MEMBROS / INATIVOS", "🔍 TRIAGEM"])

    with t1:
        if not df_mes.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Horas", f"{int(df_mes['horas'].sum())}h")
            c2.metric("Total Estudos", int(df_mes['estudos_biblicos'].sum()))
            c3.metric("Relatórios", len(df_mes))
            
            entregaram = df_mes['nome_oficial'].dropna().unique()
            faltam = [n for n in membros_db.keys() if n not in entregaram and membros_db[n].get('categoria') != "INATIVO"]
            c4.metric("Pendentes", len(faltam))

            st.write("### Quem ainda não entregou:")
            if faltam:
                cols = st.columns(3)
                for i, p in enumerate(faltam):
                    cols[i%3].warning(f"⚠️ {p}")
            else:
                st.success("Todos os relatórios foram entregues!")

    with t2:
        st.subheader(f"Gerenciamento de Documentos - {mes_sel}")
        df_ok = df_mes[df_mes['cat_oficial'] != 'TRIAGEM']
        
        if not df_ok.empty:
            # Botão de Exportação Massiva (Mágico)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a") as zf:
                for _, r in df_ok.iterrows():
                    zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_s21(r, mes_sel))
            
            st.download_button("📥 BAIXAR TODOS OS PDFs (ZIP)", zip_buffer.getvalue(), f"Relatorios_{mes_sel}.zip", use_container_width=True)
            
            st.divider()
            for _, r in df_ok.iterrows():
                with st.expander(f"📄 {r['nome_oficial']} ({r['cat_oficial']})"):
                    col_a, col_b = st.columns([2,1])
                    pdf_bytes = gerar_pdf_s21(r, mes_sel)
                    col_a.write(f"Horas: {r['horas']} | Estudos: {r['estudos_biblicos']}")
                    col_b.download_button("Baixar PDF", pdf_bytes, f"S21_{r['nome_oficial']}.pdf", key=f"btn_{r['id']}")

    with t3:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.subheader("Ativos")
            for n, d in membros_db.items():
                if d.get('categoria') != "INATIVO":
                    with st.container(border=True):
                        st.write(f"**{n}** - {d.get('categoria')}")
                        if st.button("Mover para Inativo", key=f"to_ina_{n}"):
                            inicializar_db().collection("membros_v2").document(n).update({"categoria": "INATIVO"})
                            st.rerun()
        with col_m2:
            st.subheader("Inativos")
            for n, d in membros_db.items():
                if d.get('categoria') == "INATIVO":
                    with st.container(border=True):
                        st.write(f"❌ {n}")
                        if st.button("Reativar", key=f"re_act_{n}"):
                            inicializar_db().collection("membros_v2").document(n).update({"categoria": "PUBLICADOR"})
                            st.rerun()

    with t4:
        st.subheader("Nomes não reconhecidos")
        df_triagem = df_mes[df_mes['cat_oficial'] == 'TRIAGEM'] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty:
            st.success("Nenhum nome pendente de triagem.")
        else:
            for _, r in df_triagem.iterrows():
                with st.container(border=True):
                    st.write(f"Digitado: **{r['nome']}**")
                    nome_correto = st.selectbox("Corrigir para:", ["-- Selecione --"] + list(membros_db.keys()), key=f"sel_{r['id']}")
                    if st.button("Confirmar Correção", key=f"conf_{r['id']}"):
                        if nome_correto != "-- Selecione --":
                            inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({"nome": nome_correto})
                            st.rerun()

if __name__ == "__main__":
    main()
