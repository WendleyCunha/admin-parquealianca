import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from pypdf import PdfReader, PdfWriter

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

def mostrar_painel_passagens():
    st.header("🚌 Gestão de Passagens VGP")
    
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def gerar_pdf_registro_s21(row, mes_sel):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontSize=16, alignment=1, spaceAfter=20, fontName='Helvetica-Bold')
    elements.append(Paragraph("REGISTRO DE PUBLICADOR DE CONGREGAÇÃO", title_style))
    data_cabecalho = [[Paragraph(f"<b>Nome:</b> {row['nome_oficial']}", styles['Normal']), ""], [f"Mês: {mes_sel}", "Ano de serviço: 2026"]]
    t_cabecalho = Table(data_cabecalho, colWidths=[350, 150])
    elements.append(t_cabecalho)
    elements.append(Spacer(1, 15))
    header = ["Participou no\nministério", "Estudos\nbíblicos", "Pioneiro\nauxiliar", "Horas", "Observações"]
    check_min = "X" if row['horas'] > 0 else ""
    check_pion = "X" if row['cat_oficial'] == "PIONEIRO AUXILIAR" else ""
    corpo = [[f"[{check_min}]", str(int(row['estudos_biblicos'])), f"[{check_pion}]", str(int(row['horas'])), row.get('observacoes', '')]]
    t_dados = Table([header] + corpo, colWidths=[100, 80, 80, 70, 160])
    t_dados.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 10), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t_dados)
    doc.build(elements)
    return buffer.getvalue()

# --- FUNÇÕES DE BANCO ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão: {e}"); return None
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

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db: 
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório removido!")

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        if entrada_norm == oficial_norm: return nome_oficial
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.80 else None

# --- NOVA FUNÇÃO: CORRIGE O NAMEERROR ---
def validar_e_gravar_novo_membro(relatorio_id, nome_final, categoria):
    db = inicializar_db()
    if not db: return
    
    # 1. Cria ou atualiza o cadastro do membro
    db.collection("membros_v2").document(nome_final).set({
        "categoria": categoria,
        "nome_oficial": nome_final
    }, merge=True)
    
    # 2. Atualiza o relatório para que o nome coincida com o banco
    db.collection("relatorios_parque_alianca").document(relatorio_id).update({
        "nome": nome_final
    })
    st.success(f"Membro {nome_final} validado!")

# --- MAIN ---
def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial and nome_oficial in membros_db:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["MARÇO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tabs_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 0: RELATÓRIOS ---
    with tabs_principal[0]:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
        st.subheader(f"Resumo de {mes_sel}")
        sub_tabs_rel = st.tabs(["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "⏳ PENDÊNCIAS"])
        
        for i, cat in enumerate(categorias_lista):
            with sub_tabs_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()
                if df_cat.empty: st.info(f"Nenhum relatório de {cat} recebido.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{len(df_cat)}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-container"><div class="metric-label">Total Horas</div><div class="metric-value">{int(df_cat["horas"].sum())}h</div></div>', unsafe_allow_html=True)
                    m3.markdown(f'<div class="metric-container"><div class="metric-label">Total Estudos</div><div class="metric-value">{int(df_cat["estudos_biblicos"].sum())}</div></div>', unsafe_allow_html=True)
                    
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>', unsafe_allow_html=True)
                            if st.button(f"🗑️ Deletar", key=f"del_rel_{r['id']}"):
                                deletar_relatorio(r['id']); st.rerun()

        with sub_tabs_rel[3]:
            st.write(f"### Quem ainda não entregou em {mes_sel}")
            for cat in categorias_lista:
                membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
                pendentes = sorted([n for n in membros_cat if n not in entregaram])
                if pendentes:
                    st.warning(f"**{cat}** ({len(pendentes)})")
                    for p_nome in pendentes:
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"• {p_nome}")
                        if c2.button("Mover Inativo", key=f"pend_inat_{p_nome}"):
                            atualizar_membro(p_nome, "INATIVO"); st.rerun()
                        if c3.button("📥 Baixa Manual", key=f"pend_baixa_{p_nome}"):
                            inicializar_db().collection("relatorios_parque_alianca").add({"nome": p_nome, "mes_referencia": mes_sel, "horas": 0, "estudos_biblicos": 0, "observacoes": "Baixa manual"})
                            st.rerun()

    # --- ABA 1: TRIAGEM ---
    with tabs_principal[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Tudo certo nos nomes!")
        else:
            nomes_existentes = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.markdown(f'<div class="triagem-box"><b>Digitado:</b> {row["nome"]} | <b>Horas:</b> {row["horas"]}</div>', unsafe_allow_html=True)
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_existentes)
                    idx_sug = nomes_existentes.index(sugestao) + 1 if sugestao else 0
                    c1, c2 = st.columns(2)
                    n_f = c1.text_input("Novo Nome?", value=row['nome'], key=f"tri_n_{row['id']}")
                    n_s = c2.selectbox("É algum destes?", ["-- Selecionar --"] + nomes_existentes, index=idx_sug, key=f"tri_s_{row['id']}")
                    cat_n = st.selectbox("Categoria:", categorias_lista, key=f"tri_c_{row['id']}")
                    if st.button("✅ VALIDAR", key=f"tri_v_{row['id']}", use_container_width=True):
                        validar_e_gravar_novo_membro(row['id'], n_s if n_s != "-- Selecionar --" else n_f, cat_n)
                        st.rerun()

   # --- MAIN ---
def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial and nome_oficial in membros_db:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tabs_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 0: RELATÓRIOS ---
    with tabs_principal[0]:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
        st.subheader(f"Resumo de {mes_sel}")
        sub_tabs_rel = st.tabs(["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "⏳ PENDÊNCIAS"])
        
        for i, cat in enumerate(categorias_lista):
            with sub_tabs_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()
                if df_cat.empty: 
                    st.info(f"Nenhum relatório de {cat} recebido.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{len(df_cat)}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-container"><div class="metric-label">Total Horas</div><div class="metric-value">{int(df_cat["horas"].sum())}h</div></div>', unsafe_allow_html=True)
                    m3.markdown(f'<div class="metric-container"><div class="metric-label">Total Estudos</div><div class="metric-value">{int(df_cat["estudos_biblicos"].sum())}</div></div>', unsafe_allow_html=True)
                    
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>', unsafe_allow_html=True)
                            if st.button(f"🗑️ Deletar", key=f"del_rel_{r['id']}"):
                                deletar_relatorio(r['id']); st.rerun()

        with sub_tabs_rel[3]:
            st.write(f"### Quem ainda não entregou em {mes_sel}")
            for cat in categorias_lista:
                membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
                pendentes = sorted([n for n in membros_cat if n not in entregaram])
                if pendentes:
                    st.warning(f"**{cat}** ({len(pendentes)})")
                    for p_nome in pendentes:
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"• {p_nome}")
                        if c2.button("Mover Inativo", key=f"pend_inat_{p_nome}"):
                            atualizar_membro(p_nome, "INATIVO"); st.rerun()
                        if c3.button("📥 Baixa Manual", key=f"pend_baixa_{p_nome}"):
                            inicializar_db().collection("relatorios_parque_alianca").add({"nome": p_nome, "mes_referencia": mes_sel, "horas": 0, "estudos_biblicos": 0, "observacoes": "Baixa manual"})
                            st.rerun()

    # --- ABA 1: TRIAGEM ---
    with tabs_principal[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: 
            st.success("✨ Tudo certo nos nomes!")
        else:
            nomes_existentes = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.markdown(f'<div class="triagem-box"><b>Digitado:</b> {row["nome"]} | <b>Horas:</b> {row["horas"]}</div>', unsafe_allow_html=True)
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_existentes)
                    idx_sug = nomes_existentes.index(sugestao) + 1 if sugestao else 0
                    c1, c2 = st.columns(2)
                    n_f = c1.text_input("Novo Nome?", value=row['nome'], key=f"tri_n_{row['id']}")
                    n_s = c2.selectbox("É algum destes?", ["-- Selecionar --"] + nomes_existentes, index=idx_sug, key=f"tri_s_{row['id']}")
                    cat_n = st.selectbox("Categoria:", categorias_lista, key=f"tri_c_{row['id']}")
                    if st.button("✅ VALIDAR", key=f"tri_v_{row['id']}", use_container_width=True):
                        validar_e_gravar_novo_membro(row['id'], n_s if n_s != "-- Selecionar --" else n_f, cat_n)
                        st.rerun()

    # --- ABA 2: CONFIGURAÇÃO ---
    with tabs_principal[2]:
        sub_tabs_cfg = st.tabs(["👤 MEMBROS", "📂 REGISTROS TOTAIS (PDF/ZIP)"])
        
        with sub_tabs_cfg[0]:
            st.subheader("Cadastrar Novo Membro")
            c1, c2, c3 = st.columns([2, 1, 1])
            new_n = c1.text_input("Nome Completo", key="new_mem_n")
            new_c = c2.selectbox("Categoria", categorias_lista, key="new_mem_c")
            if c3.button("Cadastrar", use_container_width=True):
                if new_n: 
                    atualizar_membro(new_n, new_c)
                    st.rerun()

        with sub_tabs_cfg[1]:
            st.subheader(f"📦 Exportação S-21 - {mes_sel}")
            
            df_export = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
            
            if not df_export.empty:
                # 1. BOTÃO ZIP GERAL
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for _, r in df_export.iterrows():
                        zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_registro_s21(r, mes_sel))
                
                st.download_button("📥 BAIXAR TUDO ZIP (S-21)", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", "application/zip", use_container_width=True)
                
                st.divider()
                st.write("### ✏️ Ajuste de Dados e Categoria")
                
                # 2. EDIÇÃO INDIVIDUAL (CATEGORIA + HORAS)
                for _, r in df_export.sort_values('nome_oficial').iterrows():
                    with st.expander(f"📄 {r['nome_oficial']} ({r['cat_oficial']})"):
                        ce1, ce2, ce3 = st.columns([2, 1, 1])
                        
                        # Ajuste de Categoria
                        nova_cat = ce1.selectbox(
                            "Mudar Categoria", 
                            categorias_lista, 
                            index=categorias_lista.index(r['cat_oficial']) if r['cat_oficial'] in categorias_lista else 0,
                            key=f"edit_cat_{r['id']}"
                        )
                        
                        new_h = ce2.number_input("Horas", value=int(r['horas']), key=f"edit_h_{r['id']}")
                        new_e = ce3.number_input("Estudos", value=int(r['estudos_biblicos']), key=f"edit_e_{r['id']}")
                        
                        b_col1, b_col2 = st.columns(2)
                        
                        if b_col1.button("💾 Salvar", key=f"save_ed_{r['id']}", use_container_width=True):
                            # Atualiza Relatório do Mês
                            inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({
                                "horas": new_h, 
                                "estudos_biblicos": new_e
                            })
                            # Atualiza Cadastro do Membro (Categoria)
                            atualizar_membro(r['nome_oficial'], nova_cat)
                            st.success("Atualizado!")
                            st.rerun()
                            
                        pdf_data = gerar_pdf_registro_s21(r, mes_sel)
                        b_col2.download_button("📥 PDF Individual", pdf_data, f"S21_{r['nome_oficial']}.pdf", key=f"pdf_ind_{r['id']}", use_container_width=True)

    st.caption("v2.0.4 | Parque Aliança | Gestão Administrativa")

if __name__ == "__main__":
    main()
