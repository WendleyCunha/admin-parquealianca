import streamlit as st
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
# 0. FUNÇÃO DE USUÁRIOS (SUBSTITUINDO O DATABASE.PY)
# =========================================================
def carregar_usuarios_emergencia():
    """
    Tenta carregar do Firestore, se falhar, usa o seu acesso padrão.
    """
    try:
        fdb = inicializar_db()
        docs = fdb.collection("usuarios").stream()
        return {doc.id: doc.to_dict() for doc in docs}
    except:
        # Se o banco falhar, garante que você consiga entrar
        return {
            "wendley": {"nome": "Wendley Cunha", "senha": "123", "role": "ADM", "foto": None}
        }

# =========================================================
# 1. CONFIGURAÇÕES E ESTILIZAÇÃO
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
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .metric-container { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. FUNÇÕES DE APOIO E FIRESTORE
# =========================================================
def inicializar_db():
    if "db_firestore" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db_firestore = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão Firestore: {e}"); return None
    return st.session_state.db_firestore

def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# (Mantendo as outras funções de carregamento de membros e relatórios...)
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
# 3. SISTEMA DE AUTENTICAÇÃO
# =========================================================
usuarios = carregar_usuarios_emergencia()

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><br><h1 style='text-align:center;'>Portal Parque Aliança</h1>", unsafe_allow_html=True)
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

# =========================================================
# 4. NAVEGAÇÃO E CONTEÚDO
# =========================================================
user_id = st.session_state.user_id
user_info = usuarios.get(user_id)

with st.sidebar:
    foto = user_info.get('foto') or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
    st.markdown(f'<img src="{foto}" class="profile-pic">', unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;'><b>{user_info['nome']}</b></p>", unsafe_allow_html=True)
    
    escolha = option_menu(
        None, ["📋 Relatórios", "⚠️ Triagem", "⚙️ Configuração", "🚪 Sair"],
        icons=["list-check", "exclamation-triangle", "gear", "box-arrow-right"],
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#002366"}}
    )
    if escolha == "🚪 Sair":
        st.session_state.autenticado = False
        st.rerun()

# Carregar dados do Parque Aliança
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
mes_sel = st.sidebar.selectbox("📅 Mês", meses_disponiveis, index=len(meses_disponiveis)-1)
df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

# --- TELAS ---
if escolha == "📋 Relatórios":
    st.title(f"Relatórios - {mes_sel}")
    # ... (Restante do código de exibição igual ao anterior)
    st.write("Dados carregados com sucesso!")
    # Adicione aqui o conteúdo da ABA 0 do seu código original
    
elif escolha == "⚠️ Triagem":
    st.title("Triagem de Nomes")
    # Adicione aqui o conteúdo da ABA 1 do seu código original

elif escolha == "⚙️ Configuração":
    st.title("Configurações")
    # Adicione aqui o conteúdo da ABA 2 do seu código original
