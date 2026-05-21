import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Parque Aliança · Admin",
    layout="wide",
    page_icon="⛪",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# DESIGN SYSTEM — CSS PREMIUM
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #07090F !important;
    font-family: 'DM Sans', sans-serif !important;
    color: #E2E8F0 !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1117 0%, #0A0E1A 100%) !important;
    border-right: 1px solid rgba(99, 102, 241, 0.15) !important;
}
[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
[data-testid="stSidebar"] .stSelectbox label { color: #94A3B8 !important; font-size: 0.7rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; }

/* ── App Header ── */
[data-testid="stHeader"] { background: transparent !important; }

/* ── Main Area ── */
[data-testid="stMain"] { background: #07090F !important; }
.main .block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }

/* ── Page Title ── */
h1 {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.9rem !important;
    background: linear-gradient(135deg, #A5B4FC 0%, #818CF8 40%, #6366F1 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    letter-spacing: -0.03em !important;
    margin-bottom: 0 !important;
}
h2, h3 {
    color: #CBD5E1 !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
    background: #0D1117 !important;
    border-radius: 12px !important;
    padding: 4px !important;
    border: 1px solid rgba(99,102,241,0.15) !important;
    gap: 2px !important;
}
[data-testid="stTabs"] [role="tab"] {
    background: transparent !important;
    color: #64748B !important;
    border-radius: 9px !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #4F46E5, #6366F1) !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 12px rgba(99,102,241,0.35) !important;
}
[data-testid="stTabs"] [role="tab"]:hover:not([aria-selected="true"]) {
    color: #A5B4FC !important;
    background: rgba(99,102,241,0.08) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #0D1117 !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    border-radius: 14px !important;
    padding: 18px 20px !important;
}
[data-testid="stMetricLabel"] { color: #64748B !important; font-size: 0.7rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; }
[data-testid="stMetricValue"] { color: #A5B4FC !important; font-size: 1.8rem !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.03em !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(99,102,241,0.5) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* Botão Danger */
.btn-danger > button {
    background: linear-gradient(135deg, #DC2626 0%, #EF4444 100%) !important;
    box-shadow: 0 2px 8px rgba(239,68,68,0.3) !important;
}
.btn-danger > button:hover {
    box-shadow: 0 4px 16px rgba(239,68,68,0.5) !important;
}

/* Botão Success */
.btn-success > button {
    background: linear-gradient(135deg, #059669 0%, #10B981 100%) !important;
    box-shadow: 0 2px 8px rgba(16,185,129,0.3) !important;
}

/* Download Button */
.stDownloadButton > button {
    background: linear-gradient(135deg, #0F766E 0%, #14B8A6 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    box-shadow: 0 2px 8px rgba(20,184,166,0.3) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: #0D1117 !important;
    border: 1px solid rgba(99,102,241,0.2) !important;
    border-radius: 10px !important;
    color: #E2E8F0 !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}
label, .stSelectbox label, .stNumberInput label {
    color: #94A3B8 !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}

/* ── Checkbox ── */
.stCheckbox label { color: #CBD5E1 !important; font-size: 0.85rem !important; text-transform: none !important; letter-spacing: 0 !important; }
.stCheckbox input:checked + span { border-color: #6366F1 !important; background: #6366F1 !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #0D1117 !important;
    border: 1px solid rgba(99,102,241,0.15) !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary {
    color: #CBD5E1 !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}

/* ── Containers / Cards ── */
[data-testid="stVerticalBlock"] > [data-testid="element-container"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #0D1117 !important;
    border: 1px solid rgba(99,102,241,0.15) !important;
    border-radius: 14px !important;
    padding: 16px !important;
}

/* ── Tables ── */
[data-testid="stDataFrame"] { border-radius: 12px !important; overflow: hidden !important; }
thead tr th {
    background: #0D1117 !important;
    color: #94A3B8 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    border-bottom: 1px solid rgba(99,102,241,0.2) !important;
}
tbody tr { background: #07090F !important; }
tbody tr:hover { background: rgba(99,102,241,0.06) !important; }
tbody td { color: #CBD5E1 !important; font-family: 'DM Mono', monospace !important; font-size: 0.8rem !important; }

/* ── Alert boxes ── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
}

/* ── Caption ── */
.stCaption { color: #334155 !important; font-size: 0.7rem !important; }

/* ── Form ── */
[data-testid="stForm"] {
    background: #0D1117 !important;
    border: 1px solid rgba(99,102,241,0.15) !important;
    border-radius: 14px !important;
    padding: 20px !important;
}

/* ── Custom Components ── */
.member-card {
    background: linear-gradient(135deg, #0D1117 0%, #0F172A 100%);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}
.member-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #6366F1, #8B5CF6);
    border-radius: 3px 0 0 3px;
}
.member-card:hover {
    border-color: rgba(99,102,241,0.4);
    box-shadow: 0 4px 20px rgba(99,102,241,0.12);
    transform: translateX(2px);
}
.member-name {
    font-weight: 700;
    font-size: 0.9rem;
    color: #E2E8F0;
    letter-spacing: -0.01em;
}
.member-meta {
    font-size: 0.75rem;
    color: #64748B;
    margin-top: 3px;
    font-family: 'DM Mono', monospace;
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.badge-pub { background: rgba(99,102,241,0.15); color: #818CF8; border: 1px solid rgba(99,102,241,0.3); }
.badge-aux { background: rgba(245,158,11,0.15); color: #FCD34D; border: 1px solid rgba(245,158,11,0.3); }
.badge-reg { background: rgba(16,185,129,0.15); color: #34D399; border: 1px solid rgba(16,185,129,0.3); }
.badge-ok  { background: rgba(16,185,129,0.15); color: #34D399; border: 1px solid rgba(16,185,129,0.3); }
.badge-pend{ background: rgba(239,68,68,0.12); color: #FCA5A5; border: 1px solid rgba(239,68,68,0.25); }
.badge-auto{ background: rgba(99,102,241,0.15); color: #A5B4FC; border: 1px solid rgba(99,102,241,0.3); }

.section-header {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #475569;
    margin: 20px 0 12px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-header::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(99,102,241,0.3), transparent);
}

.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: rgba(99,102,241,0.1);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 20px;
    font-size: 0.75rem;
    color: #A5B4FC;
    font-family: 'DM Mono', monospace;
}

.triagem-auto-card {
    background: linear-gradient(135deg, rgba(16,185,129,0.06), rgba(16,185,129,0.02));
    border: 1px solid rgba(16,185,129,0.25);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 8px;
}
.triagem-manual-card {
    background: linear-gradient(135deg, rgba(245,158,11,0.06), rgba(245,158,11,0.02));
    border: 1px solid rgba(245,158,11,0.25);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 8px;
}

.pendencia-row {
    background: #0D1117;
    border: 1px solid rgba(99,102,241,0.12);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.score-bar {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(90deg, #6366F1, #8B5CF6);
    margin-top: 4px;
}

/* Sidebar logo area */
.sidebar-logo {
    padding: 20px 16px 24px;
    border-bottom: 1px solid rgba(99,102,241,0.12);
    margin-bottom: 20px;
}
.sidebar-logo h3 {
    color: #A5B4FC !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    margin: 0 !important;
}
.sidebar-logo p {
    color: #475569 !important;
    font-size: 0.7rem !important;
    margin: 4px 0 0 0 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}

/* Dividers */
hr { border-color: rgba(99,102,241,0.12) !important; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────
CATEGORIAS = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
MESES_ORDEM = [
    "SETEMBRO 2025", "OUTUBRO 2025", "NOVEMBRO 2025", "DEZEMBRO 2025",
    "JANEIRO 2026", "FEVEREIRO 2026", "MARÇO 2026", "ABRIL 2026", "MAIO 2026",
    "JUNHO 2026", "JULHO 2026", "AGOSTO 2026",
]
BADGE_MAP = {
    "PUBLICADOR": "badge-pub",
    "PIONEIRO AUXILIAR": "badge-aux",
    "PIONEIRO REGULAR": "badge-reg",
}
CAT_ICONS = {
    "PUBLICADOR": "👤",
    "PIONEIRO AUXILIAR": "🔶",
    "PIONEIRO REGULAR": "🌟",
}


# ─────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────
def normalizar(texto: str) -> str:
    if not texto:
        return ""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento.lower().strip())


def tokens(texto: str) -> set:
    return set(normalizar(texto).split())


def iniciais(texto: str) -> str:
    return "".join(p[0] for p in normalizar(texto).split() if p)


def score_similaridade(a: str, b: str) -> float:
    """Combina múltiplas estratégias de matching para máxima cobertura."""
    a_n, b_n = normalizar(a), normalizar(b)
    if not a_n or not b_n:
        return 0.0

    # 1. Sequência completa
    s1 = SequenceMatcher(None, a_n, b_n).ratio()

    # 2. Token overlap (Jaccard)
    ta, tb = tokens(a), tokens(b)
    s2 = len(ta & tb) / len(ta | tb) if ta | tb else 0.0

    # 3. Substring bidirecional
    s3 = 1.0 if a_n in b_n or b_n in a_n else 0.0

    # 4. Iniciais
    ia, ib = iniciais(a), iniciais(b)
    s4 = SequenceMatcher(None, ia, ib).ratio() if len(ia) >= 2 else 0.0

    # 5. Tokens ordenados (rearranjados)
    a_sorted = " ".join(sorted(a_n.split()))
    b_sorted = " ".join(sorted(b_n.split()))
    s5 = SequenceMatcher(None, a_sorted, b_sorted).ratio()

    # Peso ponderado
    score = (s1 * 0.35) + (s2 * 0.25) + (s3 * 0.15) + (s4 * 0.10) + (s5 * 0.15)
    return score


def identificar_membro(nome_recebido: str, membros: dict) -> tuple[str | None, float]:
    """Retorna (nome_oficial, score) ou (None, 0)."""
    melhor, maior = None, 0.0
    for nome_oficial in membros:
        s = score_similaridade(nome_recebido, nome_oficial)
        if s > maior:
            maior, melhor = s, nome_oficial
    return (melhor, maior) if maior >= 0.78 else (None, maior)


def obter_mes_atual_str() -> str:
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
             "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    n = datetime.now()
    return f"{meses[n.month-1]} {n.year}"


def badge_html(texto: str, classe: str = "") -> str:
    if not classe:
        classe = BADGE_MAP.get(texto, "badge-pub")
    return f'<span class="badge {classe}">{texto}</span>'


# ─────────────────────────────────────────────
# GERADOR DE PDF S-21
# ─────────────────────────────────────────────
def gerar_pdf_s21(nome_cabecalho: str, categoria_label: str, dados_rows: pd.DataFrame):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado.")
        return None

    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5,
    }

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24 * mm, 258 * mm, str(nome_cabecalho).upper())

    for _, row in dados_rows.iterrows():
        mes_key = str(row["mes_referencia"]).split()[0].upper()
        if mes_key not in y_map:
            continue
        y_pos = y_map[mes_key] * mm
        h = int(row.get("horas", 0))
        e = int(row.get("estudos_biblicos", 0))
        if h > 0 or e > 0:
            can.drawCentredString(53.5 * mm, y_pos, "X")
        can.drawCentredString(80.5 * mm, y_pos, str(e))
        if row.get("cat_oficial") == "PIONEIRO AUXILIAR" or "AUXILIAR" in str(categoria_label).upper():
            can.drawCentredString(97.5 * mm, y_pos, "X")
        can.drawCentredString(116.5 * mm, y_pos, str(h))
        obs = str(row.get("observacoes", ""))[:30]
        if obs and obs.lower() != "nan":
            can.setFont("Helvetica", 7)
            can.drawString(133 * mm, y_pos, obs)
            can.setFont("Helvetica-Bold", 10)

    can.save()
    packet.seek(0)
    reader = PdfReader(open(path_original, "rb"))
    writer = PdfWriter()
    pagina = reader.pages[0]
    pagina.merge_page(PdfReader(packet).pages[0])
    writer.add_page(pagina)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


# ─────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(
                credentials=creds, project="wendleydesenvolvimento"
            )
        except Exception as e:
            st.error(f"Erro ao conectar ao banco: {e}")
            return None
    return st.session_state.db


def carregar_membros() -> dict:
    db = inicializar_db()
    if not db:
        return {}
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}


def carregar_relatorios() -> list:
    db = inicializar_db()
    if not db:
        return []
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()]


def atualizar_membro(nome: str, categoria: str, novo: bool = False):
    db = inicializar_db()
    if db:
        dados = {"categoria": categoria, "nome_oficial": nome}
        if novo:
            dados["mes_inicio"] = obter_mes_atual_str()
        db.collection("membros_v2").document(nome).set(dados, merge=True)


def salvar_relatorio(nome: str, mes: str, horas: int, estudos: int, observacoes: str = ""):
    db = inicializar_db()
    if db:
        doc = {
            "nome": nome,
            "mes_referencia": mes,
            "horas": horas,
            "estudos_biblicos": estudos,
            "observacoes": observacoes,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
        db.collection("relatorios_parque_alianca").add(doc)


def deletar_relatorio_db(relatorio_id: str):
    """
    Ao deletar, substitui por um relatório zerado (horas=0, estudos=0).
    Isso evita que o membro apareça em PENDÊNCIAS após uma exclusão.
    """
    db = inicializar_db()
    if db:
        ref = db.collection("relatorios_parque_alianca").document(relatorio_id)
        doc = ref.get().to_dict()
        if doc:
            ref.update({
                "horas": 0,
                "estudos_biblicos": 0,
                "observacoes": "[RELATÓRIO ZERADO]",
                "deletado": True,
                "timestamp_delete": firestore.SERVER_TIMESTAMP,
            })


# ─────────────────────────────────────────────
# PROCESSAMENTO DE RELATÓRIOS
# ─────────────────────────────────────────────
AUTO_THRESHOLD = 0.92   # acima disso → auto-validado sem triagem
MANUAL_THRESHOLD = 0.78  # entre 0.78 e 0.92 → sugestão forte, confirma 1 clique


def processar_relatorios(relatorios_brutos: list, membros_db: dict) -> pd.DataFrame:
    if not relatorios_brutos:
        return pd.DataFrame()

    df = pd.DataFrame(relatorios_brutos)
    df["horas"] = pd.to_numeric(df["horas"], errors="coerce").fillna(0)
    df["estudos_biblicos"] = pd.to_numeric(df.get("estudos_biblicos", 0), errors="coerce").fillna(0)
    df["mes_referencia"] = df["mes_referencia"].str.upper().str.strip()

    resultados = []
    for _, row in df.iterrows():
        nome_raw = row["nome"]
        h = row["horas"]

        nome_oficial, score = identificar_membro(nome_raw, membros_db)

        if nome_oficial and score >= AUTO_THRESHOLD:
            # Auto-validado
            dados_m = membros_db[nome_oficial]
            cat_original = dados_m.get("categoria", "PUBLICADOR")
            cat_final = "PIONEIRO AUXILIAR" if cat_original == "PUBLICADOR" and h >= 15 else cat_original
            status = "IDENTIFICADO"
        elif nome_oficial and score >= MANUAL_THRESHOLD:
            # Sugestão forte — ainda vai para triagem mas com 1 clique
            dados_m = membros_db[nome_oficial]
            cat_original = dados_m.get("categoria", "PUBLICADOR")
            cat_final = "PIONEIRO AUXILIAR" if cat_original == "PUBLICADOR" and h >= 15 else cat_original
            status = "SUGESTAO"
        else:
            cat_final = "DESCONHECIDO"
            status = "TRIAGEM"

        resultados.append({
            "nome_oficial": nome_oficial or nome_raw,
            "cat_oficial": cat_final,
            "status_validacao": status,
            "match_score": round(score, 3),
        })

    df_res = pd.DataFrame(resultados)
    return pd.concat([df.reset_index(drop=True), df_res], axis=1)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # ── Sidebar ──
    st.sidebar.markdown("""
        <div class="sidebar-logo">
            <h3>⛪ Parque Aliança</h3>
            <p>Gestão de Relatórios</p>
        </div>
    """, unsafe_allow_html=True)

    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    df = processar_relatorios(relatorios_brutos, membros_db)

    meses_disponiveis = (
        sorted(df["mes_referencia"].dropna().unique().tolist(),
               key=lambda x: MESES_ORDEM.index(x) if x in MESES_ORDEM else 99)
        if not df.empty else [obter_mes_atual_str()]
    )

    mes_sel = st.sidebar.selectbox(
        "📅 Mês de Análise",
        meses_disponiveis,
        index=len(meses_disponiveis) - 1,
    )

    # Contagens para badges na sidebar
    if not df.empty:
        df_mes_all = df[df["mes_referencia"] == mes_sel]
        n_triagem = len(df_mes_all[df_mes_all["status_validacao"].isin(["TRIAGEM", "SUGESTAO"])])
        if n_triagem > 0:
            st.sidebar.markdown(
                f'<div style="margin-top:8px"><span class="badge badge-aux">⚠️ {n_triagem} em triagem</span></div>',
                unsafe_allow_html=True,
            )

    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    st.sidebar.markdown(
        '<p style="color:#334155;font-size:0.65rem;letter-spacing:0.08em;text-transform:uppercase;padding:0 4px">v3.0 · Sistema Administrativo</p>',
        unsafe_allow_html=True,
    )

    # ── Cabeçalho ──
    col_t, col_s = st.columns([3, 1])
    with col_t:
        st.title("Gestão · Parque Aliança")
        st.markdown(
            f'<span class="stat-pill">📅 {mes_sel}</span> '
            f'<span class="stat-pill">👥 {len(membros_db)} membros</span> '
            f'<span class="stat-pill">📄 {len(relatorios_brutos)} relatórios</span>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Abas principais ──
    tabs = st.tabs(["📋 Relatórios", "⚠️ Triagem", "📈 Consolidado", "⚙️ Configuração"])

    # ──────────────────────────────────────────
    # ABA 0 — RELATÓRIOS
    # ──────────────────────────────────────────
    with tabs[0]:
        df_mes = df[df["mes_referencia"] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok = df_mes[df_mes["status_validacao"] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        entregaram = set(df_ok["nome_oficial"].unique()) if not df_ok.empty else set()

        # KPIs do mês
        if not df_ok.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Envios", len(df_ok))
            k2.metric("Total Horas", f"{int(df_ok['horas'].sum())}h")
            k3.metric("Estudos Bíblicos", int(df_ok["estudos_biblicos"].sum()))
            total_membros_ativos = sum(
                1 for n, d in membros_db.items()
                if (mes_idx := MESES_ORDEM.index(d.get("mes_inicio", "SETEMBRO 2025")) if d.get("mes_inicio", "SETEMBRO 2025") in MESES_ORDEM else 0) <=
                   (MESES_ORDEM.index(mes_sel) if mes_sel in MESES_ORDEM else 99)
            )
            taxa = round(len(entregaram) / total_membros_ativos * 100) if total_membros_ativos else 0
            k4.metric("Taxa de Entrega", f"{taxa}%")

        st.markdown("<hr>", unsafe_allow_html=True)

        sub_rel = st.tabs(["👤 Publicadores", "🔶 Pion. Auxiliar", "🌟 Pion. Regular", "⏳ Pendências"])

        for i, cat in enumerate(CATEGORIAS):
            with sub_rel[i]:
                df_cat = df_ok[df_ok["cat_oficial"] == cat] if not df_ok.empty else pd.DataFrame()

                if df_cat.empty:
                    st.info(f"Nenhum envio de {cat.title()} em {mes_sel}.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Envios", len(df_cat))
                    m2.metric("Total Horas", f"{int(df_cat['horas'].sum())}h")
                    m3.metric("Estudos Bíblicos", int(df_cat["estudos_biblicos"].sum()))

                    st.markdown(
                        f'<div class="section-header">Membros que entregaram</div>',
                        unsafe_allow_html=True,
                    )
                    cols = st.columns(3)
                    for idx, (_, r) in enumerate(df_cat.sort_values("nome_oficial").iterrows()):
                        with cols[idx % 3]:
                            st.markdown(f"""
                            <div class="member-card">
                                <div class="member-name">{r['nome_oficial']}</div>
                                <div class="member-meta">⏱ {int(r['horas'])}h &nbsp;·&nbsp; 📖 {int(r['estudos_biblicos'])} estudos</div>
                            </div>
                            """, unsafe_allow_html=True)

        # ── Pendências ──
        with sub_rel[3]:
            idx_mes_sel = MESES_ORDEM.index(mes_sel) if mes_sel in MESES_ORDEM else 99

            # Montar lista de pendentes por categoria
            pendentes_por_cat: dict[str, list[str]] = {}
            for cat in CATEGORIAS:
                lista = []
                for n, d in membros_db.items():
                    inicio = d.get("mes_inicio", "SETEMBRO 2025")
                    idx_ini = MESES_ORDEM.index(inicio) if inicio in MESES_ORDEM else 0
                    if d.get("categoria") == cat and n not in entregaram and idx_mes_sel >= idx_ini:
                        lista.append(n)
                if lista:
                    pendentes_por_cat[cat] = sorted(lista)

            total_pend = sum(len(v) for v in pendentes_por_cat.values())

            if total_pend == 0:
                st.success("🎉 Todos os membros entregaram para este mês!")
            else:
                # ── Painel de Baixa em Lote ──
                st.markdown(
                    f'<div class="section-header">Pendentes neste mês — {total_pend} membros</div>',
                    unsafe_allow_html=True,
                )

                # Estado para seleção de pendências
                if "pend_selecionados" not in st.session_state:
                    st.session_state.pend_selecionados = {}

                # Botões de seleção rápida
                col_sel_all, col_des_all, col_spacer = st.columns([1, 1, 4])
                with col_sel_all:
                    if st.button("✅ Selecionar Todos", key="sel_all"):
                        for cat, lista in pendentes_por_cat.items():
                            for n in lista:
                                st.session_state.pend_selecionados[n] = True
                        st.rerun()
                with col_des_all:
                    if st.button("☐ Desmarcar Todos", key="des_all"):
                        st.session_state.pend_selecionados = {}
                        st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)

                # Grid de pendentes com checkbox
                for cat, lista in pendentes_por_cat.items():
                    badge_c = BADGE_MAP.get(cat, "badge-pub")
                    st.markdown(
                        f'<div class="section-header">{CAT_ICONS.get(cat,"")} {cat} ({len(lista)})</div>',
                        unsafe_allow_html=True,
                    )
                    for p in lista:
                        with st.container(border=True):
                            c_chk, c_nome, c_h, c_e, c_btn = st.columns([0.5, 3, 1, 1, 1.5])
                            checked = st.session_state.pend_selecionados.get(p, False)
                            novo_check = c_chk.checkbox(
                                "", value=checked, key=f"chk_pend_{p}_{mes_sel}"
                            )
                            st.session_state.pend_selecionados[p] = novo_check
                            c_nome.markdown(f"**{p}**")
                            h_manual = c_h.number_input("H", min_value=0, step=1, key=f"h_pend_{p}_{mes_sel}", label_visibility="collapsed")
                            e_manual = c_e.number_input("E", min_value=0, step=1, key=f"e_pend_{p}_{mes_sel}", label_visibility="collapsed")
                            if c_btn.button("Dar Baixa", key=f"btn_pend_{p}_{mes_sel}"):
                                salvar_relatorio(p, mes_sel, h_manual, e_manual)
                                st.toast(f"✅ Baixa registrada para {p}")
                                st.rerun()

                # ── Baixa em Lote ──
                selecionados = [n for n, v in st.session_state.pend_selecionados.items() if v]
                if selecionados:
                    st.markdown("<hr>", unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="margin-bottom:12px">'
                        f'<span class="badge badge-auto">✓ {len(selecionados)} selecionados</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    col_b1, col_b2, col_b3 = st.columns([1, 1, 3])
                    h_lote = col_b1.number_input("Horas (lote)", min_value=0, step=1, key="h_lote_global")
                    e_lote = col_b2.number_input("Estudos (lote)", min_value=0, step=1, key="e_lote_global")
                    if col_b3.button(f"🚀 Dar Baixa para {len(selecionados)} membros", key="btn_baixa_lote"):
                        for nome_sel in selecionados:
                            salvar_relatorio(nome_sel, mes_sel, h_lote, e_lote)
                        st.session_state.pend_selecionados = {}
                        st.toast(f"✅ Baixa em lote para {len(selecionados)} membros!")
                        st.rerun()

    # ──────────────────────────────────────────
    # ABA 1 — TRIAGEM
    # ──────────────────────────────────────────
    with tabs[1]:
        df_mes_t = df[df["mes_referencia"] == mes_sel] if not df.empty else pd.DataFrame()
        df_triagem = (
            df_mes_t[df_mes_t["status_validacao"].isin(["TRIAGEM", "SUGESTAO"])]
            if not df_mes_t.empty else pd.DataFrame()
        )

        if df_triagem.empty:
            st.markdown("""
                <div style="text-align:center;padding:60px 20px">
                    <div style="font-size:3rem;margin-bottom:12px">🎯</div>
                    <div style="color:#34D399;font-size:1.1rem;font-weight:600">Triagem limpa!</div>
                    <div style="color:#475569;font-size:0.8rem;margin-top:6px">Todos os relatórios foram identificados automaticamente.</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            # Separar sugestões automáticas de triagem manual
            df_sug = df_triagem[df_triagem["status_validacao"] == "SUGESTAO"]
            df_manual = df_triagem[df_triagem["status_validacao"] == "TRIAGEM"]

            # ── Sugestões Fortes (quase automático) ──
            if not df_sug.empty:
                st.markdown(
                    f'<div class="section-header">🤖 Sugestão Automática — {len(df_sug)} itens (1 clique para confirmar)</div>',
                    unsafe_allow_html=True,
                )
                for _, row in df_sug.iterrows():
                    score_pct = int(row["match_score"] * 100)
                    with st.container():
                        st.markdown(f"""
                        <div class="triagem-auto-card">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                                <div>
                                    <span style="color:#94A3B8;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">Recebido</span>
                                    <div style="color:#E2E8F0;font-weight:700;font-size:0.95rem">{row['nome']}</div>
                                </div>
                                <div style="text-align:right">
                                    <div style="color:#34D399;font-weight:700;font-size:1.1rem">{score_pct}%</div>
                                    <div style="color:#475569;font-size:0.65rem">confiança</div>
                                </div>
                            </div>
                            <div style="margin-bottom:10px">
                                <div class="score-bar" style="width:{score_pct}%"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        c1, c2, c3 = st.columns([3, 2, 1])
                        nomes_db = sorted(list(membros_db.keys()))
                        sugestao = row["nome_oficial"]
                        idx_sug = nomes_db.index(sugestao) + 1 if sugestao in nomes_db else 0
                        vincular = c1.selectbox(
                            "Vincular a:",
                            ["-- Novo Membro --"] + nomes_db,
                            index=idx_sug,
                            key=f"v_sug_{row['id']}",
                        )
                        cat_v = c2.selectbox(
                            "Categoria:",
                            CATEGORIAS,
                            index=CATEGORIAS.index(row["cat_oficial"]) if row["cat_oficial"] in CATEGORIAS else 0,
                            key=f"c_sug_{row['id']}",
                        )
                        if c3.button("✓ Confirmar", key=f"b_sug_{row['id']}"):
                            nome_final = row["nome"] if vincular == "-- Novo Membro --" else vincular
                            atualizar_membro(nome_final, cat_v, novo=(vincular == "-- Novo Membro --"))
                            inicializar_db().collection("relatorios_parque_alianca").document(row["id"]).update({"nome": nome_final})
                            st.rerun()

            # ── Triagem Manual ──
            if not df_manual.empty:
                st.markdown(
                    f'<div class="section-header">🔍 Identificação Manual — {len(df_manual)} itens</div>',
                    unsafe_allow_html=True,
                )
                for _, row in df_manual.iterrows():
                    score_pct = int(row["match_score"] * 100)
                    with st.container():
                        st.markdown(f"""
                        <div class="triagem-manual-card">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                                <div>
                                    <span style="color:#94A3B8;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">Nome recebido</span>
                                    <div style="color:#FCD34D;font-weight:700;font-size:0.95rem">{row['nome']}</div>
                                </div>
                                <div style="display:flex;gap:8px;align-items:center">
                                    <span class="badge badge-pend">sem match</span>
                                    <span style="color:#475569;font-size:0.7rem;font-family:DM Mono,monospace">⏱ {int(row['horas'])}h · 📖 {int(row['estudos_biblicos'])}</span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        c1, c2, c3 = st.columns([3, 2, 1])
                        nomes_db = sorted(list(membros_db.keys()))
                        sugestao = row["nome_oficial"] if row["nome_oficial"] in nomes_db else None
                        idx_sug = nomes_db.index(sugestao) + 1 if sugestao else 0
                        vincular = c1.selectbox(
                            "Vincular a:",
                            ["-- Novo Membro --"] + nomes_db,
                            index=idx_sug,
                            key=f"v_man_{row['id']}",
                        )
                        cat_v = c2.selectbox("Categoria:", CATEGORIAS, key=f"c_man_{row['id']}")
                        if c3.button("✓ Confirmar", key=f"b_man_{row['id']}"):
                            nome_final = row["nome"] if vincular == "-- Novo Membro --" else vincular
                            atualizar_membro(nome_final, cat_v, novo=(vincular == "-- Novo Membro --"))
                            inicializar_db().collection("relatorios_parque_alianca").document(row["id"]).update({"nome": nome_final})
                            st.rerun()

    # ──────────────────────────────────────────
    # ABA 2 — CONSOLIDADO
    # ──────────────────────────────────────────
    with tabs[2]:
        c1_tab, c2_tab = st.tabs(["👤 Histórico Individual", "📊 Por Categoria"])

        with c1_tab:
            publicador = st.selectbox("Escolha o Publicador", [""] + sorted(list(membros_db.keys())))
            if publicador:
                df_hist = (
                    df[(df["nome_oficial"] == publicador) & (df["status_validacao"] == "IDENTIFICADO")]
                    .sort_values("mes_referencia", key=lambda s: s.map(lambda x: MESES_ORDEM.index(x) if x in MESES_ORDEM else 99))
                )

                if not df_hist.empty:
                    cat_membro = membros_db[publicador].get("categoria", "PUBLICADOR")
                    badge_c = BADGE_MAP.get(cat_membro, "badge-pub")
                    st.markdown(
                        f'<div style="margin-bottom:16px"><span class="badge {badge_c}">{cat_membro}</span></div>',
                        unsafe_allow_html=True,
                    )

                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Meses Ativos", len(df_hist))
                    col_m2.metric("Total Horas", f"{int(df_hist['horas'].sum())}h")
                    col_m3.metric("Total Estudos", int(df_hist["estudos_biblicos"].sum()))

                    st.dataframe(
                        df_hist[["mes_referencia", "horas", "estudos_biblicos"]].rename(
                            columns={"mes_referencia": "Mês", "horas": "Horas", "estudos_biblicos": "Estudos"}
                        ),
                        use_container_width=True, hide_index=True,
                    )
                    pdf = gerar_pdf_s21(publicador, cat_membro, df_hist)
                    if pdf:
                        st.download_button("📥 Baixar Cartão S-21", pdf, f"S21_{publicador}.pdf", mime="application/pdf")
                else:
                    st.info("Nenhum relatório encontrado para este publicador.")

        with c2_tab:
            cat_sel = st.selectbox("Categoria", CATEGORIAS, key="cat_cons")
            df_cons = df[(df["status_validacao"] == "IDENTIFICADO") & (df["cat_oficial"] == cat_sel)] if not df.empty else pd.DataFrame()

            if not df_cons.empty:
                resumo = (
                    df_cons.groupby("mes_referencia")
                    .agg({"id": "count", "horas": "sum", "estudos_biblicos": "sum"})
                    .reset_index()
                    .rename(columns={"id": "Relatórios", "horas": "Total Horas", "estudos_biblicos": "Total Estudos", "mes_referencia": "Mês"})
                )
                resumo = resumo.sort_values("Mês", key=lambda s: s.map(lambda x: MESES_ORDEM.index(x) if x in MESES_ORDEM else 99))

                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Meses com Dados", len(resumo))
                col_m2.metric("Média Horas/Mês", f"{resumo['Total Horas'].mean():.0f}h")
                col_m3.metric("Total Estudos", int(resumo["Total Estudos"].sum()))

                st.dataframe(resumo, use_container_width=True, hide_index=True)

                df_pdf = df_cons.rename(columns={"Total Horas": "horas", "Total Estudos": "estudos_biblicos"})
                df_agg = (
                    df_cons.groupby("mes_referencia")
                    .agg({"horas": "sum", "estudos_biblicos": "sum"})
                    .reset_index()
                    .assign(cat_oficial=cat_sel)
                )
                pdf_c = gerar_pdf_s21(f"CONSOLIDADO {cat_sel}S", cat_sel, df_agg)
                if pdf_c:
                    st.download_button(f"📥 Cartão Consolidado — {cat_sel}", pdf_c, f"S21_Consolidado_{cat_sel}.pdf", mime="application/pdf")
            else:
                st.info("Sem dados para a categoria selecionada.")

    # ──────────────────────────────────────────
    # ABA 3 — CONFIGURAÇÃO
    # ──────────────────────────────────────────
    with tabs[3]:
        sub_cfg = st.tabs(["✏️ Editar Relatórios", "👥 Gerenciar Membros", "➕ Novo Membro", "📦 Exportar ZIP"])

        # ── Editar Relatórios ──
        with sub_cfg[0]:
            if df.empty:
                st.info("Sem relatórios.")
            else:
                df_ok_mes = df[(df["mes_referencia"] == mes_sel) & (df["status_validacao"] == "IDENTIFICADO")]
                if df_ok_mes.empty:
                    st.info(f"Sem relatórios validados em {mes_sel}.")
                else:
                    for _, r in df_ok_mes.sort_values("nome_oficial").iterrows():
                        # Não exibir relatórios zerados via delete
                        if r.get("observacoes") == "[RELATÓRIO ZERADO]":
                            continue
                        with st.expander(f"📝 {r['nome_oficial']}  ·  {int(r['horas'])}h  ·  {int(r['estudos_biblicos'])} estudos"):
                            ce1, ce2, ce3 = st.columns([2, 1, 1])
                            idx_cat = CATEGORIAS.index(r["cat_oficial"]) if r["cat_oficial"] in CATEGORIAS else 0
                            nova_cat = ce1.selectbox("Categoria", CATEGORIAS, index=idx_cat, key=f"e_c_{r['id']}")
                            novas_h = ce2.number_input("Horas", value=int(r["horas"]), min_value=0, key=f"e_h_{r['id']}")
                            novos_e = ce3.number_input("Estudos", value=int(r["estudos_biblicos"]), min_value=0, key=f"e_e_{r['id']}")

                            col_save, col_del = st.columns([1, 1])
                            if col_save.button("💾 Salvar", key=f"s_b_{r['id']}"):
                                inicializar_db().collection("relatorios_parque_alianca").document(r["id"]).update({
                                    "horas": novas_h, "estudos_biblicos": novos_e,
                                })
                                atualizar_membro(r["nome_oficial"], nova_cat)
                                st.toast("✅ Alterações salvas!")
                                st.rerun()

                            st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                            if col_del.button("🗑 Zerar Relatório", key=f"del_{r['id']}"):
                                deletar_relatorio_db(r["id"])
                                st.toast(f"⚠️ Relatório de {r['nome_oficial']} zerado (não aparecerá em pendências).")
                                st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

        # ── Gerenciar Membros ──
        with sub_cfg[1]:
            busca = st.text_input("🔎 Buscar membro", placeholder="Digite parte do nome…")
            membros_filtrados = {
                n: d for n, d in membros_db.items()
                if not busca or normalizar(busca) in normalizar(n)
            }
            st.markdown(
                f'<div class="section-header">{len(membros_filtrados)} membros</div>',
                unsafe_allow_html=True,
            )
            for nome in sorted(membros_filtrados.keys()):
                d = membros_db[nome]
                cat_gravada = d.get("categoria", "PUBLICADOR")
                if cat_gravada not in CATEGORIAS:
                    cat_gravada = "PUBLICADOR"
                badge_c = BADGE_MAP.get(cat_gravada, "badge-pub")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.markdown(
                        f'<div style="padding:4px 0"><span style="font-weight:700;color:#E2E8F0">{nome}</span><br>'
                        f'{badge_html(cat_gravada, badge_c)}</div>',
                        unsafe_allow_html=True,
                    )
                    nova_c = c2.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(cat_gravada), key=f"cfg_{nome}")
                    if c3.button("Salvar", key=f"btn_up_{nome}"):
                        atualizar_membro(nome, nova_c)
                        st.toast(f"✅ {nome} atualizado!")
                        st.rerun()

        # ── Novo Membro ──
        with sub_cfg[2]:
            with st.form("novo_membro"):
                st.markdown('<div class="section-header">Adicionar Novo Membro</div>', unsafe_allow_html=True)
                nm = st.text_input("Nome Completo")
                ct = st.selectbox("Categoria", CATEGORIAS)
                submitted = st.form_submit_button("✚ Adicionar Membro")
                if submitted:
                    if nm.strip():
                        atualizar_membro(nm.strip(), ct, novo=True)
                        st.success(f"✅ {nm.strip()} adicionado como {ct}!")
                        st.rerun()
                    else:
                        st.error("Por favor, informe o nome completo.")

        # ── Exportar ZIP ──
        with sub_cfg[3]:
            df_exp = df[(df["mes_referencia"] == mes_sel) & (df["status_validacao"] == "IDENTIFICADO")] if not df.empty else pd.DataFrame()
            df_exp = df_exp[df_exp.get("observacoes", "") != "[RELATÓRIO ZERADO]"] if not df_exp.empty else df_exp

            st.markdown(
                f'<div class="section-header">Exportar PDFs — {mes_sel}</div>',
                unsafe_allow_html=True,
            )
            if df_exp.empty:
                st.info("Sem relatórios validados para exportar.")
            else:
                col_i1, col_i2 = st.columns(2)
                col_i1.metric("Relatórios para exportar", len(df_exp))
                col_i2.metric("Membros únicos", df_exp["nome_oficial"].nunique())

                if st.button("🚀 Gerar ZIP Mensal", key="gerar_zip"):
                    buf = io.BytesIO()
                    erros = []
                    with zipfile.ZipFile(buf, "a") as zf:
                        for _, r in df_exp.iterrows():
                            pdf = gerar_pdf_s21(r["nome_oficial"], r["cat_oficial"], pd.DataFrame([r]))
                            if pdf:
                                zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf)
                            else:
                                erros.append(r["nome_oficial"])
                    if erros:
                        st.warning(f"Não foi possível gerar PDF para: {', '.join(erros)}")
                    st.download_button(
                        "📥 Baixar ZIP Completo",
                        buf.getvalue(),
                        f"S21_{mes_sel.replace(' ', '_')}.zip",
                        mime="application/zip",
                    )

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.caption("v3.0.0 · Parque Aliança · Sistema de Gestão de Relatórios")


if __name__ == "__main__":
    main()
