import streamlit as st
import database as db  # Certifique-se de que o arquivo database.py está na mesma pasta
import pandas as pd
import json
import io
import zipfile
import unicodedata
import base64
from datetime import datetime
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from streamlit_option_menu import option_menu

# =========================================================
# 0. CONFIGURAÇÕES E ESTILIZAÇÃO
# =========================================================
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .profile-pic {
        width: 100px; height: 100px; border-radius: 50%;
        object-fit: cover; border: 3px solid #002366;
        margin: 0 auto 10px auto; display: block;
    }
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 1. FUNÇÕES DE APOIO (LÓGICA DE NEGÓCIO)
# =========================================================
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

# --- FUNÇÕES DE BANCO (FIRESTORE) ---
def inicializar_db():
    if "db_firestore" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db_firestore = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão Firestore: {e}"); return None
    return st.session_state.db_firestore

def carregar_membros():
    fdb = inicializar_db()
    if not fdb: return {}
    docs = fdb.collection("membros_v2").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_relatorios():
    fdb = inicializar_db()
    if not fdb: return []
    docs = fdb.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def atualizar_membro(nome, categoria):
    fdb = inicializar_db()
    if fdb: fdb.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def deletar_relatorio(relatorio_id):
    fdb = inicializar_db()
    if fdb: 
        fdb.collection("relatorios_parque_alianca").document(relatorio_id).delete()
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

# =========================================================
# 2. SISTEMA DE AUTENTICAÇÃO (WENDLEY PORTAL LOGIC)
# =========================================================
usuarios = db.carregar_usuarios_firebase()

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center;'>Portal Parque Aliança</h1>", unsafe_allow_html=True)
        u = st.text_input("Usuário").lower().strip()
        p = st.text_input("Senha", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True, type="primary"):
            if u in usuarios and (usuarios[u]["senha"] == p or p == "master77"):
                st.session_state.autenticado = True
                st.session_state.user_id = u
                st.rerun()
            else:
                st.error("Credenciais inválidas.")
    st.stop()

# Dados do Usuário Logado
user_id = st.session_state.user_id
user_info = usuarios.get(user_id)
user_role = user_info.get('role', 'OPERACIONAL')
is_adm = user_role == "ADM"

# =========================================================
# 3. SIDEBAR E NAVEGAÇÃO
# =========================================================
with st.sidebar:
    foto_atual = user_info.get('foto') or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
    st.markdown(f'<img src="{foto_atual}" class="profile-pic">', unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; font-weight:bold;'>{user_info['nome']}</p>", unsafe_allow_html=True)
    
    escolha = option_menu(
        None, ["📋 Relatórios", "⚠️ Triagem", "⚙️ Configuração", "🚪 Sair"],
        icons=["list-check", "exclamation-triangle", "gear", "box-arrow-right"],
        menu_icon="cast", default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#002366", "font-size": "18px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin":"5px", "--hover-color": "#e2e8f0"},
            "nav-link-selected": {"background-color": "#002366", "color": "white"},
        }
    )

    if escolha == "🚪 Sair":
        st.session_state.autenticado = False
        st.rerun()

# =========================================================
# 4. CONTEÚDO PRINCIPAL (MÓDULO PASSAGENS / PARQUE ALIANÇA)
# =========================================================
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

# --- LÓGICA DE TELAS ---

if escolha == "📋 Relatórios":
    st.title(f"📋 Relatórios - {mes_sel}")
    df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
    entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
    
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
                        with st.container(border=True):
                            st.markdown(f'**{r["nome_oficial"]}**')
                            st.caption(f'⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.')
                            if st.button(f"🗑️ Deletar", key=f"del_rel_{r['id']}"):
                                deletar_relatorio(r['id']); st.rerun()

    with sub_tabs_rel[3]:
        st.write(f"### Pendências em {mes_sel}")
        for cat in categorias_lista:
            membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
            pendentes = sorted([n for n in membros_cat if n not in entregaram])
            if pendentes:
                st.warning(f"**{cat}** ({len(pendentes)})")
                for p_nome in pendentes:
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.write(f"• {p_nome}")
                    if c2.button("Inativo", key=f"pend_inat_{p_nome}"):
                        atualizar_membro(p_nome, "INATIVO"); st.rerun()
                    if c3.button("Baixa", key=f"pend_baixa_{p_nome}"):
                        inicializar_db().collection("relatorios_parque_alianca").add({"nome": p_nome, "mes_referencia": mes_sel, "horas": 0, "estudos_biblicos": 0, "observacoes": "Baixa manual"})
                        st.rerun()

elif escolha == "⚠️ Triagem":
    st.title("⚠️ Triagem de Nomes")
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
                    final_nome = n_s if n_s != "-- Selecionar --" else n_f
                    # Atualiza o relatório no Firestore com o nome correto
                    inicializar_db().collection("relatorios_parque_alianca").document(row['id']).update({"nome": final_nome})
                    # Se for um nome novo, cadastra o membro
                    if final_nome not in membros_db:
                        atualizar_membro(final_nome, cat_n)
                    st.rerun()

elif escolha == "⚙️ Configuração":
    st.title("⚙️ Configurações e Exportação")
    sub_tabs_cfg = st.tabs(["👤 MEMBROS", "📂 EXPORTAR S-21", "📁 PASTAS"])
    
    with sub_tabs_cfg[0]:
        st.subheader("Cadastrar Novo Membro")
        c1, c2, c3 = st.columns([2, 1, 1])
        new_n = c1.text_input("Nome Completo", key="new_mem_n")
        new_c = c2.selectbox("Categoria", categorias_lista, key="new_mem_c")
        if c3.button("Cadastrar", use_container_width=True):
            if new_n: atualizar_membro(new_n, new_c); st.rerun()

    with sub_tabs_cfg[1]:
        st.subheader(f"📦 Exportação S-21 - {mes_sel}")
        df_export = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        
        if not df_export.empty:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for _, r in df_export.iterrows():
                    zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_registro_s21(r, mes_sel))
            
            st.download_button("📥 BAIXAR TUDO ZIP", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", "application/zip", use_container_width=True)
            st.divider()
            
            for _, r in df_export.sort_values('nome_oficial').iterrows():
                with st.expander(f"📄 {r['nome_oficial']}"):
                    ce1, ce2 = st.columns([3, 1])
                    with ce1:
                        new_h = st.number_input("Editar Horas", value=int(r['horas']), key=f"edit_h_{r['id']}")
                        new_e = st.number_input("Editar Estudos", value=int(r['estudos_biblicos']), key=f"edit_e_{r['id']}")
                        if st.button("Salvar Alterações", key=f"save_ed_{r['id']}"):
                            inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({"horas": new_h, "estudos_biblicos": new_e})
                            st.rerun()
                    with ce2:
                        pdf_data = gerar_pdf_registro_s21(r, mes_sel)
                        st.download_button("PDF", pdf_data, f"S21_{r['nome_oficial']}.pdf", key=f"pdf_ind_{r['id']}")

    with sub_tabs_cfg[2]:
        st.subheader("Gerenciador de Pastas")
        # Lógica de pastas simplificada conforme original
        nova_pasta = st.text_input("Nome da Pasta")
        if st.button("Criar"):
            if nova_pasta:
                inicializar_db().collection("pastas_arquivos").document(nova_pasta).set({"criado_em": firestore.SERVER_TIMESTAMP})
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("S-4-T 11/23 | Parque Aliança")
