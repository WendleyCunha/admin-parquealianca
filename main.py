import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
from datetime import datetime
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="⛪")

# ============================================================
# ESTILOS PREMIUM
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }

/* Background */
[data-testid="stAppViewContainer"] > .main { background: #edf0f7; }
[data-testid="stAppViewContainer"] > .main > .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }

/* ── SIDEBAR PREMIUM ── */
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(175deg, #00112b 0%, #001f5e 55%, #003080 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] .block-container { padding: 1rem 1rem 2rem; }

/* Todos os textos da sidebar */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div { color: #b8ccec !important; }

/* Selectbox sidebar */
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.09) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: white !important;
    border-radius: 10px !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div > div { color: white !important; }

/* ── HEADER LOGO ── */
.sidebar-logo {
    text-align: center;
    padding: 12px 0 20px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 20px;
}
.sidebar-logo .icon { font-size: 2.4rem; line-height: 1; }
.sidebar-logo .title { font-size: 1.0rem; font-weight: 800; color: white !important; letter-spacing: 1.5px; margin-top: 6px; }
.sidebar-logo .sub { font-size: 0.62rem; color: #6a90c0 !important; letter-spacing: 3px; text-transform: uppercase; margin-top: 2px; }

/* ── BADGE MÊS ── */
.mes-badge {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 12px;
    padding: 14px 10px;
    text-align: center;
    margin: 10px 0 6px;
}
.mes-badge-top { font-size: 0.6rem; color: #6a90c0 !important; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 5px; }
.mes-badge-main { font-size: 1.15rem; font-weight: 800; color: white !important; letter-spacing: 0.5px; }

/* ── MINI STATS SIDEBAR ── */
.sidebar-stats { display: flex; gap: 6px; margin: 10px 0 16px; }
.sstat {
    flex: 1;
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 6px;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.1);
}
.sstat-num { font-size: 1.35rem; font-weight: 800; color: white !important; line-height: 1; }
.sstat-lbl { font-size: 0.58rem; color: #6a90c0 !important; text-transform: uppercase; letter-spacing: 1.5px; margin-top: 3px; }
.sstat-warn { color: #ffc542 !important; }

/* ── METRIC BOXES ── */
.mbox {
    background: white;
    border-radius: 14px;
    padding: 18px 14px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,35,100,0.07);
    border-top: 3px solid #002d80;
    margin-bottom: 0;
    height: 100%;
}
.mbox.green { border-top-color: #16a34a; }
.mbox.amber { border-top-color: #d97706; }
.mbox.red   { border-top-color: #dc2626; }
.mnum { font-size: 2rem; font-weight: 800; color: #001a4d; line-height: 1.1; font-variant-numeric: tabular-nums; }
.mlbl { font-size: 0.62rem; color: #64748b; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px; }

/* ── REPORT CARD ── */
.rcard {
    background: white;
    border-radius: 12px;
    padding: 12px 16px;
    margin: 5px 0;
    border-left: 4px solid #002d80;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05);
    transition: box-shadow 0.15s ease, border-color 0.15s ease;
}
.rcard:hover { box-shadow: 0 3px 14px rgba(0,35,100,0.10); }
.rcard.sel { border-left-color: #e63946; background: #fff7f7; }
.rcard-name { font-weight: 700; font-size: 0.9rem; color: #0f172a; margin-bottom: 3px; }
.rcard-meta { font-size: 0.78rem; color: #475569; display: flex; gap: 12px; align-items: center; }

/* ── BADGES ── */
.badge { display:inline-block; padding:2px 9px; border-radius:20px; font-size:0.68rem; font-weight:700; letter-spacing:0.5px; }
.badge-pub { background:#e0f2fe; color:#0369a1; }
.badge-aux { background:#fef3c7; color:#92400e; }
.badge-reg { background:#dcfce7; color:#166534; }
.badge-unk { background:#f1f5f9; color:#475569; }

/* ── SCORE TRIAGEM ── */
.score-hi { display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.7rem; font-weight:700; background:#dcfce7; color:#166534; }
.score-md { display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.7rem; font-weight:700; background:#fef9c3; color:#854d0e; }
.score-lo { display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.7rem; font-weight:700; background:#fee2e2; color:#991b1b; }

/* ── BULK BAR ── */
.bulk-bar {
    background: linear-gradient(90deg, #1e3a8a, #2563eb);
    border-radius: 12px;
    padding: 12px 18px;
    color: white !important;
    font-weight: 700;
    font-size: 0.9rem;
    margin: 6px 0 10px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* ── PENDING CARD ── */
.pending-card {
    background: white;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 6px 0;
    border-left: 4px solid #f59e0b;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.pending-name { font-weight: 700; font-size: 0.9rem; color: #0f172a; }

/* ── TRIAGEM CARD ── */
.triagem-card {
    background: #fffbf0;
    border: 1px solid #fbbf24;
    border-radius: 12px;
    padding: 16px 18px;
    margin: 8px 0;
}
.triagem-nome-digitado {
    font-family: 'DM Mono', monospace;
    background: #f1f5f9;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.95rem;
    font-weight: 600;
    color: #0f172a;
}

/* ── DIVIDER ── */
.section-divider {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 16px 0;
}

/* Oculta rodapé Streamlit */
#MainMenu, footer, .stDeployButton { visibility: hidden; }

/* Estilo dos tabs */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05);
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    padding: 8px 18px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    transition: background 0.15s ease !important;
}
.stTabs [aria-selected="true"] {
    background: #002d80 !important;
    color: white !important;
}

/* Buttons */
.stButton > button {
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background: #002d80 !important;
    border: none !important;
}
.stDownloadButton > button {
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================

def normalizar_texto(texto):
    if not texto: return ""
    return "".join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()

def obter_mes_atual_str():
    meses = ["JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
             "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"]
    now = datetime.now()
    return f"{meses[now.month-1]} {now.year}"

def badge_html(cat):
    cls_map = {"PUBLICADOR": "pub", "PIONEIRO AUXILIAR": "aux", "PIONEIRO REGULAR": "reg"}
    cls = cls_map.get(cat, "unk")
    return f'<span class="badge badge-{cls}">{cat}</span>'

def score_html(score):
    pct = int(score * 100)
    cls = "score-hi" if pct >= 80 else ("score-md" if pct >= 65 else "score-lo")
    label = "Alta" if pct >= 80 else ("Média" if pct >= 65 else "Baixa")
    return f'<span class="{cls}">≈{pct}% · {label} confiança</span>'

# ============================================================
# MOTOR DE MATCHING — MULTI-ESTRATÉGIA
# ============================================================

def calcular_score_match(nome_recebido: str, lista_membros: list) -> tuple:
    """
    Retorna (melhor_match, score) usando múltiplas estratégias combinadas:
    1. Sequência completa normalizada
    2. Token-sort (ignora ordem dos nomes)
    3. Jaccard de tokens (sobreposição de palavras)
    4. Subtoken (nome parcial contido em outro)
    5. Bônus: primeiro nome idêntico
    6. Bônus: match exato
    """
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3:
        return None, 0.0

    tokens_e = entrada_norm.split()
    tokens_e_sorted = sorted(tokens_e)
    set_e = set(tokens_e)
    melhor_match, maior_score = None, 0.0

    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        tokens_o = oficial_norm.split()
        tokens_o_sorted = sorted(tokens_o)
        set_o = set(tokens_o)

        # 1 — Sequência completa
        s1 = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()

        # 2 — Token-sort (ordena antes de comparar, tolera inversões de nome)
        s2 = SequenceMatcher(None,
                             " ".join(tokens_e_sorted),
                             " ".join(tokens_o_sorted)).ratio()

        # 3 — Jaccard de tokens
        union = set_e | set_o
        s3 = len(set_e & set_o) / len(union) if union else 0.0

        # 4 — Subtoken parcial (ex: "Wend" detecta "Wendley")
        s4 = 0.0
        for te in tokens_e:
            if len(te) < 3:
                continue
            for to in tokens_o:
                if te in to or to in te:
                    shorter = min(len(te), len(to))
                    longer  = max(len(te), len(to))
                    s4 = max(s4, shorter / longer * 0.85)

        # Score composto ponderado
        score = s1 * 0.35 + s2 * 0.35 + s3 * 0.20 + s4 * 0.10

        # Bônus: primeiro token idêntico (mesmo primeiro nome)
        if tokens_e and tokens_o and tokens_e[0] == tokens_o[0]:
            score = min(1.0, score + 0.08)

        # Bônus: match exato após normalização
        if entrada_norm == oficial_norm:
            score = 1.0

        if score > maior_score:
            maior_score, melhor_match = score, nome_oficial

    return melhor_match, maior_score

def normalizar_nome_no_banco(nome_recebido: str, lista_membros) -> str | None:
    """Compatibilidade com código legado — retorna só o nome ou None."""
    match, score = calcular_score_match(nome_recebido, list(lista_membros))
    # Threshold reduzido de 0.85 → 0.72 graças ao algoritmo mais robusto
    return match if score >= 0.72 else None

# ============================================================
# MOTOR DE PDF (inalterado)
# ============================================================

def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado.")
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24*mm, 258*mm, str(nome_cabecalho).upper())

    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5,
    }

    for _, row in dados_rows.iterrows():
        mes_key = str(row['mes_referencia']).split()[0].upper()
        if mes_key not in y_map:
            continue
        y_pos = y_map[mes_key] * mm
        if int(row.get('horas', 0)) > 0 or int(row.get('estudos_biblicos', 0)) > 0:
            can.drawCentredString(53.5*mm, y_pos, "X")
        can.drawCentredString(80.5*mm, y_pos, str(int(row.get('estudos_biblicos', 0))))
        if row.get('cat_oficial') == "PIONEIRO AUXILIAR" or "AUXILIAR" in str(categoria_label).upper():
            can.drawCentredString(97.5*mm, y_pos, "X")
        can.drawCentredString(116.5*mm, y_pos, str(int(row.get('horas', 0))))
        obs = str(row.get('observacoes', ''))[:30]
        if obs and obs.lower() != 'nan':
            can.setFont("Helvetica", 7)
            can.drawString(133*mm, y_pos, obs)
            can.setFont("Helvetica-Bold", 10)

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

# ============================================================
# BANCO DE DADOS — com cache de sessão para evitar reads excessivos
# ============================================================

def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(
                credentials=creds, project="wendleydesenvolvimento"
            )
        except Exception as e:
            st.error(f"Erro de conexão com Firestore: {e}")
            return None
    return st.session_state.db

def invalidar_cache():
    """Remove todos os caches para forçar reload do Firestore no próximo acesso."""
    for k in ['membros_cache', 'relatorios_cache', 'df_processado']:
        st.session_state.pop(k, None)

def carregar_membros() -> dict:
    db = inicializar_db()
    if not db: return {}
    if 'membros_cache' not in st.session_state:
        st.session_state.membros_cache = {
            doc.id: doc.to_dict()
            for doc in db.collection("membros_v2").stream()
        }
    return st.session_state.membros_cache

def carregar_relatorios() -> list:
    db = inicializar_db()
    if not db: return []
    if 'relatorios_cache' not in st.session_state:
        st.session_state.relatorios_cache = [
            {"id": doc.id, **doc.to_dict()}
            for doc in db.collection("relatorios_parque_alianca").stream()
        ]
    return st.session_state.relatorios_cache

def atualizar_membro(nome: str, categoria: str, novo: bool = False):
    db = inicializar_db()
    if db:
        dados = {"categoria": categoria, "nome_oficial": nome}
        if novo:
            dados["mes_inicio"] = obter_mes_atual_str()
        db.collection("membros_v2").document(nome).set(dados, merge=True)
        invalidar_cache()

def deletar_relatorio(relatorio_id: str):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        invalidar_cache()
        st.toast("🗑️ Relatório deletado.")
        st.rerun()

def deletar_multiplos(ids: list):
    """Batch delete para máxima eficiência no Firestore."""
    db = inicializar_db()
    if not db or not ids: return
    batch = db.batch()
    for rid in ids:
        batch.delete(db.collection("relatorios_parque_alianca").document(rid))
    batch.commit()
    invalidar_cache()
    # Limpa checkboxes dos itens deletados
    for rid in ids:
        st.session_state.pop(f"chk_{rid}", None)
    st.toast(f"🗑️ {len(ids)} relatório(s) deletado(s).")
    st.rerun()

def salvar_baixa_manual(nome: str, mes: str, horas: int, estudos: int):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").add({
            "nome": nome,
            "mes_referencia": mes,
            "horas": horas,
            "estudos_biblicos": estudos,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        invalidar_cache()
        st.toast(f"✅ Baixa registrada para {nome}!")
        st.rerun()

# ============================================================
# PROCESSAMENTO DO DATAFRAME — com cache na sessão
# ============================================================

def processar_df(relatorios_brutos: list, membros_db: dict) -> pd.DataFrame:
    """
    Processa e valida relatórios. Usa cache de sessão — só reprocessa quando
    os dados brutos mudam (invalidar_cache() limpa 'df_processado').
    """
    if 'df_processado' in st.session_state:
        return st.session_state.df_processado

    if not relatorios_brutos:
        st.session_state.df_processado = pd.DataFrame()
        return st.session_state.df_processado

    df = pd.DataFrame(relatorios_brutos)
    df['horas'] = pd.to_numeric(df.get('horas', 0), errors='coerce').fillna(0)
    df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)

    lista_membros = list(membros_db.keys())  # pré-calculado, não chama dict.keys() por linha

    def validar_envio(row):
        nome_oficial = normalizar_nome_no_banco(row['nome'], lista_membros)
        if nome_oficial:
            dados_m = membros_db[nome_oficial]
            cat_original = dados_m.get('categoria', 'PUBLICADOR')
            cat_final = (
                "PIONEIRO AUXILIAR"
                if cat_original == "PUBLICADOR" and row['horas'] >= 15
                else cat_original
            )
            return pd.Series([nome_oficial, cat_final, "IDENTIFICADO"])
        return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
    df['mes_referencia'] = df['mes_referencia'].str.upper()

    st.session_state.df_processado = df
    return df

# ============================================================
# HELPERS DE UI
# ============================================================

def render_metric(col, label: str, value, color: str = ""):
    col.markdown(
        f'<div class="mbox {color}"><div class="mnum">{value}</div><div class="mlbl">{label}</div></div>',
        unsafe_allow_html=True
    )

def get_checked_ids(df_cat: pd.DataFrame) -> list:
    """Lê o estado atual dos checkboxes sem precisar de rerun."""
    return [
        r['id'] for _, r in df_cat.iterrows()
        if st.session_state.get(f"chk_{r['id']}", False)
    ]

def gerar_zip_df(df_source: pd.DataFrame, df_full: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "a") as zf:
        for _, r in df_source.iterrows():
            df_hist = df_full[
                (df_full['nome_oficial'] == r['nome_oficial']) &
                (df_full['status_validacao'] == 'IDENTIFICADO')
            ].sort_values('mes_referencia')
            pdf_bytes = gerar_pdf_padrao_s21(r['nome_oficial'], r['cat_oficial'], df_hist)
            if pdf_bytes:
                zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf_bytes)
    buf.seek(0)
    return buf.getvalue()

# ============================================================
# APP PRINCIPAL
# ============================================================

def main():
    # Dados base
    membros_db       = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    categorias_lista  = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    meses_ordem = [
        "SETEMBRO 2025","OUTUBRO 2025","NOVEMBRO 2025","DEZEMBRO 2025",
        "JANEIRO 2026","FEVEREIRO 2026","MARÇO 2026","ABRIL 2026","MAIO 2026",
    ]

    # DF processado (cached)
    df = processar_df(relatorios_brutos, membros_db)

    # Meses disponíveis
    if not df.empty and 'mes_referencia' in df.columns:
        meses_disp = sorted(df['mes_referencia'].dropna().unique().tolist())
    else:
        meses_disp = [obter_mes_atual_str()]

    # ═══════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-logo">
            <div class="icon">⛪</div>
            <div class="title">PARQUE ALIANÇA</div>
            <div class="sub">Gestão · 72249</div>
        </div>
        """, unsafe_allow_html=True)

        # Label
        st.markdown(
            '<div style="font-size:0.62rem;color:#5a7ea8;letter-spacing:2.5px;'
            'text-transform:uppercase;margin-bottom:6px;">📅 Mês de análise</div>',
            unsafe_allow_html=True
        )

        mes_sel = st.selectbox(
            "Mês", meses_disp,
            index=len(meses_disp) - 1,
            label_visibility="collapsed"
        )

        # Badge visual do mês selecionado
        partes = mes_sel.split()
        nome_mes = partes[0] if partes else mes_sel
        ano_mes  = partes[1] if len(partes) > 1 else ""
        st.markdown(f"""
        <div class="mes-badge">
            <div class="mes-badge-top">analisando</div>
            <div class="mes-badge-main">📆 {nome_mes}<br>
                <span style="font-size:0.85rem;font-weight:500;color:#9ab5d8;">{ano_mes}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Mini stats do mês
        if not df.empty:
            df_mes_s   = df[df['mes_referencia'] == mes_sel]
            n_enviados = len(df_mes_s[df_mes_s['status_validacao'] == 'IDENTIFICADO'])
            n_triagem  = len(df_mes_s[df_mes_s['status_validacao'] == 'TRIAGEM'])
            n_membros  = len(membros_db)
            warn_cls   = "sstat-warn" if n_triagem > 0 else ""
            st.markdown(f"""
            <div class="sidebar-stats">
                <div class="sstat">
                    <div class="sstat-num">{n_enviados}</div>
                    <div class="sstat-lbl">Enviados</div>
                </div>
                <div class="sstat">
                    <div class="sstat-num {warn_cls}">{n_triagem}</div>
                    <div class="sstat-lbl">Triagem</div>
                </div>
                <div class="sstat">
                    <div class="sstat-num">{n_membros}</div>
                    <div class="sstat-lbl">Membros</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<hr style="border:none;border-top:1px solid rgba(255,255,255,0.1);margin:12px 0;">', unsafe_allow_html=True)

        if st.button("🔄 Recarregar dados", use_container_width=True):
            invalidar_cache()
            st.rerun()

        st.markdown(
            '<div style="font-size:0.6rem;color:#3a5c82;margin-top:16px;text-align:center;">'
            'v3.0.0 · Parque Aliança</div>',
            unsafe_allow_html=True
        )

    # ═══════════════════════════════════
    # CABEÇALHO PRINCIPAL
    # ═══════════════════════════════════
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:22px;
                background:white;border-radius:16px;padding:16px 22px;
                box-shadow:0 2px 10px rgba(0,0,0,0.05);">
        <div style="font-size:2.2rem;line-height:1;">📊</div>
        <div>
            <h1 style="margin:0;font-size:1.45rem;color:#001a4d;font-weight:800;">
                Gestão Parque Aliança
            </h1>
            <p style="margin:0;color:#64748b;font-size:0.82rem;">
                Congregação 72249 &nbsp;·&nbsp; {mes_sel}
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ─── Dados do mês selecionado ───
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
    df_ok  = df_mes[df_mes['status_validacao'] == 'IDENTIFICADO'] if not df_mes.empty else pd.DataFrame()
    entregaram = set(df_ok['nome_oficial'].unique()) if not df_ok.empty else set()

    # ═══════════════════════════════════
    # ABAS PRINCIPAIS
    # ═══════════════════════════════════
    tabs = st.tabs(["📋 Relatórios", "⚠️ Triagem", "📈 Consolidado", "⚙️ Configurações"])

    # ═══════════════════════════════════════════════════════════
    # ABA 0 — RELATÓRIOS
    # ═══════════════════════════════════════════════════════════
    with tabs[0]:
        # Métricas rápidas
        total_pub  = len(df_ok[df_ok['cat_oficial'] == 'PUBLICADOR'])         if not df_ok.empty else 0
        total_aux  = len(df_ok[df_ok['cat_oficial'] == 'PIONEIRO AUXILIAR'])  if not df_ok.empty else 0
        total_reg  = len(df_ok[df_ok['cat_oficial'] == 'PIONEIRO REGULAR'])   if not df_ok.empty else 0
        total_h    = int(df_ok['horas'].sum())                                 if not df_ok.empty else 0
        total_est  = int(df_ok['estudos_biblicos'].sum())                      if not df_ok.empty else 0

        m1,m2,m3,m4,m5 = st.columns(5)
        render_metric(m1, "Relatórios", len(df_ok))
        render_metric(m2, "Publicadores", total_pub, "")
        render_metric(m3, "Pioneiros Aux.", total_aux, "amber")
        render_metric(m4, "Pioneiros Reg.", total_reg, "green")
        render_metric(m5, "Total Horas", f"{total_h}h")

        st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)

        # ── Sub-abas por categoria + Pendências ──
        sub_rel = st.tabs(["👥 Publicadores", "🌟 Pioneiros Aux.", "🏆 Pioneiros Reg.", "⏳ Pendências"])

        for i, cat in enumerate(categorias_lista):
            with sub_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()

                if df_cat.empty:
                    st.info(f"Nenhum relatório de {cat.title()} para {mes_sel}.")
                    continue

                # ── Barra de seleção em lote ──
                checked_ids = get_checked_ids(df_cat)

                hdr_c1, hdr_c2, hdr_c3 = st.columns([2, 2, 4])
                with hdr_c1:
                    if st.button("☑️ Selecionar todos", key=f"selall_{i}", use_container_width=True):
                        for rid in df_cat['id'].tolist():
                            st.session_state[f"chk_{rid}"] = True
                        st.rerun()
                with hdr_c2:
                    if st.button("□ Limpar seleção", key=f"desel_{i}", use_container_width=True):
                        for rid in df_cat['id'].tolist():
                            st.session_state[f"chk_{rid}"] = False
                        st.rerun()

                if checked_ids:
                    st.markdown(
                        f'<div class="bulk-bar">✅ {len(checked_ids)} relatório(s) selecionado(s)</div>',
                        unsafe_allow_html=True
                    )
                    ba1, ba2, ba3 = st.columns([2, 2, 4])

                    with ba1:
                        if st.button("🗑️ Deletar selecionados", key=f"bulk_del_{i}", type="primary", use_container_width=True):
                            deletar_multiplos(checked_ids)

                    with ba2:
                        df_sel = df_cat[df_cat['id'].isin(checked_ids)]
                        zip_bytes = gerar_zip_df(df_sel, df)
                        st.download_button(
                            "📦 Baixar ZIP selecionados",
                            zip_bytes,
                            f"S21_Selecionados_{mes_sel}.zip",
                            mime="application/zip",
                            key=f"bulk_dl_{i}",
                            use_container_width=True
                        )

                st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

                # ── Cards individuais ──
                for _, r in df_cat.sort_values('nome_oficial').iterrows():
                    rid = r['id']
                    is_sel = st.session_state.get(f"chk_{rid}", False)

                    col_chk, col_card, col_btn = st.columns([0.4, 5, 2.2])

                    with col_chk:
                        st.markdown('<div style="padding-top:22px;">', unsafe_allow_html=True)
                        st.checkbox("", key=f"chk_{rid}", label_visibility="collapsed")
                        st.markdown('</div>', unsafe_allow_html=True)

                    with col_card:
                        border = "#e63946" if is_sel else "#002d80"
                        bg     = "background:#fff7f7;" if is_sel else ""
                        obs_txt = str(r.get('observacoes', ''))
                        obs_html = (
                            f'&nbsp;·&nbsp; 💬 <em style="color:#94a3b8;">{obs_txt[:40]}</em>'
                            if obs_txt and obs_txt.lower() not in ('nan', '', 'none')
                            else ""
                        )
                        st.markdown(f"""
                        <div class="rcard" style="border-left-color:{border};{bg}">
                            <div class="rcard-name">{r['nome_oficial']}</div>
                            <div class="rcard-meta">
                                ⏱️ {int(r['horas'])}h
                                &nbsp;·&nbsp;
                                📚 {int(r['estudos_biblicos'])} est.
                                &nbsp;·&nbsp;
                                {badge_html(r['cat_oficial'])}
                                {obs_html}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_btn:
                        # PDF individual (histórico completo)
                        df_hist_ind = df[
                            (df['nome_oficial'] == r['nome_oficial']) &
                            (df['status_validacao'] == 'IDENTIFICADO')
                        ].sort_values('mes_referencia')
                        pdf_bytes = gerar_pdf_padrao_s21(
                            r['nome_oficial'], r['cat_oficial'], df_hist_ind
                        )
                        if pdf_bytes:
                            st.download_button(
                                "📄 S-21",
                                pdf_bytes,
                                f"S21_{r['nome_oficial']}.pdf",
                                key=f"dl_{rid}",
                                use_container_width=True
                            )
                        if st.button("🗑️ Deletar", key=f"del_{rid}", use_container_width=True):
                            deletar_relatorio(rid)

        # ── PENDÊNCIAS ──
        with sub_rel[3]:
            idx_mes_sel = meses_ordem.index(mes_sel) if mes_sel in meses_ordem else 99

            st.warning(f"⏳ Publicadores que **não entregaram** relatório em **{mes_sel}**")

            total_pend = 0
            for cat in categorias_lista:
                pendentes = []
                for n, d in membros_db.items():
                    inicio   = d.get('mes_inicio', 'SETEMBRO 2025')
                    idx_ini  = meses_ordem.index(inicio) if inicio in meses_ordem else 0
                    if (d.get('categoria') == cat
                            and n not in entregaram
                            and idx_mes_sel >= idx_ini):
                        pendentes.append(n)
                total_pend += len(pendentes)

                if not pendentes:
                    continue

                icons = {"PUBLICADOR": "👥", "PIONEIRO AUXILIAR": "🌟", "PIONEIRO REGULAR": "🏆"}
                with st.expander(
                    f"{icons.get(cat,'📂')} {cat} — {len(pendentes)} pendente(s)",
                    expanded=True
                ):
                    for p in sorted(pendentes):
                        st.markdown(f'<div class="pending-card"><div class="pending-name">👤 {p}</div></div>',
                                    unsafe_allow_html=True)
                        pc1, pc2, pc3, pc4 = st.columns([0.1, 1.2, 1.2, 1.8])
                        h_m = pc2.number_input(
                            "Horas", min_value=0, step=1,
                            key=f"h_man_{p}_{mes_sel}"
                        )
                        e_m = pc3.number_input(
                            "Estudos", min_value=0, step=1,
                            key=f"e_man_{p}_{mes_sel}"
                        )
                        if pc4.button(
                            "✅ Dar Baixa",
                            key=f"btn_man_{p}_{mes_sel}",
                            use_container_width=True
                        ):
                            salvar_baixa_manual(p, mes_sel, h_m, e_m)
                        st.markdown('<hr class="section-divider" style="margin:6px 0;">', unsafe_allow_html=True)

            if total_pend == 0:
                st.success("🎉 Todos os membros entregaram o relatório neste mês!")

    # ═══════════════════════════════════════════════════════════
    # ABA 1 — TRIAGEM
    # ═══════════════════════════════════════════════════════════
    with tabs[1]:
        df_triagem = (
            df_mes[df_mes['status_validacao'] == 'TRIAGEM']
            if not df_mes.empty
            else pd.DataFrame()
        )

        if df_triagem.empty:
            st.success("✅ Tudo identificado! Nenhum relatório aguarda triagem para este mês.")
        else:
            st.warning(f"⚠️ **{len(df_triagem)}** relatório(s) aguardando identificação manual.")
            nomes_db = sorted(list(membros_db.keys()))

            for _, row in df_triagem.iterrows():
                sugestao, score = calcular_score_match(row['nome'], nomes_db)
                idx_sug = (nomes_db.index(sugestao) + 1) if sugestao else 0

                with st.container(border=True):
                    # Cabeçalho do card
                    st.markdown(f"""
                    <div style="margin-bottom:10px;">
                        <span style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
                              letter-spacing:1.5px;">Nome digitado pelo publicador</span><br>
                        <span class="triagem-nome-digitado">{row['nome']}</span>
                        &nbsp;
                        <span style="font-size:0.8rem;color:#64748b;">
                            ⏱️ {int(row['horas'])}h &nbsp;·&nbsp;
                            📚 {int(row['estudos_biblicos'])} est.
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Resultado do matching
                    if sugestao:
                        st.markdown(
                            f"🔍 Sugestão automática: **{sugestao}** &nbsp; "
                            f"{score_html(score)}",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            "🔍 **Nenhuma sugestão automática encontrada** — revise manualmente."
                        )

                    c1, c2 = st.columns(2)
                    vincular = c1.selectbox(
                        "Vincular a membro existente:",
                        ["— Cadastrar como Novo Membro —"] + nomes_db,
                        index=idx_sug,
                        key=f"v_{row['id']}"
                    )
                    cat_v = c2.selectbox(
                        "Categoria:", categorias_lista, key=f"c_{row['id']}"
                    )

                    btn1, btn2 = st.columns([2, 1])
                    with btn1:
                        if st.button(
                            "✅ Confirmar Identificação",
                            key=f"b_{row['id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            eh_novo = (vincular == "— Cadastrar como Novo Membro —")
                            nome_final = row['nome'] if eh_novo else vincular
                            atualizar_membro(nome_final, cat_v, novo=eh_novo)
                            inicializar_db().collection("relatorios_parque_alianca") \
                                .document(row['id']).update({"nome": nome_final})
                            invalidar_cache()
                            st.rerun()
                    with btn2:
                        if st.button(
                            "🗑️ Descartar",
                            key=f"disc_{row['id']}",
                            use_container_width=True
                        ):
                            deletar_relatorio(row['id'])

    # ═══════════════════════════════════════════════════════════
    # ABA 2 — CONSOLIDADO
    # ═══════════════════════════════════════════════════════════
    with tabs[2]:
        c1_tab, c2_tab = st.tabs(["👤 Individual (Histórico)", "📊 Por Categoria"])

        with c1_tab:
            publicador = st.selectbox("Escolha o Publicador", sorted(list(membros_db.keys())))
            if publicador:
                df_hist = df[
                    (df['nome_oficial'] == publicador) &
                    (df['status_validacao'] == 'IDENTIFICADO')
                ].sort_values('mes_referencia')

                if df_hist.empty:
                    st.info("Nenhum relatório encontrado para este publicador.")
                else:
                    st.dataframe(
                        df_hist[['mes_referencia','horas','estudos_biblicos']].rename(
                            columns={'mes_referencia':'Mês','horas':'Horas',
                                     'estudos_biblicos':'Estudos'}
                        ),
                        use_container_width=True,
                        hide_index=True
                    )
                    cat_pub = membros_db[publicador].get('categoria', 'PUBLICADOR')
                    pdf = gerar_pdf_padrao_s21(publicador, cat_pub, df_hist)
                    if pdf:
                        st.download_button(
                            "📥 Baixar Cartão S-21 Completo",
                            pdf,
                            f"S21_{publicador}.pdf",
                            mime="application/pdf"
                        )

        with c2_tab:
            cat_sel = st.selectbox("Consolidado por Categoria", categorias_lista)
            df_cons = df[
                (df['status_validacao'] == 'IDENTIFICADO') &
                (df['cat_oficial'] == cat_sel)
            ]
            if df_cons.empty:
                st.info(f"Nenhum dado para {cat_sel}.")
            else:
                resumo = df_cons.groupby('mes_referencia').agg(
                    relatorios_enviados=('id', 'count'),
                    total_horas=('horas', 'sum'),
                    total_estudos=('estudos_biblicos', 'sum')
                ).reset_index().rename(columns={'mes_referencia': 'Mês'})
                st.dataframe(resumo, use_container_width=True, hide_index=True)

                pdf_c = gerar_pdf_padrao_s21(
                    f"CONSOLIDADO {cat_sel}S", cat_sel,
                    resumo.rename(columns={
                        'Mês': 'mes_referencia',
                        'total_horas': 'horas',
                        'total_estudos': 'estudos_biblicos'
                    })
                )
                if pdf_c:
                    st.download_button(
                        f"📥 Baixar Cartão {cat_sel}",
                        pdf_c,
                        f"S21_Consolidado_{cat_sel}.pdf",
                        mime="application/pdf"
                    )

    # ═══════════════════════════════════════════════════════════
    # ABA 3 — CONFIGURAÇÕES
    # ═══════════════════════════════════════════════════════════
    with tabs[3]:
        sub_cfg = st.tabs([
            "✏️ Editar Relatórios",
            "👥 Gerenciar Membros",
            "➕ Novo Membro",
            "📦 Exportar ZIP"
        ])

        # ── Editar relatórios ──
        with sub_cfg[0]:
            if df_ok.empty:
                st.info("Nenhum relatório validado para editar neste mês.")
            else:
                for _, r in df_ok.sort_values('nome_oficial').iterrows():
                    with st.expander(
                        f"📝 {r['nome_oficial']} — {int(r['horas'])}h · {int(r['estudos_biblicos'])} est."
                    ):
                        ce1, ce2, ce3 = st.columns([2, 1, 1])
                        idx_cat = (
                            categorias_lista.index(r['cat_oficial'])
                            if r['cat_oficial'] in categorias_lista else 0
                        )
                        nova_cat = ce1.selectbox(
                            "Categoria", categorias_lista,
                            index=idx_cat, key=f"e_c_{r['id']}"
                        )
                        novas_h = ce2.number_input(
                            "Horas", value=int(r['horas']), min_value=0, key=f"e_h_{r['id']}"
                        )
                        novos_e = ce3.number_input(
                            "Estudos", value=int(r['estudos_biblicos']), min_value=0, key=f"e_e_{r['id']}"
                        )
                        sb1, sb2 = st.columns(2)
                        with sb1:
                            if st.button(
                                "💾 Salvar Alterações",
                                key=f"s_b_{r['id']}",
                                use_container_width=True
                            ):
                                inicializar_db().collection("relatorios_parque_alianca") \
                                    .document(r['id']).update({
                                        "horas": novas_h,
                                        "estudos_biblicos": novos_e
                                    })
                                atualizar_membro(r['nome_oficial'], nova_cat)
                                invalidar_cache()
                                st.rerun()
                        with sb2:
                            if st.button(
                                "🗑️ Deletar Relatório",
                                key=f"del_cfg_{r['id']}",
                                use_container_width=True
                            ):
                                deletar_relatorio(r['id'])

        # ── Gerenciar membros ──
        with sub_cfg[1]:
            st.subheader("Membros Cadastrados")
            busca = st.text_input("🔍 Buscar membro", placeholder="Digite parte do nome...")

            for nome in sorted(membros_db.keys()):
                if busca and normalizar_texto(busca) not in normalizar_texto(nome):
                    continue
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1.2])
                    c1.markdown(f"**{nome}**")
                    c1.caption(f"📅 Desde: {membros_db[nome].get('mes_inicio', 'N/A')}")
                    cat_gravada = membros_db[nome].get('categoria', 'PUBLICADOR')
                    if cat_gravada not in categorias_lista:
                        cat_gravada = "PUBLICADOR"
                    idx_m   = categorias_lista.index(cat_gravada)
                    nova_c  = c2.selectbox(
                        "Categoria", categorias_lista,
                        index=idx_m, key=f"cfg_{nome}"
                    )
                    if c3.button("Atualizar", key=f"btn_up_{nome}", use_container_width=True):
                        atualizar_membro(nome, nova_c)
                        st.toast(f"✅ {nome} atualizado!")

        # ── Novo membro ──
        with sub_cfg[2]:
            st.subheader("Adicionar Novo Membro")
            with st.form("novo_membro", clear_on_submit=True):
                nm = st.text_input(
                    "Nome Completo",
                    placeholder="Digite exatamente como o publicador usará no formulário"
                )
                ct = st.selectbox("Categoria", categorias_lista)
                if st.form_submit_button("➕ Adicionar Membro", use_container_width=True):
                    if nm.strip():
                        atualizar_membro(nm.strip(), ct, novo=True)
                        st.success(f"✅ {nm.strip()} adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error("⚠️ O nome não pode estar vazio.")

        # ── Exportar ZIP ──
        with sub_cfg[3]:
            st.subheader(f"Exportar ZIP — {mes_sel}")
            st.info(
                "Gera cartões S-21 individuais (histórico completo) "
                "para todos os relatórios validados do mês selecionado."
            )
            if df_ok.empty:
                st.warning("Nenhum relatório validado para exportar neste mês.")
            else:
                st.write(f"**{len(df_ok)} relatório(s)** prontos para exportação.")
                if st.button("🚀 Gerar ZIP Completo do Mês", type="primary", use_container_width=True):
                    with st.spinner("Gerando PDFs..."):
                        zip_bytes = gerar_zip_df(df_ok, df)
                    st.download_button(
                        f"📥 Baixar ZIP — {mes_sel}",
                        zip_bytes,
                        f"S21_{mes_sel}.zip",
                        mime="application/zip"
                    )

    st.caption("v3.0.0 | Parque Aliança | Gestão Completa")


if __name__ == "__main__":
    main()
