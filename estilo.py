# =============================================================
# estilo.py
# CSS global do app (aplicado uma vez, no main.py) + suporte a
# logo personalizado.
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
#
# Para trocar o logo: é só substituir o arquivo na raiz do repo
# por um com um desses nomes (ou adicionar o seu nome à lista
# _LOGO_CANDIDATOS abaixo).
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    *, *::before, *::after { box-sizing: border-box; }

    html, body, [class*="css"], .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
    }

    .stApp {
        background: linear-gradient(180deg, #FAF7EE 0%, #F4EFDD 100%) !important;
        color: #1A1A1A !important;
    }
    .main .block-container {
        padding: 1.5rem 2.5rem 3rem !important;
        max-width: 1400px;
    }

    /* ---- Barra superior única em preto (referência: jw.org) ---- */
    header[data-testid="stHeader"] {
        background: #111111 !important;
        border-bottom: 3px solid #C9A227 !important;
        height: 3.1rem !important;
    }
    header[data-testid="stHeader"] * {
        color: #F4EFDD !important;
    }
    [data-testid="stToolbar"] { color: #F4EFDD !important; }

    /* ---- Sidebar clara e dourada ---- */
    [data-testid="stSidebar"] {
        background: #FFFDF6 !important;
        border-right: 1px solid #EEE3B8 !important;
    }

    [data-testid="stSidebar"],
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {
        color: #6B5E3C !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #1A1A1A !important;
    }

    [data-testid="stSidebar"] .pa-card *,
    [data-testid="stSidebar"] .pa-metric * {
        color: #1A1A1A !important;
    }
    [data-testid="stSidebar"] .pa-metric-label {
        color: #9C8A46 !important;
    }

    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
        background: #FFFFFF !important;
        border: 1px solid #E7D9A0 !important;
        color: #1A1A1A !important;
        border-radius: 8px !important;
    }

    .sidebar-brand { text-align: center; padding: 8px 0 2px; }
    .sidebar-brand-title {
        font-size: 1.05rem !important; font-weight: 800 !important;
        color: #1A1A1A !important; letter-spacing: -0.01em;
    }
    .sidebar-brand-sub {
        font-size: 0.7rem !important; font-weight: 700 !important;
        color: #B4952E !important; text-transform: uppercase;
        letter-spacing: 0.09em; margin-top: 2px;
    }
    .sidebar-divider {
        border: none !important; border-top: 1px solid #EEE3B8 !important;
        margin: 14px 0 !important;
    }
    .mes-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: #FBF1D4; border: 1px solid #E9D48E; border-radius: 999px;
        padding: 5px 14px; font-size: 0.75rem; font-weight: 700; color: #8A6D14;
    }
    .mes-dot { width: 7px; height: 7px; border-radius: 50%; background: #C9A227; display: inline-block; }

    h1, h2, h3, h4, h5 {
        color: #1A1A1A !important;
        font-family: 'Inter', sans-serif !important;
    }
    h1 { font-size: 1.9rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
    h2 { font-weight: 600 !important; font-size: 1.3rem !important; }

    [data-testid="stTabs"] [data-testid="stTab"] {
        color: #888888 !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
        color: #C9A227 !important;
        border-bottom: 2px solid #C9A227 !important;
    }

    /* ---- Cards & Metrics — versão dourada elevada ---- */
    .pa-card, .pa-metric {
        background: linear-gradient(180deg, #FFFFFF 0%, #FBF7EA 100%) !important;
        border: 1px solid #EFE3B8 !important;
        border-top: 3px solid #C9A227 !important;
        border-radius: 14px !important;
        padding: 1.2rem !important;
        margin-bottom: 0.8rem !important;
        box-shadow: 0 2px 6px rgba(140,110,20,0.07), 0 1px 2px rgba(201,162,39,0.10);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }
    .pa-card:hover, .pa-metric:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 26px rgba(140,110,20,0.14), 0 3px 10px rgba(201,162,39,0.22);
        border-color: #C9A227 !important;
    }

    .pa-metric-value {
        font-size: 24px !important;
        font-weight: 800 !important;
        color: #1A1A1A !important;
        letter-spacing: -0.01em !important;
    }
    .pa-metric-label {
        font-size: 11px !important;
        font-weight: 700 !important;
        color: #9C8A46 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        margin-top: 2px !important;
    }

    .pa-card-header {
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        color: #1A1A1A !important;
        margin-bottom: 4px !important;
    }
    .pa-card-sub {
        font-size: 0.8rem !important;
        color: #6B6B6B !important;
        font-weight: 500 !important;
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
        color: #C9A227 !important;
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
        font-size: 0.82rem;
    }
    .assist-table th {
        background: #1A1A1A;
        color: #FFFFFF;
        padding: 8px 10px;
        text-align: center;
        font-weight: 600;
        font-size: 0.75rem;
        border: 1px solid #333;
    }
    .assist-table th.col-mes {
        background: #2A2A2A;
        text-align: left;
    }
    .assist-table td {
        padding: 7px 10px;
        border: 1px solid #DEDEDE;
        text-align: center;
        background: #FFFFFF;
        color: #1A1A1A;
    }
    .assist-table td.col-mes {
        text-align: left;
        font-weight: 500;
        background: #FAFAFA;
    }
    .assist-table tr.row-total td {
        background: #F0F0F0;
        font-weight: 700;
        border-top: 2px solid #AAAAAA;
    }
    .assist-table .ano-header {
        background: #C9A227;
        color: #111;
        font-size: 1.1rem;
        font-weight: 800;
        text-align: center;
        padding: 6px;
    }
    </style>
    """, unsafe_allow_html=True)
