import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
import base64
from datetime import datetime, date
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Parque Aliança · Gestão",
    layout="wide",
    page_icon="⛪",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# ESTILIZAÇÃO GLOBAL — 
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset e Fonte Global ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], .stMarkdown p {
    font-family: 'Inter', sans-serif !important;
}

/* ── Fundo do App (Light Theme) ── */
.stApp {
    background: #F4F4F4 !important;
    color: #1A1A1A !important;
}
.main .block-container {
    padding: 1.5rem 2.5rem 3rem !important;
    max-width: 1400px;
}

/* ── CORREÇÃO DA BARRA LATERAL (image_95b61e.png) ── */
[data-testid="stSidebar"] {
    background: #111010 !important;
    border-right: 1px solid #222222 !important;
}

/* Força todos os textos gerais e labels da sidebar a ficarem claros */
[data-testid="stSidebar"] , 
[data-testid="stSidebar"] p, 
[data-testid="stSidebar"] label, 
[data-testid="stSidebar"] span {
    color: #C5C5C5 !important;
}

/* Títulos principais dentro da Sidebar */
[data-testid="stSidebar"] h1, 
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3 {
    color: #FFFFFF !important;
}

/* Garante que os números e textos DENTRO dos cards brancos continuem escuros */
[data-testid="stSidebar"] .pa-card *, 
[data-testid="stSidebar"] .pa-metric * {
    color: #1A1A1A !important;
}
[data-testid="stSidebar"] .pa-metric-label {
    color: #888888 !important;
}

/* Navegação ativa/Selectbox na Sidebar */
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: #1C1C1C !important;
    border: 1px solid #333333 !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
}

/* ── Títulos ── */
h1, h2, h3, h4, h5 { 
    color: #1A1A1A !important; 
    font-family: 'Inter', sans-serif !important;
}
h1 { font-size: 1.9rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
h2 { font-weight: 600 !important; font-size: 1.3rem !important; }

/* ── Tabs (Abas) ── */
[data-testid="stTabs"] [data-testid="stTab"] {
    color: #888888 !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
    color: #C9A227 !important;
    border-bottom: 2px solid #C9A227 !important;
}

/* ── Cards Customizados ── */
.pa-card, .pa-metric {
    background: #FFFFFF !important;
    border: 1px solid #EDEDED !important;
    border-radius: 14px !important;
    padding: 1.2rem !important;
    margin-bottom: 0.8rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    transition: transform 0.2s, box-shadow 0.2s;
}
.pa-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.pa-metric-value {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #1A1A1A !important;
}

/* ── Inputs e Campos de Texto ── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] > div > div {
    background: #FFFFFF !important;
    border: 1px solid #E8E8E8 !important;
    color: #1A1A1A !important;
    border-radius: 8px !important;
}

/* ── Botões ── */
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
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════
_AUTH_USERS = {"wendley": "Qmerd@10"}

def tela_login():
    # Injeta um background escuro temporário apenas na tela de login
    st.markdown("""
    <style>
    .stApp { background: #111111 !important; }
    </style>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 1.2, 1])
    with col_center:
        # CORREÇÃO DA IDENTIDADE E DO CONTRASTE (image_95b6d7.png)
        st.markdown("""
        <div style="background: #1C1C1C; border: 1px solid #2A2A2A; border-radius: 16px; padding: 2.5rem 2rem; margin-top: 12vh; text-align: center;">
          <div style="display: flex; justify-content: center; margin-bottom: 1.25rem;">
            <div style="background: #C9A227; border-radius: 12px; width: 54px; height: 54px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 20px; color: #111;">
              PA
            </div>
          </div>
          <h2 style="color: #FFFFFF !important; font-size: 22px; font-weight: 600; margin-bottom: 6px;">Portal de Relatórios</h2>
          <p style="color: #AAAAAA !important; font-size: 13px; margin-bottom: 1.5rem;">Congregação Parque Aliança – 72249</p>
        </div>
        """, unsafe_allow_html=True)

        # Inputs do Streamlit colocados logo abaixo
        with st.container():
            user = st.text_input("Usuário", placeholder="Digite seu usuário", label_visibility="collapsed", key="login_user")
            senha = st.text_input("Senha", placeholder="Digite sua senha", type="password", label_visibility="collapsed", key="login_pass")
            entrar = st.button("Acessar Portal", use_container_width=True, type="primary")

        if entrar:
            if _AUTH_USERS.get(user.lower().strip()) == senha:
                st.session_state["autenticado"] = True
                st.session_state["usuario_logado"] = user.strip().title()
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES PDF S-21
# ═══════════════════════════════════════════════════════════════════════════════
PDF_Y_OFFSET    = 0.0
PDF_NOME_Y      = 272.0
PDF_NOME_X      = 24.0
PDF_NASCI_Y     = 265.0
PDF_NASCI_X     = 48.0
PDF_BATISM_Y    = 258.0
PDF_BATISM_X    = 48.0
PDF_CARGO_Y     = 252.0
PDF_MASC_X      = 150.0
PDF_FEM_X       = 172.0
PDF_OVELHAS_X   = 150.0
PDF_UNGIDO_X    = 172.0
PDF_ANCIAO_X    = 9.5
PDF_SERVO_X     = 35.0
PDF_PREG_X      = 65.0
PDF_PESP_X      = 100.0
PDF_MISS_X      = 140.0
PDF_TEL_HEADER_Y = 232.0

_Y_MAP_BASE = {
    "SETEMBRO":  228.5, "OUTUBRO":   220.5, "NOVEMBRO":  212.5, "DEZEMBRO":  204.5,
    "JANEIRO":   196.5, "FEVEREIRO": 188.5, "MARÇO":     180.5, "ABRIL":     172.5,
    "MAIO":      164.5, "JUNHO":     156.5, "JULHO":     148.5, "AGOSTO":    140.5,
}

PDF_TOTAL_Y        = 131.5
PDF_COL_PARTICIP_X = 53.5
PDF_COL_ESTUDOS_X  = 80.5
PDF_COL_PIAUX_X    = 97.5
PDF_COL_HORAS_X    = 116.5
PDF_COL_OBS_X      = 133.0

_CARGO_X_MAP = {
    "Ancião":               PDF_ANCIAO_X,
    "Servo ministerial":    PDF_SERVO_X,
    "Pioneiro regular":     PDF_PREG_X,
    "Pioneiro especial":    PDF_PESP_X,
    "Missionário em campo": PDF_MISS_X,
}

_CARGOS_LISTA = [
    "Ancião", "Servo ministerial", "Pioneiro regular",
    "Pioneiro especial", "Missionário em campo"
]

_MESES_ORDEM = [
    "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL",
    "MAIO", "JUNHO", "JULHO", "AGOSTO"
]

categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]

meses_referencia_ordem = [
    "SETEMBRO 2024", "OUTUBRO 2024", "NOVEMBRO 2024", "DEZEMBRO 2024",
    "JANEIRO 2025", "FEVEREIRO 2025", "MARÇO 2025", "ABRIL 2025", "MAIO 2025",
    "JUNHO 2025", "JULHO 2025", "AGOSTO 2025",
    "SETEMBRO 2025", "OUTUBRO 2025", "NOVEMBRO 2025", "DEZEMBRO 2025",
    "JANEIRO 2026", "FEVEREIRO 2026", "MARÇO 2026", "ABRIL 2026", "MAIO 2026",
    "JUNHO 2026", "JULHO 2026", "AGOSTO 2026",
]


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════
def normalizar_texto(texto):
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


def obter_mes_vigente_str():
    """
    O mês inicia no dia 20 de cada mês:
    - Se hoje >= dia 20 → mês vigente é o mês atual
    - Se hoje < dia 20  → mês vigente é o mês anterior
    """
    meses = ["JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
             "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"]
    hoje = date.today()
    if hoje.day >= 20:
        return f"{meses[hoje.month - 1]} {hoje.year}"
    else:
        # mês anterior
        if hoje.month == 1:
            return f"DEZEMBRO {hoje.year - 1}"
        return f"{meses[hoje.month - 2]} {hoje.year}"


def cargos_para_lista(cargo_val):
    if not cargo_val:
        return []
    if isinstance(cargo_val, list):
        return [c for c in cargo_val if c]
    return [cargo_val] if cargo_val else []


def ordenar_df_por_mes(df_input):
    def chave_mes(mes_ref):
        partes = str(mes_ref).upper().split()
        nome_mes = partes[0] if partes else ""
        ano = int(partes[1]) if len(partes) > 1 else 0
        idx = _MESES_ORDEM.index(nome_mes) if nome_mes in _MESES_ORDEM else 99
        return (ano, idx)
    df_sorted = df_input.copy()
    df_sorted["_sort_key"] = df_sorted["mes_referencia"].apply(chave_mes)
    df_sorted = df_sorted.sort_values("_sort_key").drop(columns=["_sort_key"])
    return df_sorted


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE TRIAGEM APRIMORADO
# Lógica: extrai primeiro e segundo nome, busca match por componentes
# ═══════════════════════════════════════════════════════════════════════════════
def normalizar_nome_no_banco(nome_recebido, lista_membros):
    """
    Tenta identificar o membro digitado:
    1. Match exato normalizado
    2. O nome digitado é subconjunto de tokens de algum nome oficial
    3. Qualquer token do nome digitado coincide com o primeiro nome oficial
    4. Fuzzy SequenceMatcher >= 0.82
    """
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 2:
        return None

    tokens_entrada = set(entrada_norm.split())
    melhor_match, maior_score = None, 0.0

    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        tokens_oficial = oficial_norm.split()

        # 1. Exato
        if entrada_norm == oficial_norm:
            return nome_oficial

        # 2. Token único digitado bate com primeiro nome oficial
        if len(tokens_entrada) == 1:
            primeiro = tokens_oficial[0] if tokens_oficial else ""
            segundo  = tokens_oficial[1] if len(tokens_oficial) > 1 else ""
            if entrada_norm in (primeiro, segundo):
                return nome_oficial

        # 3. Todos tokens digitados são subconjunto dos tokens oficiais
        if tokens_entrada and tokens_entrada.issubset(set(tokens_oficial)):
            score = len(tokens_entrada) / max(len(tokens_oficial), 1) + 0.5
            if score > maior_score:
                maior_score, melhor_match = score, nome_oficial
            continue

        # 4. Algum token coincide com primeiro nome
        primeiro_oficial = tokens_oficial[0] if tokens_oficial else ""
        for tok in tokens_entrada:
            if tok == primeiro_oficial and len(tok) >= 3:
                score = 0.88
                if score > maior_score:
                    maior_score, melhor_match = score, nome_oficial

        # 5. Fuzzy geral
        score_fuzzy = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score_fuzzy > maior_score:
            maior_score, melhor_match = score_fuzzy, nome_oficial

    return melhor_match if maior_score >= 0.82 else None


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE PDF
# ═══════════════════════════════════════════════════════════════════════════════
def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows, membro_info=None):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado na pasta do app.")
        return None

    mi = membro_info or {}
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)

    can.setFont("Helvetica-Bold", 10)
    can.drawString(PDF_NOME_X * mm, PDF_NOME_Y * mm, str(nome_cabecalho).upper())

    data_nasc = str(mi.get("data_nascimento", "")).strip()
    if data_nasc:
        can.setFont("Helvetica", 9)
        can.drawString(PDF_NASCI_X * mm, PDF_NASCI_Y * mm, data_nasc)

    data_bat = str(mi.get("data_batismo", "")).strip()
    if data_bat:
        can.setFont("Helvetica", 9)
        can.drawString(PDF_BATISM_X * mm, PDF_BATISM_Y * mm, data_bat)

    genero = mi.get("genero", "")
    can.setFont("Helvetica-Bold", 10)
    if genero == "Masculino":
        can.drawString(PDF_MASC_X * mm, PDF_NASCI_Y * mm, "X")
    elif genero == "Feminino":
        can.drawString(PDF_FEM_X * mm, PDF_NASCI_Y * mm, "X")

    classe = mi.get("classe", "")
    if classe == "Outras ovelhas":
        can.drawString(PDF_OVELHAS_X * mm, PDF_BATISM_Y * mm, "X")
    elif classe == "Ungido":
        can.drawString(PDF_UNGIDO_X * mm, PDF_BATISM_Y * mm, "X")

    cargos = cargos_para_lista(mi.get("cargo", ""))
    can.setFont("Helvetica-Bold", 10)
    for cargo in cargos:
        if cargo in _CARGO_X_MAP:
            can.drawString(_CARGO_X_MAP[cargo] * mm, PDF_CARGO_Y * mm, "X")

    tel_emerg = str(mi.get("telefone_emergencia", "")).strip()
    if tel_emerg:
        can.setFont("Helvetica-Bold", 9)
        can.drawString(PDF_COL_OBS_X * mm, PDF_TEL_HEADER_Y * mm, f"Tel: {tel_emerg}"[:32])

    total_horas = 0
    total_estud = 0

    for _, row in dados_rows.iterrows():
        mes_key = str(row.get('mes_referencia', '')).split()[0].upper()
        y_base  = _Y_MAP_BASE.get(mes_key)
        if y_base is None:
            continue
        y_pos = (y_base + PDF_Y_OFFSET) * mm

        horas = int(row.get('horas', 0))
        estud = int(row.get('estudos_biblicos', 0))
        total_horas += horas
        total_estud += estud

        if horas > 0 or estud > 0:
            can.setFont("Helvetica-Bold", 10)
            can.drawCentredString(PDF_COL_PARTICIP_X * mm, y_pos, "X")

        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_ESTUDOS_X * mm, y_pos, str(estud))

        # 💡 AJUSTE AQUI: Identifica a categoria real aplicada a ESTE mês específico
        categoria_do_mes = str(row.get('cat_oficial', '')).upper()
        
        # Se for Pioneiro Auxiliar neste mês específico, marca o "X" na coluna correta
        if categoria_do_mes == "PIONEIRO AUXILIAR":
            can.drawCentredString(PDF_COL_PIAUX_X * mm, y_pos, "X")

        can.drawCentredString(PDF_COL_HORAS_X * mm, y_pos, str(horas))

        # 💡 AJUSTE AQUI: Regra da aba OBS para incluir o Pioneiro Auxiliar dinamicamente
        obs_normal = str(row.get('observacoes', ''))
        obs_normal = obs_normal if obs_normal.lower() not in ('nan', '', 'none') else ''
        
        # Concatena a informação caso o membro tenha atuado como auxiliar neste mês
        if categoria_do_mes == "PIONEIRO AUXILIAR":
            if obs_normal:
                obs_final = f"Pion. Auxiliar | {obs_normal}"
            else:
                obs_final = "Pioneiro Auxiliar"
        else:
            obs_final = obs_normal

        if obs_final:
            can.setFont("Helvetica", 8)
            can.drawString(PDF_COL_OBS_X * mm, y_pos, obs_final[:32])

        can.setFont("Helvetica-Bold", 10)

    if total_horas > 0:
        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_HORAS_X * mm, PDF_TOTAL_Y * mm, str(total_horas))
    if total_estud > 0:
        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_ESTUDOS_X * mm, PDF_TOTAL_Y * mm, str(total_estud))

    can.save()
    packet.seek(0)

    reader_original = PdfReader(open(path_original, "rb"))
    writer = PdfWriter()
    pagina_base = reader_original.pages[0]
    pagina_base.merge_page(PdfReader(packet).pages[0])
    writer.add_page(pagina_base)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# BANCO DE DADOS — com cache para velocidade
# ═══════════════════════════════════════════════════════════════════════════════
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(
                credentials=creds, project="wendleydesenvolvimento")
        except Exception:
            return None
    return st.session_state.db


@st.cache_data(ttl=60, show_spinner=False)
def carregar_membros_cached():
    db = inicializar_db()
    if not db:
        return {}
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}


@st.cache_data(ttl=60, show_spinner=False)
def carregar_relatorios_cached():
    db = inicializar_db()
    if not db:
        return []
    return [{"id": doc.id, **doc.to_dict()}
            for doc in db.collection("relatorios_parque_alianca").stream()]


def carregar_membros():
    return carregar_membros_cached()


def carregar_relatorios():
    return carregar_relatorios_cached()


def atualizar_membro(nome, categoria, novo=False, extra=None):
    db = inicializar_db()
    if db:
        dados = {"categoria": categoria, "nome_oficial": nome}
        if novo:
            dados["mes_inicio"] = obter_mes_vigente_str()
        if extra:
            dados.update({k: v for k, v in extra.items() if v is not None})
        db.collection("membros_v2").document(nome).set(dados, merge=True)
        carregar_membros_cached.clear()


def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db:
        # 1. Apaga do banco de dados do Firestore
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        
        # 2. Limpeza agressiva de Cache (Garante que o fantasma não volte)
        carregar_relatorios_cached.clear()
        carregar_membros_cached.clear()
        
        # 3. Força a atualização
        st.toast("🗑️ Relatório deletado permanentemente!")
        st.rerun()


def salvar_baixa_manual(nome, mes, horas, estudos):
    db = inicializar_db()
    if db:
        novo_doc = {
            "nome": nome, "mes_referencia": mes, "horas": horas,
            "estudos_biblicos": estudos, "timestamp": firestore.SERVER_TIMESTAMP
        }
        db.collection("relatorios_parque_alianca").add(novo_doc)
        carregar_relatorios_cached.clear()
        st.success(f"✅ Relatório de {nome} adicionado!")
        st.rerun()


# ─── ANÚNCIOS ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def carregar_anuncios_cached():
    db = inicializar_db()
    if not db:
        return []
    try:
        docs = (db.collection("anuncios")
                  .order_by("data_postagem", direction=firestore.Query.DESCENDING)
                  .stream())
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception:
        return []


def carregar_anuncios():
    return carregar_anuncios_cached()


def salvar_anuncio(dados):
    db = inicializar_db()
    if not db:
        return False
    dados["data_postagem"] = firestore.SERVER_TIMESTAMP
    db.collection("anuncios").add(dados)
    carregar_anuncios_cached.clear()
    return True


def deletar_anuncio(anuncio_id):
    db = inicializar_db()
    if db:
        db.collection("anuncios").document(anuncio_id).delete()
        carregar_anuncios_cached.clear()
        st.toast("✅ Anúncio deletado!")
        st.rerun()


# ─── GERADOR DE HTML DE AGENDA ─────────────────────────────────────────────────
def gerar_html_agenda(d):
    C_CANT  = "#1a78b4"
    C_TES   = "#1a3566"
    C_TES_I = "#1a5fa8"
    C_MIN   = "#8a6200"
    C_MIN_I = "#a07800"
    C_NVC   = "#cc0000"
    C_NVC_I = "#1a5fa8"

    def row(num, titulo, duracao, bg, cor_item):
        if not str(titulo).strip():
            return ""
        dur = (f'<br><span style="font-size:12px;color:#888;margin-left:4px;">({duracao})</span>'
               if str(duracao).strip() else "")
        return (f'<div style="padding:6px 14px;background:{bg};border-bottom:1px solid #e8e8e8;">'
                f'<span style="color:{cor_item};font-weight:bold;">{num}. {titulo}</span>{dur}'
                f'</div>')

    def sec_header(texto, bg):
        return (f'<div style="background:{bg};color:white;padding:9px 14px;'
                f'font-weight:bold;font-size:14.5px;letter-spacing:0.3px;">{texto}</div>')

    html = ('<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;'
            'border:1px solid #ccc;border-radius:10px;overflow:hidden;'
            'box-shadow:0 2px 8px rgba(0,0,0,0.12);margin:auto;">')
    html += f'<div style="padding:12px 14px 8px;background:#ffffff;">'
    html += f'<div style="font-size:19px;font-weight:bold;color:#111;">{d.get("data_texto","")}</div>'
    if d.get("escritura"):
        html += f'<div style="color:{C_CANT};font-size:13px;font-weight:bold;margin-top:2px;">{d["escritura"]}</div>'
    html += '</div>'
    html += '<hr style="margin:0;border:0;border-top:1px solid #ddd;">'

    if d.get("cantico_abertura"):
        html += (f'<div style="padding:7px 14px;font-size:13px;background:#fff;">'
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_abertura"]}</span>'
                 f' e oração | <strong>Comentários iniciais</strong> (1 min)</div>')

    html += '<div style="margin-top:8px;">'
    html += sec_header("TESOUROS DA PALAVRA DE DEUS", C_TES)
    for it in d.get("tesouros", []):
        html += row(it["num"], it["titulo"], it.get("duracao", ""), "#f0f4ff", C_TES_I)
    html += '</div>'

    html += '<div style="margin-top:8px;">'
    html += sec_header("FAÇA SEU MELHOR NO MINISTÉRIO", C_MIN)
    for it in d.get("ministerio", []):
        html += row(it["num"], it["titulo"], it.get("duracao", ""), "#fffcf0", C_MIN_I)
    html += '</div>'

    html += '<div style="margin-top:8px;">'
    html += sec_header("NOSSA VIDA CRISTÃ", C_NVC)
    if d.get("cantico_meio"):
        html += (f'<div style="padding:6px 14px;background:#fff5f5;border-bottom:1px solid #e8e8e8;">'
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_meio"]}</span></div>')
    for it in d.get("vida_crista", []):
        html += row(it["num"], it["titulo"], it.get("duracao", ""), "#fff5f5", C_NVC_I)
    html += '</div>'

    if d.get("cantico_final"):
        html += (f'<hr style="margin:0;border:0;border-top:1px solid #ddd;">'
                 f'<div style="padding:9px 14px;font-size:13px;background:#fff;">'
                 f'<strong>Comentários finais</strong> (3 min) | '
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_final"]}</span>'
                 f' e oração</div>')

    html += '</div>'
    return html


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESSAMENTO DO DATAFRAME — validação de relatórios
# Regra 8: categoria do membro é a FONTE DA VERDADE (com exceção mensal)
# ═══════════════════════════════════════════════════════════════════════════════
def processar_dataframe(relatorios_brutos, membros_db):
    if not relatorios_brutos:
        return pd.DataFrame()

    df = pd.DataFrame(relatorios_brutos)
    df['horas'] = pd.to_numeric(df.get('horas', 0), errors='coerce').fillna(0)
    df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
    df['mes_referencia'] = df['mes_referencia'].str.upper()

    lista_nomes = list(membros_db.keys())

    def validar_envio(row):
        nome_oficial = normalizar_nome_no_banco(row['nome'], lista_nomes)
        if nome_oficial:
            dados_m = membros_db[nome_oficial]
            
            # 💡 NOVO: Verifica se o relatório tem uma categoria ESPECÍFICA salva para este mês
            cat_mes = row.get('categoria_mes')
            
            # Se houver uma exceção salva e ela for válida, usa ela
            if pd.notna(cat_mes) and cat_mes in categorias_lista:
                cat_final = cat_mes
            else:
                # Se não houver exceção, obedece à Fonte da Verdade (cadastro global)
                cat_final = dados_m.get('categoria', 'PUBLICADOR')
                if cat_final not in categorias_lista:
                    cat_final = 'PUBLICADOR'
                    
            return pd.Series([nome_oficial, cat_final, "IDENTIFICADO"])
        return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: gerar ZIP de pendentes por categoria
# ═══════════════════════════════════════════════════════════════════════════════
def gerar_zip_pendentes(pendentes, mes, membros_db, df_todos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for nome in pendentes:
            mi = membros_db.get(nome, {})
            df_hist = df_todos[
                (df_todos['nome_oficial'] == nome) &
                (df_todos['status_validacao'] == "IDENTIFICADO")
            ]
            df_hist = ordenar_df_por_mes(df_hist) if not df_hist.empty else pd.DataFrame()
            pdf = gerar_pdf_padrao_s21(nome, mi.get('categoria', 'PUBLICADOR'),
                                       df_hist, membro_info=mi)
            if pdf:
                nome_arq = "".join(c for c in nome if c.isalnum() or c in (' ', '_', '-')
                                   ).strip().replace(' ', '_')
                zf.writestr(f"Pendente_{nome_arq}.pdf", pdf)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# APP PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    # ── Autenticação ──────────────────────────────────────────────────────────
    if not st.session_state.get("autenticado"):
        tela_login()
        st.stop()

    # ── Carregar dados (com cache) ─────────────────────────────────────────────
    membros_db        = carregar_membros()
    relatorios_brutos = carregar_relatorios()

    df = processar_dataframe(relatorios_brutos, membros_db)

    # ── Mês vigente (dia 20 = início do mês) ──────────────────────────────────
    mes_vigente = obter_mes_vigente_str()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-brand">
            <div style="font-size:2rem;margin-bottom:4px;">⛪</div>
            <div class="sidebar-brand-title">Parque Aliança</div>
            <div class="sidebar-brand-sub">Gestão · v5.0</div>
        </div>
        <hr class="sidebar-divider">
        """, unsafe_allow_html=True)

        st.markdown('<p style="color:#6b7280;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;margin-bottom:4px;">Mês de Análise</p>', unsafe_allow_html=True)

        meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else [mes_vigente]

        # Sempre tenta selecionar o mês vigente como padrão
        idx_default = len(meses_disponiveis) - 1
        if mes_vigente in meses_disponiveis:
            idx_default = meses_disponiveis.index(mes_vigente)

        mes_sel = st.selectbox(
            "Mês",
            meses_disponiveis,
            index=idx_default,
            label_visibility="collapsed"
        )

        # Badge do mês vigente
        eh_vigente = (mes_sel == mes_vigente)
        if eh_vigente:
            st.markdown(f"""
            <div class="mes-badge">
                <span class="mes-dot"></span>
                MÊS VIGENTE
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="display:inline-flex;align-items:center;gap:6px;
                background:#1f2937;border:1px solid #374151;border-radius:999px;
                padding:5px 14px;font-size:0.75rem;font-weight:700;color:#6b7280;">
                📅 HISTÓRICO
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        # Totais rápidos
        if not df.empty:
            df_mes_side = df[df['mes_referencia'] == mes_sel]
            df_id_side  = df_mes_side[df_mes_side['status_validacao'] == "IDENTIFICADO"]
            df_tri_side = df_mes_side[df_mes_side['status_validacao'] == "TRIAGEM"]

            st.markdown(f"""
            <div style="display:grid;gap:6px;">
              <div class="pa-metric">
                <div class="pa-metric-value">{len(df_id_side)}</div>
                <div class="pa-metric-label">Identificados</div>
              </div>
              <div class="pa-metric">
                <div class="pa-metric-value" style="color:#ef4444">{len(df_tri_side)}</div>
                <div class="pa-metric-label">Em triagem</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
        usuario = st.session_state.get("usuario_logado", "Admin")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
          <div style="width:32px;height:32px;border-radius:50%;
            background:linear-gradient(135deg,#d97706,#f59e0b);
            display:flex;align-items:center;justify-content:center;
            font-weight:800;font-size:0.85rem;color:#000;">{usuario[0].upper()}</div>
          <div>
            <div style="font-weight:700;font-size:0.82rem;color:#f9fafb;">{usuario}</div>
            <div style="font-size:0.68rem;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Administrador</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Sair", use_container_width=True):
            for k in ["autenticado", "usuario_logado"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Header da página ───────────────────────────────────────────────────────
    col_title, col_mes = st.columns([3, 1])
    with col_title:
        st.markdown("# ⛪ Parque Aliança")
        st.markdown('<p style="color:#6b7280;font-size:0.85rem;margin-top:-8px;">Sistema de Gestão · Relatórios & Publicadores</p>', unsafe_allow_html=True)
    with col_mes:
        st.markdown(f"""
        <div style="text-align:right;margin-top:12px;">
            <div class="mes-badge">
                <span class="mes-dot"></span>
                {mes_vigente}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Tabs principais ────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📋  RELATÓRIOS",
        "⚠️  TRIAGEM",
        "📈  CONSOLIDADO",
        "📢  ANÚNCIOS",
        "⚙️  CONFIGURAÇÃO",
    ])

    df_mes   = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
    df_ok    = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
    entregaram = set(df_ok['nome_oficial'].unique()) if not df_ok.empty else set()

    # ════════════════════════════════════════════════════════════════════════════
    # ABA 0 — RELATÓRIOS
    # ════════════════════════════════════════════════════════════════════════════
    with tabs[0]:
        st.markdown(f"### 📋 Relatórios de {mes_sel}")

        sub_rel = st.tabs(["👤 PUBLICADOR", "🌟 P. AUXILIAR", "⭐ P. REGULAR", "⏳ PENDÊNCIAS"])

        for i, cat in enumerate(categorias_lista):
            with sub_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()

                if df_cat.empty:
                    st.info(f"Nenhum envio de {cat} em {mes_sel}.")
                else:
                    # Métricas
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"""
                        <div class="pa-metric">
                          <div class="pa-metric-value">{len(df_cat)}</div>
                          <div class="pa-metric-label">Relatórios</div>
                        </div>""", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
                        <div class="pa-metric">
                          <div class="pa-metric-value">{int(df_cat['horas'].sum())}h</div>
                          <div class="pa-metric-label">Total de Horas</div>
                        </div>""", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"""
                        <div class="pa-metric">
                          <div class="pa-metric-value">{int(df_cat['estudos_biblicos'].sum())}</div>
                          <div class="pa-metric-label">Estudos Bíblicos</div>
                        </div>""", unsafe_allow_html=True)

                    st.markdown("")
                    # Cards dos publicadores em ordem alfabética
                    df_cat_sorted = df_cat.sort_values('nome_oficial')
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat_sorted.iterrows()):
                        with cols[idx % 4]:
                            st.markdown(
                                f'<div class="pa-card">'
                                f'<div class="pa-card-header">{r["nome_oficial"]}</div>'
                                f'<div class="pa-card-sub">⏱ {int(r["horas"])}h &nbsp;·&nbsp; 📚 {int(r["estudos_biblicos"])}</div>'
                                f'</div>',
                                unsafe_allow_html=True)

        # ── Pendências ────────────────────────────────────────────────────────
        with sub_rel[3]:
            idx_mes_sel = (meses_referencia_ordem.index(mes_sel)
                           if mes_sel in meses_referencia_ordem else 99)

            for cat in categorias_lista:
                pendentes = []
                for n, d_m in membros_db.items():
                    inicio    = d_m.get('mes_inicio', 'SETEMBRO 2025')
                    idx_ini   = (meses_referencia_ordem.index(inicio)
                                 if inicio in meses_referencia_ordem else 0)
                    if (d_m.get('categoria') == cat
                            and n not in entregaram
                            and idx_mes_sel >= idx_ini):
                        pendentes.append(n)

                pendentes = sorted(pendentes)  # ordem alfabética

                if not pendentes:
                    continue

                with st.expander(f"{'👤' if cat=='PUBLICADOR' else '🌟' if 'AUXILIAR' in cat else '⭐'} {cat} — {len(pendentes)} pendente(s)", expanded=False):

                    # Botão BAIXAR TODOS (item 7)
                    col_btn_baixa, _ = st.columns([2, 3])
                    with col_btn_baixa:
                        if st.button(f"✔ Dar Baixa em Todos ({len(pendentes)})", key=f"baixa_all_{cat}_{mes_sel}", type="primary"):
                            db = inicializar_db()
                            if db:
                                batch = db.batch()
                                for p in pendentes:
                                    # Cria uma nova referência vazia no Firestore
                                    doc_ref = db.collection("relatorios_parque_alianca").document()
                                    batch.set(doc_ref, {
                                        "nome": p, 
                                        "mes_referencia": mes_sel, 
                                        "horas": 0,
                                        "estudos_biblicos": 0, 
                                        "timestamp": firestore.SERVER_TIMESTAMP
                                    })
                                
                                batch.commit() # Dispara todas as baixas de uma vez
                                carregar_relatorios_cached.clear() # Limpa o cache
                                st.success(f"✅ Baixa realizada para {len(pendentes)} publicadores(as)!")
                                st.rerun()

                    st.markdown("---")
                    for p in pendentes:
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                        c1.markdown(f"**{p}**")
                        h_manual = c2.number_input("H", min_value=0, step=1, key=f"h_man_{p}_{mes_sel}")
                        e_manual = c3.number_input("E", min_value=0, step=1, key=f"e_man_{p}_{mes_sel}")
                        if c4.button("✔ Dar Baixa", key=f"btn_man_{p}_{mes_sel}"):
                            salvar_baixa_manual(p, mes_sel, h_manual, e_manual)

    # ════════════════════════════════════════════════════════════════════════════
    # ABA 1 — TRIAGEM
    # ════════════════════════════════════════════════════════════════════════════
    with tabs[1]:
        df_triagem = (df_mes[df_mes['status_validacao'] == "TRIAGEM"]
                      if not df_mes.empty else pd.DataFrame())

        if df_triagem.empty:
            st.markdown("""
            <div style="text-align:center;padding:3rem 1rem;">
              <div style="font-size:3rem;margin-bottom:0.5rem;">✅</div>
              <div style="font-size:1.1rem;font-weight:700;color:#6ee7b7;">Tudo limpo!</div>
              <div style="color:#6b7280;font-size:0.85rem;margin-top:4px;">Nenhum relatório em triagem para este mês.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="margin-bottom:1.5rem;">
              <div style="font-size:0.75rem;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">
                ⚠️ Triagem — {len(df_triagem)} item(s)
              </div>
              <div style="color:#6b7280;font-size:0.82rem;">
                Estes relatórios precisam de validação manual. O sistema tentou associar automaticamente — confirme ou ajuste.
              </div>
            </div>
            """, unsafe_allow_html=True)

            nomes_db = sorted(list(membros_db.keys()))

            for _, row in df_triagem.iterrows():
                # Tenta sugestão automática
                sugestao = normalizar_nome_no_banco(row['nome'], nomes_db)
                idx_sug  = nomes_db.index(sugestao) + 1 if sugestao else 0
                conf_str = "Auto-sugerido" if sugestao else "Não reconhecido"
                badge_cls = "badge-warn" if sugestao else "badge-err"

                with st.container(border=True):
                    col_info, col_badge = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"""
                        <div style="margin-bottom:8px;">
                          <span style="font-weight:700;color:#f9fafb;font-size:0.95rem;">"{row['nome']}"</span>
                          <span style="color:#6b7280;font-size:0.8rem;margin-left:8px;">· {int(row['horas'])}h · {int(row.get('estudos_biblicos',0))} estudos</span>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_badge:
                        st.markdown(f'<span class="badge {badge_cls}">{conf_str}</span>', unsafe_allow_html=True)

                    if sugestao:
                        st.markdown(f"""
                        <div style="background:#1a1200;border:1px solid #92400e;border-radius:8px;
                            padding:6px 12px;margin-bottom:10px;font-size:0.8rem;color:#fbbf24;">
                            💡 Sugestão: <strong>{sugestao}</strong>
                        </div>
                        """, unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    vincular = c1.selectbox(
                        "Vincular a:",
                        ["-- Novo Membro --"] + nomes_db,
                        index=idx_sug,
                        key=f"v_{row['id']}"
                    )
                    cat_v = c2.selectbox("Categoria:", categorias_lista, key=f"c_{row['id']}")

                    col_confirm, col_del = st.columns([2, 1])
                    with col_confirm:
                        if st.button("✔ Confirmar Vinculação", key=f"b_{row['id']}", type="primary", use_container_width=True):
                            nome_final = row['nome'] if vincular == "-- Novo Membro --" else vincular
                            atualizar_membro(nome_final, cat_v, novo=(vincular == "-- Novo Membro --"))
                            inicializar_db().collection("relatorios_parque_alianca") \
                                .document(row['id']).update({"nome": nome_final})
                            carregar_relatorios_cached.clear()
                            st.rerun()
                    with col_del:
                        if st.button("🗑 Deletar", key=f"del_{r['id']}", use_container_width=True):
                            try:
                                # Chama a função que apaga diretamente da coleção global do Firestore
                                deletar_relatorio(r['id'])
                                
                                # Nota: A função deletar_relatorio já possui o 'carregar_relatorios_cached.clear()' 
                                # e o 'st.rerun()' embutidos nela, o que força a tela a redesenhar sem o registro sumido.
                            except Exception as e:
                                st.error(f"Erro crítico ao deletar o relatório: {e}")
    # ════════════════════════════════════════════════════════════════════════════
    # ABA 2 — CONSOLIDADO
    # ════════════════════════════════════════════════════════════════════════════
    with tabs[2]:
        c1_tab, c2_tab = st.tabs(["👤 INDIVIDUAL (HISTÓRICO)", "📊 POR CATEGORIA"])

        with c1_tab:
            membros_ord = sorted(list(membros_db.keys()))
            publicador  = st.selectbox("Publicador", membros_ord)

            st.markdown("---")
            st.markdown("#### 📦 Exportar Todos os Cartões S-21")
            st.caption("Gera um ZIP com o cartão histórico completo de **todos** os membros.")

            if st.button("⚙️ Preparar ZIP — Todos os Cartões", use_container_width=True):
                if df.empty:
                    st.warning("Nenhum relatório encontrado.")
                    st.session_state.pop("zip_todos_cartoes", None)
                else:
                    prog = st.progress(0, text="Iniciando...")
                    membros_lista = sorted(membros_db.keys())
                    buf_all = io.BytesIO()
                    count_ok = 0
                    total_m = len(membros_lista)

                    with zipfile.ZipFile(buf_all, "w", compression=zipfile.ZIP_DEFLATED) as zf_all:
                        for i, nome_m in enumerate(membros_lista):
                            prog.progress((i + 1) / total_m, text=f"{nome_m} ({i+1}/{total_m})")
                            df_hist_m = df[
                                (df['nome_oficial'] == nome_m) &
                                (df['status_validacao'] == "IDENTIFICADO")
                            ]
                            if df_hist_m.empty:
                                continue
                            df_hist_m = ordenar_df_por_mes(df_hist_m)
                            mi_m = membros_db.get(nome_m, {})
                            pdf_m = gerar_pdf_padrao_s21(
                                nome_m, mi_m.get('categoria', 'PUBLICADOR'),
                                df_hist_m, membro_info=mi_m
                            )
                            if pdf_m:
                                nome_arq = "".join(
                                    c for c in nome_m if c.isalnum() or c in (' ', '_', '-')
                                ).strip().replace(' ', '_')
                                zf_all.writestr(f"S21_{nome_arq}.pdf", pdf_m)
                                count_ok += 1

                    prog.empty()
                    if count_ok:
                        st.session_state["zip_todos_cartoes"] = buf_all.getvalue()
                        st.session_state["zip_todos_nome"] = f"S21_Todos_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                        st.session_state["zip_todos_count"] = count_ok
                        st.success(f"✅ {count_ok} cartões prontos!")
                    else:
                        st.warning("Nenhum PDF gerado.")
                        st.session_state.pop("zip_todos_cartoes", None)

            if "zip_todos_cartoes" in st.session_state:
                st.download_button(
                    f"📥 Baixar ZIP ({st.session_state.get('zip_todos_count','?')} cartões)",
                    data=st.session_state["zip_todos_cartoes"],
                    file_name=st.session_state.get("zip_todos_nome", "S21_Todos.zip"),
                    mime="application/zip",
                    use_container_width=True,
                    type="primary",
                )

            st.markdown("---")
            st.markdown("#### 👤 Cartão Individual")

            if publicador:
                df_hist = df[
                    (df['nome_oficial'] == publicador) &
                    (df['status_validacao'] == "IDENTIFICADO")
                ] if not df.empty else pd.DataFrame()

                if not df_hist.empty:
                    df_hist = ordenar_df_por_mes(df_hist)
                    st.dataframe(
                        df_hist[['mes_referencia', 'horas', 'estudos_biblicos']].rename(columns={
                            'mes_referencia': 'Mês',
                            'horas': 'Horas',
                            'estudos_biblicos': 'Estudos'
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )
                    pdf = gerar_pdf_padrao_s21(
                        publicador,
                        membros_db[publicador].get('categoria'),
                        df_hist,
                        membro_info=membros_db[publicador]
                    )
                    if pdf:
                        st.download_button(
                            "📥 Baixar Cartão S-21",
                            pdf,
                            f"S21_{publicador}.pdf",
                            use_container_width=True,
                        )
                else:
                    st.info("Nenhum relatório identificado para este publicador.")

        with c2_tab:
            cat_sel = st.selectbox("Categoria", categorias_lista)
            df_cons = df[
                (df['status_validacao'] == "IDENTIFICADO") &
                (df['cat_oficial'] == cat_sel)
            ] if not df.empty else pd.DataFrame()

            if not df_cons.empty:
                resumo = df_cons.groupby('mes_referencia').agg(
                    total_relatorios=('id', 'count'),
                    total_horas=('horas', 'sum'),
                    total_estudos=('estudos_biblicos', 'sum'),
                ).reset_index()

                # Ordena cronologicamente
                resumo_ord = ordenar_df_por_mes(resumo.rename(columns={'mes_referencia': 'mes_referencia'}))

                # Item 6: no mês vigente, observação com total de relatórios
                def obs_col(row):
                    if row['mes_referencia'] == mes_vigente:
                        return f"📌 {int(row['total_relatorios'])} relatórios entregues"
                    return ""

                resumo_ord['observacao'] = resumo_ord.apply(obs_col, axis=1)

                st.dataframe(
                    resumo_ord.rename(columns={
                        'mes_referencia': 'Mês',
                        'total_relatorios': 'Relatórios',
                        'total_horas': 'Total Horas',
                        'total_estudos': 'Total Estudos',
                        'observacao': 'Observação'
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

                pdf_c = gerar_pdf_padrao_s21(
                    f"CONSOLIDADO {cat_sel}",
                    cat_sel,
                    resumo_ord.rename(columns={
                        'total_horas': 'horas',
                        'total_estudos': 'estudos_biblicos'
                    })
                )
                if pdf_c:
                    st.download_button(
                        f"📥 Baixar Cartão Consolidado — {cat_sel}",
                        pdf_c,
                        f"S21_Consolidado_{cat_sel}.pdf",
                        use_container_width=True,
                    )
            else:
                st.info("Sem dados para esta categoria.")

    # ════════════════════════════════════════════════════════════════════════════
    # ABA 3 — ANÚNCIOS
    # ════════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        sub_an = st.tabs(["✏️ Nova Postagem", "🗂️ Gerenciar Postagens"])

        with sub_an[0]:
            tipo = st.radio(
                "Tipo",
                ["📝 Texto / Markdown", "🖼️ Imagem (JPEG/PNG)", "📅 Agenda de Reunião"],
                horizontal=True
            )

            if tipo == "📝 Texto / Markdown":
                titulo_txt  = st.text_input("Título (opcional)")
                conteudo_md = st.text_area("Conteúdo", height=200)
                if conteudo_md:
                    with st.expander("Pré-visualização"):
                        st.markdown(conteudo_md)
                if st.button("📤 Publicar", type="primary", use_container_width=True):
                    if conteudo_md.strip():
                        salvar_anuncio({"tipo": "texto", "titulo": titulo_txt or "Anúncio",
                                        "conteudo_html": conteudo_md, "renderizar_markdown": True})
                        st.success("✅ Publicado!")
                        st.rerun()
                    else:
                        st.error("Conteúdo vazio.")

            elif tipo == "🖼️ Imagem (JPEG/PNG)":
                titulo_img = st.text_input("Legenda (opcional)")
                arquivo    = st.file_uploader("Imagem", type=["jpg","jpeg","png"])
                if arquivo:
                    st.image(arquivo, use_column_width=True)
                    if st.button("📤 Publicar Imagem", type="primary", use_container_width=True):
                        img_bytes = arquivo.read()
                        mime  = "image/png" if arquivo.name.endswith(".png") else "image/jpeg"
                        b64   = base64.b64encode(img_bytes).decode("utf-8")
                        html_img = (f'<div style="text-align:center;padding:10px;">'
                                    f'<img src="data:{mime};base64,{b64}" '
                                    f'style="max-width:100%;border-radius:8px;" />'
                                    + (f'<p style="margin-top:8px;color:#555;">{titulo_img}</p>'
                                       if titulo_img else "") + '</div>')
                        salvar_anuncio({"tipo": "imagem", "titulo": titulo_img or arquivo.name,
                                        "conteudo_html": html_img, "renderizar_markdown": False})
                        st.success("✅ Imagem publicada!")
                        st.rerun()

            elif tipo == "📅 Agenda de Reunião":
                col_a, col_b = st.columns(2)
                data_texto = col_a.text_input("Período", placeholder="18-24 DE MAIO")
                escritura  = col_b.text_input("Escritura", placeholder="ISAÍAS 62-64")

                col_c, col_d, col_e = st.columns(3)
                cant_ab   = col_c.text_input("Cântico Abertura", placeholder="44")
                cant_meio = col_d.text_input("Cântico NVC",      placeholder="115")
                cant_fin  = col_e.text_input("Cântico Final",    placeholder="151")

                st.markdown("---")
                st.markdown('<div style="background:#1a3566;color:white;padding:7px 12px;border-radius:5px;font-weight:bold;margin-bottom:6px;">TESOUROS DA PALAVRA DE DEUS</div>', unsafe_allow_html=True)
                n_tes = st.number_input("Nº itens", 1, 6, 3, key="n_tes")
                tesouros = []
                for i in range(int(n_tes)):
                    c1, c2 = st.columns([4, 1])
                    t = c1.text_input(f"Item {i+1}", key=f"tes_t_{i}", label_visibility="collapsed", placeholder=f"Item {i+1}")
                    d_dur = c2.text_input("Dur.", key=f"tes_d_{i}", label_visibility="collapsed", placeholder="10 min")
                    tesouros.append({"num": i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                st.markdown('<div style="background:#8a6200;color:white;padding:7px 12px;border-radius:5px;font-weight:bold;margin-bottom:6px;">FAÇA SEU MELHOR NO MINISTÉRIO</div>', unsafe_allow_html=True)
                n_min = st.number_input("Nº itens", 1, 6, 3, key="n_min")
                ministerio = []
                base_min = int(n_tes)
                for i in range(int(n_min)):
                    c1, c2 = st.columns([4, 1])
                    t = c1.text_input(f"Item {base_min+i+1}", key=f"min_t_{i}", label_visibility="collapsed", placeholder=f"Item {base_min+i+1}")
                    d_dur = c2.text_input("Dur.", key=f"min_d_{i}", label_visibility="collapsed", placeholder="")
                    ministerio.append({"num": base_min + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                st.markdown('<div style="background:#cc0000;color:white;padding:7px 12px;border-radius:5px;font-weight:bold;margin-bottom:6px;">NOSSA VIDA CRISTÃ</div>', unsafe_allow_html=True)
                n_nvc = st.number_input("Nº itens", 1, 10, 2, key="n_nvc")
                vida_crista = []
                base_nvc = int(n_tes) + int(n_min)
                for i in range(int(n_nvc)):
                    c1, c2 = st.columns([4, 1])
                    t = c1.text_input(f"Item {base_nvc+i+1}", key=f"nvc_t_{i}", label_visibility="collapsed", placeholder=f"Item {base_nvc+i+1}")
                    d_dur = c2.text_input("Dur.", key=f"nvc_d_{i}", label_visibility="collapsed", placeholder="")
                    vida_crista.append({"num": base_nvc + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                agenda_dados = {
                    "data_texto": data_texto, "escritura": escritura,
                    "cantico_abertura": cant_ab, "cantico_meio": cant_meio,
                    "cantico_final": cant_fin,
                    "tesouros": tesouros, "ministerio": ministerio, "vida_crista": vida_crista,
                }
                col_prev, col_pub = st.columns(2)
                with col_prev:
                    if st.button("👁 Pré-visualizar", use_container_width=True):
                        st.markdown(gerar_html_agenda(agenda_dados), unsafe_allow_html=True)
                with col_pub:
                    if st.button("📤 Publicar Agenda", use_container_width=True, type="primary"):
                        if not data_texto.strip():
                            st.error("Informe o período.")
                        else:
                            salvar_anuncio({
                                "tipo": "agenda", "titulo": data_texto,
                                "conteudo_html": gerar_html_agenda(agenda_dados),
                                "renderizar_markdown": False,
                                "dados_agenda": agenda_dados,
                            })
                            st.success(f"✅ Agenda '{data_texto}' publicada!")
                            st.rerun()

        with sub_an[1]:
            anuncios = carregar_anuncios()
            if not anuncios:
                st.info("Nenhuma postagem encontrada.")
            else:
                st.caption(f"{len(anuncios)} postagem(ns) · mais recente primeiro")
                for a in anuncios:
                    tipo_icon = {"texto": "📝", "imagem": "🖼️", "agenda": "📅"}.get(a.get("tipo",""), "📌")
                    ts = a.get("data_postagem")
                    data_str = ts.strftime("%d/%m/%Y %H:%M") if hasattr(ts, "strftime") else "–"
                    with st.expander(f"{tipo_icon} {a.get('titulo','Sem título')}  ·  {data_str}"):
                        if a.get("renderizar_markdown"):
                            st.markdown(a.get("conteudo_html",""), unsafe_allow_html=False)
                        else:
                            st.markdown(a.get("conteudo_html",""), unsafe_allow_html=True)
                        st.markdown("---")
                        if st.button("🗑 Deletar", key=f"del_an_{a['id']}", type="secondary"):
                            deletar_anuncio(a["id"])

    # ════════════════════════════════════════════════════════════════════════════
    # ABA 4 — CONFIGURAÇÃO
    # ════════════════════════════════════════════════════════════════════════════
    with tabs[4]:
        sub_cfg = st.tabs(["✏️ EDITAR RELATÓRIOS", "👥 GERENCIAR MEMBROS", "➕ NOVO MEMBRO"])

        # ── Sub-aba 0: Editar Relatórios ──────────────────────────────────────
        with sub_cfg[0]:
            st.markdown(f"#### Relatórios Identificados — {mes_sel}")
            if not df.empty:
                df_ok_mes = df[
                    (df['mes_referencia'] == mes_sel) &
                    (df['status_validacao'] == "IDENTIFICADO")
                ]
                if df_ok_mes.empty:
                    st.info("Nenhum relatório identificado neste mês.")
                else:
                    for _, r in df_ok_mes.sort_values('nome_oficial').iterrows():
                        with st.expander(f"📝 {r['nome_oficial']} — {int(r['horas'])}h"):
                            ce1, ce2, ce3 = st.columns([2, 1, 1])
                            idx_cat = (categorias_lista.index(r['cat_oficial'])
                                       if r['cat_oficial'] in categorias_lista else 0)
                            nova_cat = ce1.selectbox("Categoria", categorias_lista,
                                                      index=idx_cat, key=f"e_c_{r['id']}")
                            novas_h  = ce2.number_input("Horas", value=int(r['horas']),
                                                         key=f"e_h_{r['id']}")
                            novos_e  = ce3.number_input("Estudos", value=int(r['estudos_biblicos']),
                                                         key=f"e_e_{r['id']}")
                            col_save, col_del = st.columns(2)
                            
                            with col_save:
                                if st.button("💾 Salvar", key=f"s_b_{r['id']}", type="primary", use_container_width=True):
                                    try:
                                        # Atualiza APENAS o relatório do mês corrente com a categoria de exceção
                                        inicializar_db().collection("relatorios_parque_alianca") \
                                            .document(r['id']).update({
                                                "horas": novas_h, 
                                                "estudos_biblicos": novos_e,
                                                "categoria_mes": nova_cat  # Salva a categoria exclusiva deste mês
                                            })
                                        
                                        # ❌ REMOVIDO: atualizar_membro(r['nome_oficial'], nova_cat) 
                                        # Isso garante que a Fonte da Verdade em 'membros_v2' permaneça intacta.
                            
                                        carregar_relatorios_cached.clear()
                                        st.toast("💾 Alterações salvas com sucesso para este mês!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar alterações: {e}")
                                        
                            # 🌟 LÓGICA DE EXCLUSÃO GLOBAL IMPLEMENTADA AQUI
                            with col_del:
                                with st.popover("🗑️ Deletar", use_container_width=True):
                                    st.error("Atenção! Ação irreversível.")
                                    st.write(f"Deseja apagar definitivamente o relatório de **{r['nome_oficial']}** deste mês?")
                                    
                                    # Botão de confirmação de exclusão
                                    if st.button("Sim, Excluir", key=f"conf_del_{r['id']}", type="primary", use_container_width=True):
                                        try:
                                            # MUDA AQUI: Em vez de .delete(), atualizamos o status para EXCLUIDO
                                            inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({
                                                "status_validacao": "EXCLUIDO"
                                            })
                                            
                                            # Limpa o cache para que o Streamlit atualize os dados na hora
                                            carregar_relatorios_cached.clear()
                                            
                                            # Dá o aviso de sucesso e recarrega a tela
                                            st.toast("🗑️ Relatório removido permanentemente do sistema!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro ao tentar deletar: {e}")

        # ── Sub-aba 1: GERENCIAR MEMBROS ──────────────────────────────────────
        with sub_cfg[1]:
            st.markdown("#### 👥 Gerenciar Membros")
            st.caption("Categoria aqui é a FONTE DA VERDADE para todos os relatórios.")

            _GENEROS = ["", "Masculino", "Feminino"]
            _CLASSES = ["", "Outras ovelhas", "Ungido"]
            _STATUS_OPCOES = ["Ativo", "Inativo"] # Opções de status adicionadas

            # Criando as abas internas para separar Ativos de Inativos
            tab_ativos, tab_inativos = st.tabs(["👥 Membros Ativos", "💤 Membros Inativos"])

            # Função interna para renderizar o formulário do membro sem duplicar código
            def renderizar_formulario_membro(nome):
                m = membros_db[nome]
                cat_icon = {"PUBLICADOR": "👤", "PIONEIRO AUXILIAR": "🌟",
                            "PIONEIRO REGULAR": "⭐"}.get(m.get('categoria',''), "👤")

                with st.expander(f"{cat_icon} **{nome}** — {m.get('categoria','PUBLICADOR')}"):
                    col_a, col_b = st.columns(2)

                    with col_a:
                        st.markdown("##### 📋 Dados Pessoais")
                        cat_gravada = m.get('categoria', 'PUBLICADOR')
                        if cat_gravada not in categorias_lista:
                            cat_gravada = 'PUBLICADOR'
                        nova_cat = st.selectbox("Categoria de Serviço", categorias_lista,
                                                 index=categorias_lista.index(cat_gravada),
                                                 key=f"cat_{nome}")
                        data_nasc = st.text_input("📅 Nascimento", value=m.get('data_nascimento',''),
                                                   placeholder="DD/MM/AAAA", key=f"nasc_{nome}")
                        data_bat = st.text_input("🕊️ Batismo", value=m.get('data_batismo',''),
                                                  placeholder="DD/MM/AAAA", key=f"bat_{nome}")
                        tel_emer = st.text_input("📞 Tel. Emergência",
                                                  value=m.get('telefone_emergencia',''),
                                                  placeholder="(XX) XXXXX-XXXX", key=f"tel_{nome}")

                    with col_b:
                        st.markdown("##### 🏷️ Classificação & Cargo")
                        gen_val = m.get('genero','')
                        nova_gen = st.selectbox("Gênero", _GENEROS,
                                                 index=_GENEROS.index(gen_val) if gen_val in _GENEROS else 0,
                                                 key=f"gen_{nome}")
                        cls_val = m.get('classe','')
                        nova_cls = st.selectbox("Classe", _CLASSES,
                                                 index=_CLASSES.index(cls_val) if cls_val in _CLASSES else 0,
                                                 key=f"cls_{nome}")
                        
                        # 🌟 NOVO: Campo para selecionar o Status do membro
                        status_atual = m.get('status', 'Ativo') # Padrão 'Ativo' se não existir no banco ainda
                        novo_status = st.selectbox("Status", _STATUS_OPCOES,
                                                    index=_STATUS_OPCOES.index(status_atual) if status_atual in _STATUS_OPCOES else 0,
                                                    key=f"status_{nome}")

                        cargos_atuais = cargos_para_lista(m.get('cargo',''))
                        st.markdown("**Cargo(s)**")
                        novos_cargos = []
                        for cargo_op in _CARGOS_LISTA:
                            if st.checkbox(cargo_op, value=(cargo_op in cargos_atuais),
                                           key=f"cgo_{nome}_{cargo_op}"):
                                novos_cargos.append(cargo_op)

                    st.divider()
                    if st.button("💾 Salvar Alterações", key=f"save_{nome}",
                                 use_container_width=True, type="primary"):
                        extra = {
                            "data_nascimento":     data_nasc,
                            "data_batismo":        data_bat,
                            "telefone_emergencia": tel_emer,
                            "genero":              nova_gen,
                            "classe":              nova_cls,
                            "cargo":               novos_cargos,
                            "status":              novo_status, # 🌟 NOVO: Gravando o status alterado
                        }
                        atualizar_membro(nome, nova_cat, extra=extra)
                        st.toast(f"✅ {nome} atualizado!")
                        st.rerun()

            # Organização alfabética e filtragem por Status
            membros_ordenados = sorted(membros_db.keys())

            with tab_ativos:
                # Filtra apenas quem é 'Ativo' (ou quem não tem a propriedade definida ainda)
                ativos = [n for n in membros_ordenados if membros_db[n].get('status', 'Ativo') == 'Ativo']
                if ativos:
                    for nome in ativos:
                        renderizar_formulario_membro(nome)
                else:
                    st.info("Nenhum membro ativo cadastrado.")

            with tab_inativos:
                # Filtra apenas quem foi marcado como 'Inativo'
                inativos = [n for n in membros_ordenados if membros_db[n].get('status', 'Ativo') == 'Inativo']
                if inativos:
                    for nome in inativos:
                        renderizar_formulario_membro(nome)
                else:
                    st.info("Nenhum membro inativo.")


        # ── Sub-aba 2: NOVO MEMBRO ────────────────────────────────────────────
        with sub_cfg[2]:
            st.markdown("#### ➕ Cadastrar Novo Membro")
            with st.form("novo_membro", clear_on_submit=True):
                st.markdown("##### Dados Obrigatórios")
                c1, c2 = st.columns(2)
                nm = c1.text_input("Nome Completo *")
                ct = c2.selectbox("Categoria *", categorias_lista)

                st.markdown("##### Dados do Cartão S-21")
                c3, c4 = st.columns(2)
                data_nasc_n = c3.text_input("📅 Nascimento", placeholder="DD/MM/AAAA")
                data_bat_n  = c4.text_input("🕊️ Batismo",    placeholder="DD/MM/AAAA")

                c5, c6 = st.columns(2)
                gen_n = c5.selectbox("Gênero", ["","Masculino","Feminino"])
                cls_n = c6.selectbox("Classe", ["","Outras ovelhas","Ungido"])

                st.markdown("**Cargo(s)**")
                cargos_novos_form = []
                cols_form = st.columns(len(_CARGOS_LISTA))
                for idx_c, cargo_op in enumerate(_CARGOS_LISTA):
                    if cols_form[idx_c].checkbox(cargo_op, key=f"new_cgo_{cargo_op}"):
                        cargos_novos_form.append(cargo_op)

                tel_n = st.text_input("📞 Telefone de Emergência", placeholder="(XX) XXXXX-XXXX")

                if st.form_submit_button("➕ Adicionar Membro", use_container_width=True, type="primary"):
                    if nm.strip():
                        extra_n = {
                            "data_nascimento":     data_nasc_n,
                            "data_batismo":        data_bat_n,
                            "telefone_emergencia": tel_n,
                            "genero":              gen_n,
                            "classe":              cls_n,
                            "cargo":               cargos_novos_form,
                            "status":              "Ativo", # 🌟 NOVO: Todo membro criado nasce Ativo por padrão
                        }
                        atualizar_membro(nm.strip(), ct, novo=True, extra=extra_n)
                        st.success(f"✅ {nm.strip()} adicionado!")
                        st.rerun()
                    else:
                        st.error("Informe o nome completo.")

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 0.5rem;
        font-size:0.72rem;color:#374151;letter-spacing:0.05em;">
        v5.0 · Parque Aliança · Sistema de Gestão
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
