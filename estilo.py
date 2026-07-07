# =============================================================
# estilo.py
# CSS global do app (aplicado uma vez, no main.py) + suporte a
# logo personalizado.
#
# ESTRUTURA (v6.1): este arquivo NÃO tem mais nenhuma cor "dura"
# escrita aqui dentro. O CSS abaixo usa marcadores (ex: __PRIMARIA__)
# que são substituídos pelos valores de tema.CORES na hora de montar
# a folha de estilo. Ou seja: para trocar a paleta do app inteiro,
# o único arquivo que você edita é tema.py — nunca este aqui.
#
# Sidebar não é mais usada pelo app — filtros vivem dentro da
# página, no bloco ".pa-filtros". Mobile-first: tabs quebram em
# várias linhas em telas estreitas, cards empilham em coluna única.
#
# ATUALIZAÇÃO (v6.2):
#  - CORREÇÃO DE VAZAMENTO ENTRE ABAS: o Streamlit controla qual
#    conteúdo de aba fica visível usando o atributo HTML nativo
#    "hidden" no painel (elemento [data-baseweb="tab-panel"]). Como
#    quase todas as regras deste arquivo usam !important, havia risco
#    de conflito de prioridade entre o CSS customizado e o mecanismo
#    interno do Streamlit — o painel "escondido" podia continuar
#    sendo desenhado na tela junto com o painel ativo (o usuário via
#    o conteúdo de mais de uma aba ao mesmo tempo).
#    Corrigido reforçando explicitamente, com máxima especificidade,
#    que SOMENTE o painel sem o atributo "hidden" é exibido — todos
#    os demais ficam display:none, não importa o que mais exista na
#    folha de estilo. Veja o bloco "CORREÇÃO: isolar painel da aba
#    ativa" logo abaixo do bloco de estilo das Tabs.
#  - Extra: pequena transição de opacidade no conteúdo da aba ativa,
#    para a troca de abas parecer mais fluida (sem depender de JS).
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

from tema import CORES, GRADIENTE_AVATAR, FONTE, FONTE_GOOGLE_IMPORT

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


# CSS com marcadores — os valores reais vêm de tema.CORES (ver
# _montar_css() logo abaixo). Isso evita ter que escapar chaves {}
# de f-string dentro de um bloco de CSS gigante.
_CSS_TEMPLATE = """
<style>
@import url('__FONTE_IMPORT__');

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], .stMarkdown p {
    font-family: __FONTE__ !important;
}

.stApp {
    background: linear-gradient(180deg, __FUNDO_1__ 0%, __FUNDO_2__ 100%) !important;
    color: __TEXTO__ !important;
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
    background: __CARD_2__ !important;
    border-bottom: 2px solid __BORDA_FORTE__ !important;
    height: 3rem !important;
}
header[data-testid="stHeader"] * { color: __TEXTO_MUTED2__ !important; }
[data-testid="stToolbar"] { color: __TEXTO_MUTED2__ !important; }

/* Sidebar removida do fluxo do app — caso o Streamlit ainda
   renderize o botão de colapsar, escondemos por segurança. */
[data-testid="collapsedControl"] { display: none !important; }

h1, h2, h3, h4, h5 {
    color: __TEXTO__ !important;
    font-family: __FONTE__ !important;
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
.pa-header-title { font-size: 1.05rem; font-weight: 800; color: __TEXTO__; line-height: 1.15; }
.pa-header-sub   { font-size: 0.72rem; font-weight: 700; color: __PRIMARIA_ALT__;
    text-transform: uppercase; letter-spacing: 0.07em; margin-top: 1px; }
@media (min-width: 900px) {
    .pa-header-title { font-size: 1.35rem; }
}
.pa-header-user {
    display: flex; align-items: center; gap: 8px;
    background: __CARD_1__; border: 1px solid __BORDA__; border-radius: 999px;
    padding: 5px 8px 5px 6px; flex: 0 0 auto;
}
.pa-avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: __GRADIENTE_AVATAR__;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 0.78rem; color: __TEXTO__; flex-shrink: 0;
}
.pa-header-user-name { font-size: 0.8rem; font-weight: 700; color: __TEXTO__; line-height: 1.1; }
.pa-header-user-role { font-size: 0.63rem; color: __TEXTO_MUTED__; text-transform: uppercase; letter-spacing: 0.05em; }

/* ---- Barra de filtros dentro da página (substitui a sidebar) ---- */
.pa-filtros {
    background: __CARD_1__; border: 1px solid __BORDA__; border-radius: 14px;
    padding: 0.9rem 1rem; margin-bottom: 1rem;
    box-shadow: 0 2px 6px rgba(30,70,120,0.06);
}
.pa-filtros-label {
    font-size: 0.68rem; font-weight: 800; color: __TEXTO_MUTED__;
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;
}
.mes-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: __PRIMARIA_CLARA__; border: 1px solid __BORDA_FORTE__; border-radius: 999px;
    padding: 5px 14px; font-size: 0.75rem; font-weight: 700; color: __PRIMARIA_ESCURA__;
}
.mes-badge-historico {
    display: inline-flex; align-items: center; gap: 6px;
    background: __PRIMARIA_CLARA__; border: 1px solid __BORDA_FORTE__; border-radius: 999px;
    padding: 5px 14px; font-size: 0.75rem; font-weight: 700; color: __TEXTO_MUTED2__;
}
.mes-dot { width: 7px; height: 7px; border-radius: 50%; background: __PRIMARIA__; display: inline-block; }

/* ---- Tabs: pílulas claras, quebram linha no mobile ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 4px; flex-wrap: wrap !important; row-gap: 6px;
    border-bottom: 1px solid __BORDA__ !important;
}
[data-testid="stTabs"] [data-testid="stTab"] {
    color: __TAB_INATIVA__ !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    background: transparent !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 12px !important;
}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
    color: __TEXTO__ !important;
    background: __PRIMARIA_CLARA__ !important;
    border-bottom: 2px solid __PRIMARIA__ !important;
}
@media (max-width: 640px) {
    [data-testid="stTabs"] [data-testid="stTab"] {
        font-size: 0.74rem !important; padding: 6px 9px !important;
    }
}

/* ---- CORREÇÃO (v6.2): isolar painel da aba ativa -------------------
   O Streamlit marca o painel de cada aba inativa com o atributo HTML
   nativo "hidden" (ex: <div data-baseweb="tab-panel" hidden>...</div>).
   Isso normalmente já basta para escondê-lo, mas como este arquivo usa
   !important em quase tudo, um conflito de prioridade entre o CSS
   customizado e o próprio Streamlit pode fazer o painel "escondido"
   continuar visível na tela ao lado do painel ativo.
   As regras abaixo eliminam essa ambiguidade: por padrão TODO painel
   de aba fica oculto; só o painel que NÃO tiver o atributo "hidden"
   (ou seja, a aba selecionada no momento) é exibido. Isso garante que
   apenas o conteúdo da aba em foco apareça na tela, sempre. */
[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    display: none !important;
}
[data-testid="stTabs"] [data-baseweb="tab-panel"]:not([hidden]) {
    display: block !important;
    animation: pa-fade-in 0.18s ease;
}
@keyframes pa-fade-in {
    from { opacity: 0; transform: translateY(2px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ---- Cards & Metrics ---- */
.pa-card, .pa-metric {
    background: linear-gradient(180deg, __CARD_1__ 0%, __CARD_2__ 100%) !important;
    border: 1px solid __BORDA__ !important;
    border-top: 3px solid __PRIMARIA__ !important;
    border-radius: 14px !important;
    padding: 1.1rem !important;
    margin-bottom: 0.8rem !important;
    box-shadow: 0 2px 6px rgba(30,70,120,0.07), 0 1px 2px rgba(30,70,120,0.10);
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.pa-card:hover, .pa-metric:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 26px rgba(30,70,120,0.14), 0 3px 10px rgba(30,70,120,0.22);
    border-color: __PRIMARIA__ !important;
}
.pa-metric-value {
    font-size: 22px !important;
    font-weight: 800 !important;
    color: __TEXTO__ !important;
    letter-spacing: -0.01em !important;
}
.pa-metric-label {
    font-size: 10.5px !important;
    font-weight: 700 !important;
    color: __TEXTO_MUTED__ !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    margin-top: 2px !important;
}
.pa-card-header {
    font-size: 0.92rem !important;
    font-weight: 700 !important;
    color: __TEXTO__ !important;
    margin-bottom: 4px !important;
}
.pa-card-sub {
    font-size: 0.78rem !important;
    color: #6B6B6B !important;
    font-weight: 500 !important;
}

/* ---- Painéis de aviso / info claros ---- */
.pa-aviso-sucesso {
    background: __SUCESSO_BG__; border: 1px solid __SUCESSO_BORDA__; border-radius: 10px;
    padding: 10px 14px; color: __SUCESSO_TEXTO__; font-size: 0.85rem;
}
.pa-aviso-atencao {
    background: __ATENCAO_BG__; border: 1px solid __ATENCAO_BORDA__; border-radius: 10px;
    padding: 10px 14px; color: __ATENCAO__; font-size: 0.85rem;
}
.pa-aviso-erro {
    background: __ERRO_BG__; border: 1px solid __ERRO_BORDA__; border-radius: 10px;
    padding: 10px 14px; color: __ERRO_TEXTO__; font-size: 0.85rem;
}
.pa-aviso-neutro {
    background: __NEUTRO_BG__; border: 1px solid __NEUTRO_BORDA__; border-radius: 10px;
    padding: 10px 14px; color: __NEUTRO__; font-size: 0.85rem;
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] > div > div {
    background: __CARD_1__ !important;
    border: 1px solid #E8E8E8 !important;
    color: __TEXTO__ !important;
    border-radius: 8px !important;
}

.stButton > button {
    background: transparent !important;
    color: __PRIMARIA_ALT__ !important;
    border: 1.5px solid __PRIMARIA__ !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
button[kind="primary"], .stButton [kind="primary"] > button {
    background: __PRIMARIA__ !important;
    color: __CARD_1__ !important;
    border: none !important;
}

/* ---- Tabela de Assistência ---- */
.assist-table {
    width: 100%;
    border-collapse: collapse;
    font-family: __FONTE__;
    font-size: 0.8rem;
}
.assist-table th {
    background: __PRIMARIA_CLARA__;
    color: __TEXTO_MUTED2__;
    padding: 8px 10px;
    text-align: center;
    font-weight: 700;
    font-size: 0.74rem;
    border: 1px solid __BORDA__;
}
.assist-table th.col-mes {
    background: __TABELA_HEADER__;
    text-align: left;
}
.assist-table td {
    padding: 7px 10px;
    border: 1px solid __BORDA__;
    text-align: center;
    background: __CARD_1__;
    color: __TEXTO__;
}
.assist-table td.col-mes {
    text-align: left;
    font-weight: 500;
    background: __CARD_2_CLARO__;
}
.assist-table tr.row-total td {
    background: __PRIMARIA_CLARA__;
    font-weight: 700;
    border-top: 2px solid __PRIMARIA__;
}
.assist-table .ano-header {
    background: __PRIMARIA__;
    color: __CARD_1__;
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
"""


def _montar_css() -> str:
    """Substitui os marcadores __X__ do template pelos valores de tema.CORES."""
    substituicoes = {
        "__FONTE_IMPORT__":     FONTE_GOOGLE_IMPORT,
        "__FONTE__":            FONTE,
        "__FUNDO_1__":          CORES["fundo_pagina_1"],
        "__FUNDO_2__":          CORES["fundo_pagina_2"],
        "__TEXTO__":            CORES["texto_principal"],
        "__TEXTO_MUTED__":      CORES["texto_muted"],
        "__TEXTO_MUTED2__":     CORES["texto_muted2"],
        "__CARD_1__":           CORES["fundo_card_1"],
        "__CARD_2__":           CORES["fundo_card_2"],
        "__CARD_2_CLARO__":     CORES["fundo_card_2"],
        "__BORDA__":            CORES["primaria_borda"],
        "__BORDA_FORTE__":      CORES["primaria_borda_forte"],
        "__PRIMARIA__":         CORES["primaria"],
        "__PRIMARIA_ESCURA__":  CORES["primaria_escura"],
        "__PRIMARIA_CLARA__":   CORES["primaria_clara"],
        "__PRIMARIA_ALT__":     CORES["texto_muted2"],
        "__TAB_INATIVA__":      CORES["texto_muted"],
        "__TABELA_HEADER__":    CORES["primaria_borda_forte"],
        "__GRADIENTE_AVATAR__": GRADIENTE_AVATAR,
        "__SUCESSO_BG__":       CORES["sucesso_bg"],
        "__SUCESSO_BORDA__":    CORES["sucesso_borda"],
        "__SUCESSO_TEXTO__":    CORES["sucesso"],
        "__ATENCAO_BG__":       CORES["atencao_bg"],
        "__ATENCAO_BORDA__":    CORES["atencao_borda"],
        "__ATENCAO__":          CORES["atencao"],
        "__ERRO_BG__":          CORES["erro_bg"],
        "__ERRO_BORDA__":       CORES["erro_borda"],
        "__ERRO_TEXTO__":       CORES["erro"],
        "__NEUTRO_BG__":        CORES["neutro_bg"],
        "__NEUTRO_BORDA__":     CORES["neutro_borda"],
        "__NEUTRO__":           CORES["neutro"],
    }
    css = _CSS_TEMPLATE
    for marcador, valor in substituicoes.items():
        css = css.replace(marcador, valor)
    return css


def aplicar_estilo():
    st.markdown(_montar_css(), unsafe_allow_html=True)
