# =============================================================
# estilo.py
# CSS global do app (aplicado uma vez, no main.py) + suporte a
# logo personalizado.
#
# REDESENHO (v6.0):
#  - Removida qualquer cor escura/preta (barra superior, cards de
#    Passagens, badges de histórico, etc. agora seguem a mesma
#    paleta clara dourada/creme do restante do app).
#  - Barra lateral (sidebar) não é mais usada pelo app — os estilos
#    de sidebar foram removidos daqui. Todo filtro agora vive dentro
#    da página, no bloco ".pa-filtros".
#  - Mobile-first: tabs quebram em várias linhas em telas estreitas,
#    cards empilham em coluna única, fontes/paddings reduzem um
#    pouco abaixo de 640px.
#
# LOGO PERSONALIZADO
# -------------------
# Coloque o arquivo do seu logo na RAIZ do projeto (mesmo nível
# de main.py) com um destes nomes — o sistema procura nesta
# ordem e usa o primeiro que encontrar:
#   1. logo.png
#   2. logo.jpg / logo.jpeg
#   3. jw.png   (nome que já existe hoje no repositório)
#
# Se nenhum arquivo for encontrado, o app cai de volta no visual
# antigo (emoji 🕊️ / badge "PA"), sem quebrar nada.
# =============================================================
import os
import base64

import streamlit as st

_LOGO_CANDIDATOS = ["logo.png", "logo.jpg", "logo.jpeg", "jw.png"]


def get_logo_path():
    """Retorna o caminho do arquivo de logo encontrado, ou None."""
    raiz = os.path.dirname(os.path.abspath(__file__))
    for nome_arquivo in _LOGO_CANDIDATOS:
        caminho = os.path.join(raiz, nome_arquivo)
        if os.path.exists(caminho):
            return caminho
    return None


@st.cache_data(show_spinner=False)
def get_logo_base64():
    """Retorna (base64, mime) do logo encontrado, ou (None, None)."""
    caminho = get_logo_path()
    if not caminho:
        return None, None
    mime = "image/png" if caminho.lower().endswith(".png") else "image/jpeg"
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode(), mime


def aplicar_estilo():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    *, *::before, *::after { box-sizing: border-box; }

    html, body, [class*="css"], .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
    }

    .stApp {
        background: linear-gradient(180deg, #FAF7EE 0%, #F4EFDD 100%) !important;
        color: #1A1A1A !important;
    }
    .main .block-container {
        padding: 1rem 1.25rem 3rem !important;
        max-width: 1400px;
    }
    @media (min-width: 900px) {
        .main .block-container { padding: 1.5rem 2.5rem 3rem !important; }
    }

    /* ---- Barra superior clara (nada de preto) ---- */
    header[data-testid="stHeader"] {
        background: #FFFDF6 !important;
        border-bottom: 2px solid #E9D48E !important;
        height: 3rem !important;
    }
    header[data-testid="stHeader"] * { color: #6B5E3C !important; }
    [data-testid="stToolbar"] { color: #6B5E3C !important; }

    /* Sidebar removida do fluxo do app — caso o Streamlit ainda
       renderize o botão de colapsar, escondemos por segurança. */
    [data-testid="collapsedControl"] { display: none !important; }

    h1, h2, h3, h4, h5 {
        color: #1A1A1A !important;
        font-family: 'Inter', sans-serif !important;
    }
    h1 { font-size: 1.5rem !important; font-weight: 800 !important; letter-spacing: -0.02em !important; }
    h2 { font-weight: 700 !important; font-size: 1.15rem !important; }
    h3 { font-weight: 700 !important; font-size: 1.02rem !important; }
    @media (min-width: 900px) {
        h1 { font-size: 1.9rem !important; }
        h2 { font-size: 1.3rem !important; }
    }

    /* ---- Cabeçalho institucional (topo da página, substitui a sidebar) ---- */
    .pa-header {
        display: flex; align-items: center; gap: 14px;
        flex-wrap: wrap; margin-bottom: 0.9rem;
    }
    .pa-header-brand { display: flex; align-items: center; gap: 10px; flex: 1 1 auto; min-width: 220px; }
    .pa-header-title { font-size: 1.05rem; font-weight: 800; color: #1A1A1A; line-height: 1.15; }
    .pa-header-sub   { font-size: 0.72rem; font-weight: 700; color: #B4952E;
        text-transform: uppercase; letter-spacing: 0.07em; margin-top: 1px; }
    @media (min-width: 900px) {
        .pa-header-title { font-size: 1.35rem; }
    }
    .pa-header-user {
        display: flex; align-items: center; gap: 8px;
        background: #FFFFFF; border: 1px solid #EFE3B8; border-radius: 999px;
        padding: 5px 8px 5px 6px; flex: 0 0 auto;
    }
    .pa-avatar {
        width: 28px; height: 28px; border-radius: 50%;
        background: linear-gradient(135deg,#d97706,#f5c451);
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 0.78rem; color: #1A1A1A; flex-shrink: 0;
    }
    .pa-header-user-name { font-size: 0.8rem; font-weight: 700; color: #1A1A1A; line-height: 1.1; }
    .pa-header-user-role { font-size: 0.63rem; color: #9C8A46; text-transform: uppercase; letter-spacing: 0.05em; }

    /* ---- Barra de filtros dentro da página (substitui a sidebar) ---- */
    .pa-filtros {
        background: #FFFFFF; border: 1px solid #EFE3B8; border-radius: 14px;
        padding: 0.9rem 1rem; margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(140,110,20,0.06);
    }
    .pa-filtros-label {
        font-size: 0.68rem; font-weight: 800; color: #9C8A46;
        text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;
    }
    .mes-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: #FBF1D4; border: 1px solid #E9D48E; border-radius: 999px;
        padding: 5px 14px; font-size: 0.75rem; font-weight: 700; color: #8A6D14;
    }
    .mes-badge-historico {
        display: inline-flex; align-items: center; gap: 6px;
        background: #F1EAD2; border: 1px solid #E2D5A0; border-radius: 999px;
        padding: 5px 14px; font-size: 0.75rem; font-weight: 700; color: #6B6141;
    }
    .mes-dot { width: 7px; height: 7px; border-radius: 50%; background: #C9A227; display: inline-block; }

    /* ---- Tabs: pílulas claras, quebram linha no mobile ---- */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 4px; flex-wrap: wrap !important; row-gap: 6px;
        border-bottom: 1px solid #EFE3B8 !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"] {
        color: #8A7D55 !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        background: transparent !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 8px 12px !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
        color: #1A1A1A !important;
        background: #FBF1D4 !important;
        border-bottom: 2px solid #C9A227 !important;
    }
    @media (max-width: 640px) {
        [data-testid="stTabs"] [data-testid="stTab"] {
            font-size: 0.74rem !important; padding: 6px 9px !important;
        }
    }

    /* ---- Cards & Metrics ---- */
    .pa-card, .pa-metric {
        background: linear-gradient(180deg, #FFFFFF 0%, #FBF7EA 100%) !important;
        border: 1px solid #EFE3B8 !important;
        border-top: 3px solid #C9A227 !important;
        border-radius: 14px !important;
        padding: 1.1rem !important;
        margin-bottom: 0.8rem !important;
        box-shadow: 0 2px 6px rgba(140,110,20,0.07), 0 1px 2px rgba(201,162,39,0.10);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }
    .pa-card:hover, .pa-metric:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 26px rgba(140,110,20,0.14), 0 3px 10px rgba(201,162,39,0.22);
        border-color: #C9A227 !important;
    }
    .pa-metric-value {
        font-size: 22px !important;
        font-weight: 800 !important;
        color: #1A1A1A !important;
        letter-spacing: -0.01em !important;
    }
    .pa-metric-label {
        font-size: 10.5px !important;
        font-weight: 700 !important;
        color: #9C8A46 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        margin-top: 2px !important;
    }
    .pa-card-header {
        font-size: 0.92rem !important;
        font-weight: 700 !important;
        color: #1A1A1A !important;
        margin-bottom: 4px !important;
    }
    .pa-card-sub {
        font-size: 0.78rem !important;
        color: #6B6B6B !important;
        font-weight: 500 !important;
    }

    /* ---- Painéis de aviso / info claros (substituem os antigos escuros) ---- */
    .pa-aviso-sucesso {
        background: #EEF9F0; border: 1px solid #BFE8C8; border-radius: 10px;
        padding: 10px 14px; color: #1D6B33; font-size: 0.85rem;
    }
    .pa-aviso-atencao {
        background: #FFF6E5; border: 1px solid #F0D48E; border-radius: 10px;
        padding: 10px 14px; color: #8A6D14; font-size: 0.85rem;
    }
    .pa-aviso-erro {
        background: #FDECEC; border: 1px solid #F3B8B8; border-radius: 10px;
        padding: 10px 14px; color: #A32A2A; font-size: 0.85rem;
    }
    .pa-aviso-neutro {
        background: #F4F1E4; border: 1px solid #E6DEC2; border-radius: 10px;
        padding: 10px 14px; color: #5B5540; font-size: 0.85rem;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] > div > div {
        background: #FFFFFF !important;
        border: 1px solid #E8E8E8 !important;
        color: #1A1A1A !important;
        border-radius: 8px !important;
    }

    .stButton > button {
        background: transparent !important;
        color: #B4952E !important;
        border: 1.5px solid #C9A227 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    button[kind="primary"], .stButton [kind="primary"] > button {
        background: #C9A227 !important;
        color: #111111 !important;
        border: none !important;
    }

    /* ---- Tabela de Assistência ---- */
    .assist-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
    }
    .assist-table th {
        background: #FBF1D4;
        color: #6B5E3C;
        padding: 8px 10px;
        text-align: center;
        font-weight: 700;
        font-size: 0.74rem;
        border: 1px solid #EFE3B8;
    }
    .assist-table th.col-mes {
        background: #F5E8B8;
        text-align: left;
    }
    .assist-table td {
        padding: 7px 10px;
        border: 1px solid #EEE3C7;
        text-align: center;
        background: #FFFFFF;
        color: #1A1A1A;
    }
    .assist-table td.col-mes {
        text-align: left;
        font-weight: 500;
        background: #FFFDF6;
    }
    .assist-table tr.row-total td {
        background: #FBF1D4;
        font-weight: 700;
        border-top: 2px solid #C9A227;
    }
    .assist-table .ano-header {
        background: #C9A227;
        color: #111;
        font-size: 1.05rem;
        font-weight: 800;
        text-align: center;
        padding: 6px;
    }

    /* Empilhar colunas do Streamlit em telas de celular quando fizer
       sentido — várias abas usam st.columns([...]) para formulários
       lado a lado, que ficam apertados em telas < 640px. */
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        div[data-testid="stHorizontalBlock"] > div {
            min-width: 100% !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
