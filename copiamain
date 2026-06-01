import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
import base64
from datetime import datetime
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO CUSTOMIZADA ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px;
                   border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px;
                        border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    .anuncio-preview { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;
                       margin-bottom: 8px; background: #f8fafc; }
    </style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE CALIBRAÇÃO DO PDF S-21
# Se o preenchimento aparecer deslocado, ajuste os valores abaixo.
# Todas as medidas são em mm a partir do rodapé da página (padrão ReportLab).
# PDF_Y_OFFSET: positivo = sobe tudo; negativo = desce tudo (tabela de meses)
# ═══════════════════════════════════════════════════════════════════════════════
PDF_Y_OFFSET    = 0.0     # ajuste fino global das linhas da tabela (mm)

# ── Cabeçalho ──────────────────────────────────────────────────────────────────
# DIAGNÓSTICO: nome estava aparecendo na linha do batismo → todos sobem +14 mm
PDF_NOME_Y      = 272.0   # y do nome      (era 258.0)
PDF_NOME_X      = 24.0    # x do nome

PDF_NASCI_Y     = 265.0   # y data de nascimento  (era 251.5)
PDF_NASCI_X     = 48.0    # x do valor (após o label)

PDF_BATISM_Y    = 258.0   # y data de batismo     (era 244.5)
PDF_BATISM_X    = 48.0    # x do valor

PDF_CARGO_Y     = 252.0   # y linha dos checkboxes de cargo (+1mm para cima)

# ── Gênero (lado direito — mesma linha do nascimento) ─────────────────────────
# X precisa ir mais para a DIREITA para alcançar o checkbox de Masculino/Feminino
PDF_MASC_X      = 150.0   # era 122 → mais à direita (ajuste ±3mm se necessário)
PDF_FEM_X       = 172.0   # era 148 → mais à direita

# ── Classe (lado direito — mesma linha do batismo) ────────────────────────────
PDF_OVELHAS_X   = 150.0   # era 122 → mais à direita
PDF_UNGIDO_X    = 172.0   # era 148 → mais à direita

# ── Cargos/Privilégios (linha inferior do cabeçalho) ──────────────────────────
# X do Ancião: ligeiramente à esquerda e mínimo para cima
PDF_ANCIAO_X    = 9.5     # era 12.0 → levemente à esquerda
PDF_SERVO_X     = 35.0
PDF_PREG_X      = 65.0    # Pioneiro regular
PDF_PESP_X      = 100.0   # Pioneiro especial
PDF_MISS_X      = 140.0   # Missionário em campo

# ── Telefone de emergência fixo no cabeçalho da tabela (sob "Observações") ────
PDF_TEL_HEADER_Y = 232.0  # ajuste ±2mm se necessário

# ── Y-map dos meses (ajuste PDF_Y_OFFSET se todos estiverem deslocados) ────────
# Valores corrigidos +24 mm em relação à versão anterior para alinhar ao s21.pdf
_Y_MAP_BASE = {
    "SETEMBRO":  228.5,
    "OUTUBRO":   220.5,
    "NOVEMBRO":  212.5,
    "DEZEMBRO":  204.5,
    "JANEIRO":   196.5,
    "FEVEREIRO": 188.5,
    "MARÇO":     180.5,
    "ABRIL":     172.5,
    "MAIO":      164.5,
    "JUNHO":     156.5,
    "JULHO":     148.5,
    "AGOSTO":    140.5,
}

# Colunas da tabela
PDF_COL_PARTICIP_X = 53.5   # "Participou no ministério" (X)
PDF_COL_ESTUDOS_X  = 80.5   # Estudos bíblicos
PDF_COL_PIAUX_X    = 97.5   # Pioneiro auxiliar (X)
PDF_COL_HORAS_X    = 116.5  # Horas
PDF_COL_OBS_X      = 133.0  # Observações

# ───────────────────────────────────────────────────────────────────────────────


# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


def obter_mes_atual_str():
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
             "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    now = datetime.now()
    return f"{meses[now.month - 1]} {now.year}"


# ─── MOTOR DE PDF ──────────────────────────────────────────────────────────────
def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows, membro_info=None):
    """
    Preenche o cartão S-21.
    membro_info : dict com os campos extras do membro (data_nascimento,
                  data_batismo, genero, classe, cargo, telefone_emergencia).
    """
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado na pasta do app.")
        return None

    mi = membro_info or {}

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)

    # ── Nome ────────────────────────────────────────────────────────────────
    can.setFont("Helvetica-Bold", 10)
    can.drawString(PDF_NOME_X * mm, PDF_NOME_Y * mm, str(nome_cabecalho).upper())

    # ── Data de Nascimento ───────────────────────────────────────────────────
    data_nasc = str(mi.get("data_nascimento", "")).strip()
    if data_nasc:
        can.setFont("Helvetica", 9)
        can.drawString(PDF_NASCI_X * mm, PDF_NASCI_Y * mm, data_nasc)

    # ── Data de Batismo ──────────────────────────────────────────────────────
    data_bat = str(mi.get("data_batismo", "")).strip()
    if data_bat:
        can.setFont("Helvetica", 9)
        can.drawString(PDF_BATISM_X * mm, PDF_BATISM_Y * mm, data_bat)

    # ── Gênero ───────────────────────────────────────────────────────────────
    genero = mi.get("genero", "")
    can.setFont("Helvetica-Bold", 10)
    if genero == "Masculino":
        can.drawString(PDF_MASC_X * mm, PDF_NASCI_Y * mm, "X")
    elif genero == "Feminino":
        can.drawString(PDF_FEM_X * mm, PDF_NASCI_Y * mm, "X")

    # ── Classe ───────────────────────────────────────────────────────────────
    classe = mi.get("classe", "")
    if classe == "Outras ovelhas":
        can.drawString(PDF_OVELHAS_X * mm, PDF_BATISM_Y * mm, "X")
    elif classe == "Ungido":
        can.drawString(PDF_UNGIDO_X * mm, PDF_BATISM_Y * mm, "X")

    # ── Cargo / Privilégio ───────────────────────────────────────────────────
    cargo = mi.get("cargo", "")
    cargo_map = {
        "Ancião":               PDF_ANCIAO_X,
        "Servo ministerial":    PDF_SERVO_X,
        "Pioneiro regular":     PDF_PREG_X,
        "Pioneiro especial":    PDF_PESP_X,
        "Missionário em campo": PDF_MISS_X,
    }
    if cargo in cargo_map:
        can.drawString(cargo_map[cargo] * mm, PDF_CARGO_Y * mm, "X")

    # ── Telefone de emergência: fixo no cabeçalho da tabela (sob "Observações") ─
    tel_emerg = str(mi.get("telefone_emergencia", "")).strip()
    if tel_emerg:
        can.setFont("Helvetica-Bold", 9)
        can.drawString(PDF_COL_OBS_X * mm, PDF_TEL_HEADER_Y * mm,
                       f"Tel: {tel_emerg}"[:32])

    # ── Linhas da tabela de meses ────────────────────────────────────────────
    for _, row in dados_rows.iterrows():
        mes_key = str(row.get('mes_referencia', '')).split()[0].upper()
        y_base  = _Y_MAP_BASE.get(mes_key)
        if y_base is None:
            continue
        y_pos = (y_base + PDF_Y_OFFSET) * mm

        horas = int(row.get('horas', 0))
        estud = int(row.get('estudos_biblicos', 0))

        # Participou no ministério
        if horas > 0 or estud > 0:
            can.setFont("Helvetica-Bold", 10)
            can.drawCentredString(PDF_COL_PARTICIP_X * mm, y_pos, "X")

        # Estudos bíblicos
        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_ESTUDOS_X * mm, y_pos, str(estud))

        # Pioneiro auxiliar
        cat_str = str(categoria_label).upper()
        if row.get('cat_oficial') == "PIONEIRO AUXILIAR" or "AUXILIAR" in cat_str:
            can.drawCentredString(PDF_COL_PIAUX_X * mm, y_pos, "X")

        # Horas
        can.drawCentredString(PDF_COL_HORAS_X * mm, y_pos, str(horas))

        # Observações da linha (sem telefone — já está no cabeçalho)
        obs_normal = str(row.get('observacoes', ''))
        obs_normal = obs_normal if obs_normal.lower() not in ('nan', '', 'none') else ''
        if obs_normal:
            can.setFont("Helvetica", 8)
            can.drawString(PDF_COL_OBS_X * mm, y_pos, obs_normal[:32])

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


# --- BANCO DE DADOS ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds,
                                                    project="wendleydesenvolvimento")
        except Exception:
            return None
    return st.session_state.db


def carregar_membros():
    db = inicializar_db()
    if not db:
        return {}
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}


def carregar_relatorios():
    db = inicializar_db()
    if not db:
        return []
    return [{"id": doc.id, **doc.to_dict()}
            for doc in db.collection("relatorios_parque_alianca").stream()]


def atualizar_membro(nome, categoria, novo=False, extra=None):
    """
    Salva/atualiza um membro no Firestore.
    extra : dict com campos adicionais (data_nascimento, data_batismo,
            genero, classe, cargo, telefone_emergencia).
    """
    db = inicializar_db()
    if db:
        dados = {"categoria": categoria, "nome_oficial": nome}
        if novo:
            dados["mes_inicio"] = obter_mes_atual_str()
        if extra:
            dados.update({k: v for k, v in extra.items() if v is not None})
        db.collection("membros_v2").document(nome).set(dados, merge=True)


def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório deletado!")
        st.rerun()


def salvar_baixa_manual(nome, mes, horas, estudos):
    db = inicializar_db()
    if db:
        novo_doc = {
            "nome": nome, "mes_referencia": mes, "horas": horas,
            "estudos_biblicos": estudos, "timestamp": firestore.SERVER_TIMESTAMP
        }
        db.collection("relatorios_parque_alianca").add(novo_doc)
        st.success(f"Relatório de {nome} adicionado!")
        st.rerun()


def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3:
        return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score:
            maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.85 else None


# ─── FUNÇÕES DE ANÚNCIOS ───────────────────────────────────────────────────────
def carregar_anuncios():
    db = inicializar_db()
    if not db:
        return []
    try:
        docs = (db.collection("anuncios")
                  .order_by("data_postagem", direction=firestore.Query.DESCENDING)
                  .stream())
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception as e:
        st.warning(f"Erro ao carregar anúncios: {e}")
        return []


def salvar_anuncio(dados):
    db = inicializar_db()
    if not db:
        return False
    dados["data_postagem"] = firestore.SERVER_TIMESTAMP
    db.collection("anuncios").add(dados)
    return True


def deletar_anuncio(anuncio_id):
    db = inicializar_db()
    if db:
        db.collection("anuncios").document(anuncio_id).delete()
        st.toast("✅ Anúncio deletado!")
        st.rerun()


# ─── GERADOR DE HTML DA AGENDA ─────────────────────────────────────────────────
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
                f'font-weight:bold;font-size:14.5px;letter-spacing:0.3px;">'
                f'{texto}</div>')

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
# APP PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    meses_referencia_ordem = [
        "SETEMBRO 2025", "OUTUBRO 2025", "NOVEMBRO 2025", "DEZEMBRO 2025",
        "JANEIRO 2026", "FEVEREIRO 2026", "MARÇO 2026", "ABRIL 2026", "MAIO 2026"
    ]

    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(
            df.get('estudos_biblicos', 0), errors='coerce').fillna(0)

        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial:
                dados_m = membros_db[nome_oficial]
                cat_original = dados_m.get('categoria', 'PUBLICADOR')
                cat_final = ("PIONEIRO AUXILIAR"
                             if cat_original == "PUBLICADOR" and row['horas'] >= 15
                             else cat_original)
                return pd.Series([nome_oficial, cat_final, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(
            validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = (sorted(df['mes_referencia'].unique())
                         if not df.empty else [obter_mes_atual_str()])
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis,
                                    index=len(meses_disponiveis) - 1)

    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO",
                    "📢 ANÚNCIOS", "⚙️ CONFIGURAÇÃO"])

    # ── ABA 0: RELATÓRIOS ──────────────────────────────────────────────────────
    with tabs[0]:
        df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok  = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        entregaram = df_ok['nome_oficial'].unique()

        st.subheader(f"Resumo de {mes_sel}")
        sub_rel = st.tabs(["PUBLICADOR", "P. AUXILIAR", "P. REGULAR", "⏳ PENDÊNCIAS"])

        for i, cat in enumerate(categorias_lista):
            with sub_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat]
                if df_cat.empty:
                    st.info("Sem envios.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Envios", len(df_cat))
                    m2.metric("Total Horas", f"{int(df_cat['horas'].sum())}h")
                    m3.metric("Estudos", int(df_cat['estudos_biblicos'].sum()))
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(
                                f'<div class="card">'
                                f'<div class="card-header">{r["nome_oficial"]}</div>'
                                f'⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}'
                                f'</div>',
                                unsafe_allow_html=True)

        with sub_rel[3]:
            st.warning(f"Quem ainda NÃO entregou em {mes_sel}:")
            idx_mes_sel = (meses_referencia_ordem.index(mes_sel)
                           if mes_sel in meses_referencia_ordem else 99)
            for cat in categorias_lista:
                pendentes = []
                for n, d_m in membros_db.items():
                    inicio  = d_m.get('mes_inicio', 'SETEMBRO 2025')
                    idx_ini = (meses_referencia_ordem.index(inicio)
                               if inicio in meses_referencia_ordem else 0)
                    if (d_m.get('categoria') == cat
                            and n not in entregaram
                            and idx_mes_sel >= idx_ini):
                        pendentes.append(n)
                if pendentes:
                    with st.expander(f"{cat} ({len(pendentes)})"):
                        for p in sorted(pendentes):
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                            c1.write(f"**{p}**")
                            h_manual = c2.number_input("H", min_value=0, step=1,
                                                        key=f"h_man_{p}_{mes_sel}")
                            e_manual = c3.number_input("E", min_value=0, step=1,
                                                        key=f"e_man_{p}_{mes_sel}")
                            if c4.button("Dar Baixa", key=f"btn_man_{p}_{mes_sel}"):
                                salvar_baixa_manual(p, mes_sel, h_manual, e_manual)

    # ── ABA 1: TRIAGEM ─────────────────────────────────────────────────────────
    with tabs[1]:
        df_triagem = (df_mes[df_mes['status_validacao'] == "TRIAGEM"]
                      if not df_mes.empty else pd.DataFrame())
        if df_triagem.empty:
            st.success("✅ Tudo limpo! Nenhum relatório em triagem.")
        else:
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.write(f"**Digitado:** {row['nome']} | **Horas:** {row['horas']}")
                    nomes_db = sorted(list(membros_db.keys()))
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_db)
                    idx_sug  = nomes_db.index(sugestao) + 1 if sugestao else 0
                    c1, c2   = st.columns(2)
                    vincular = c1.selectbox("Vincular a:",
                                            ["-- Novo Membro --"] + nomes_db,
                                            index=idx_sug, key=f"v_{row['id']}")
                    cat_v = c2.selectbox("Categoria:", categorias_lista,
                                         key=f"c_{row['id']}")
                    if st.button("Confirmar", key=f"b_{row['id']}"):
                        nome_final = row['nome'] if vincular == "-- Novo Membro --" else vincular
                        atualizar_membro(nome_final, cat_v,
                                         novo=(vincular == "-- Novo Membro --"))
                        inicializar_db().collection("relatorios_parque_alianca") \
                            .document(row['id']).update({"nome": nome_final})
                        st.rerun()

    # ── ABA 2: CONSOLIDADO ─────────────────────────────────────────────────────
    with tabs[2]:
        c1_tab, c2_tab = st.tabs(["👤 INDIVIDUAL (HISTÓRICO)", "📊 CATEGORIA"])
        with c1_tab:
            publicador = st.selectbox("Escolha o Publicador",
                                       sorted(list(membros_db.keys())))
            if publicador:
                df_hist = df[
                    (df['nome_oficial'] == publicador) &
                    (df['status_validacao'] == "IDENTIFICADO")
                ].sort_values('mes_referencia')
                if not df_hist.empty:
                    st.table(df_hist[['mes_referencia', 'horas', 'estudos_biblicos']])
                    pdf = gerar_pdf_padrao_s21(
                        publicador,
                        membros_db[publicador].get('categoria'),
                        df_hist,
                        membro_info=membros_db[publicador]   # ← dados completos
                    )
                    if pdf:
                        st.download_button("📥 Baixar Cartão S-21 Completo", pdf,
                                           f"S21_{publicador}.pdf")

        with c2_tab:
            cat_sel  = st.selectbox("Consolidado por Categoria", categorias_lista)
            df_cons  = df[(df['status_validacao'] == "IDENTIFICADO") &
                          (df['cat_oficial'] == cat_sel)]
            if not df_cons.empty:
                resumo = df_cons.groupby('mes_referencia').agg(
                    {'id': 'count', 'horas': 'sum', 'estudos_biblicos': 'sum'}
                ).reset_index().rename(columns={
                    'id': 'relatorios_enviados',
                    'horas': 'total_horas',
                    'estudos_biblicos': 'total_estudos'
                })
                st.dataframe(resumo, use_container_width=True)
                pdf_c = gerar_pdf_padrao_s21(
                    f"CONSOLIDADO {cat_sel}S", cat_sel,
                    resumo.rename(columns={
                        'total_horas': 'horas',
                        'total_estudos': 'estudos_biblicos'
                    })
                )
                if pdf_c:
                    st.download_button(f"📥 Baixar Cartão {cat_sel}", pdf_c,
                                       f"S21_Consolidado_{cat_sel}.pdf")

    # ── ABA 3: ANÚNCIOS ────────────────────────────────────────────────────────
    with tabs[3]:
        sub_an = st.tabs(["✏️ Nova Postagem", "🗂️ Gerenciar Postagens"])

        with sub_an[0]:
            tipo = st.radio(
                "Tipo de postagem",
                ["📝 Texto / Markdown", "🖼️ Imagem (JPEG/PNG)", "📅 Agenda de Reunião"],
                horizontal=True
            )

            if tipo == "📝 Texto / Markdown":
                st.info("Use Markdown: **negrito**, *itálico*, listas com `-`, títulos com `#`.")
                titulo_txt   = st.text_input("Título do anúncio (opcional)")
                conteudo_md  = st.text_area("Conteúdo", height=200,
                                             placeholder="Digite o texto do anúncio aqui...")
                st.caption("Pré-visualização:")
                if conteudo_md:
                    st.markdown(conteudo_md)
                if st.button("📤 Publicar Texto", use_container_width=True):
                    if conteudo_md.strip():
                        salvar_anuncio({
                            "tipo": "texto",
                            "titulo": titulo_txt or "Anúncio",
                            "conteudo_html": conteudo_md,
                            "renderizar_markdown": True
                        })
                        st.success("✅ Anúncio publicado!")
                        st.rerun()
                    else:
                        st.error("O conteúdo não pode estar vazio.")

            elif tipo == "🖼️ Imagem (JPEG/PNG)":
                titulo_img = st.text_input("Legenda / Título da imagem (opcional)")
                arquivo    = st.file_uploader("Enviar imagem", type=["jpg", "jpeg", "png"])
                if arquivo:
                    st.image(arquivo, caption=titulo_img or "Pré-visualização",
                             use_column_width=True)
                    if st.button("📤 Publicar Imagem", use_container_width=True):
                        img_bytes = arquivo.read()
                        mime  = "image/png" if arquivo.name.endswith(".png") else "image/jpeg"
                        b64   = base64.b64encode(img_bytes).decode("utf-8")
                        html_img = (
                            f'<div style="text-align:center;padding:10px;">'
                            f'<img src="data:{mime};base64,{b64}" '
                            f'style="max-width:100%;border-radius:8px;" />'
                            + (f'<p style="margin-top:8px;color:#555;font-size:14px;">'
                               f'{titulo_img}</p>' if titulo_img else "")
                            + '</div>'
                        )
                        salvar_anuncio({
                            "tipo": "imagem",
                            "titulo": titulo_img or arquivo.name,
                            "conteudo_html": html_img,
                            "renderizar_markdown": False
                        })
                        st.success("✅ Imagem publicada!")
                        st.rerun()
                else:
                    st.info("Selecione uma imagem para enviar.")

            elif tipo == "📅 Agenda de Reunião":
                st.markdown("#### 📋 Preencha a Agenda")

                col_a, col_b = st.columns(2)
                data_texto = col_a.text_input("📅 Período", placeholder="18-24 DE MAIO")
                escritura  = col_b.text_input("📖 Escritura", placeholder="ISAÍAS 62-64")

                col_c, col_d, col_e = st.columns(3)
                cant_ab   = col_c.text_input("🎵 Cântico Abertura", placeholder="44")
                cant_meio = col_d.text_input("🎵 Cântico NVC",      placeholder="115")
                cant_fin  = col_e.text_input("🎵 Cântico Final",    placeholder="151")

                st.markdown("---")
                st.markdown(
                    '<div style="background:#1a3566;color:white;padding:7px 12px;'
                    'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                    'TESOUROS DA PALAVRA DE DEUS</div>', unsafe_allow_html=True)
                n_tes = st.number_input("Nº de itens", 1, 6, 3, key="n_tes")
                tesouros = []
                for i in range(int(n_tes)):
                    c1, c2 = st.columns([4, 1])
                    t     = c1.text_input(f"Item {i+1}", key=f"tes_t_{i}",
                                          label_visibility="collapsed",
                                          placeholder=f"Item {i+1} – Título")
                    d_dur = c2.text_input("Dur.", key=f"tes_d_{i}",
                                          label_visibility="collapsed",
                                          placeholder="10 min")
                    tesouros.append({"num": i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                st.markdown(
                    '<div style="background:#8a6200;color:white;padding:7px 12px;'
                    'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                    'FAÇA SEU MELHOR NO MINISTÉRIO</div>', unsafe_allow_html=True)
                n_min    = st.number_input("Nº de itens", 1, 6, 3, key="n_min")
                ministerio = []
                base_min = int(n_tes)
                for i in range(int(n_min)):
                    c1, c2 = st.columns([4, 1])
                    t     = c1.text_input(f"Item {base_min+i+1}", key=f"min_t_{i}",
                                          label_visibility="collapsed",
                                          placeholder=f"Item {base_min+i+1} – Título")
                    d_dur = c2.text_input("Dur.", key=f"min_d_{i}",
                                          label_visibility="collapsed", placeholder="")
                    ministerio.append({"num": base_min + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                st.markdown(
                    '<div style="background:#cc0000;color:white;padding:7px 12px;'
                    'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                    'NOSSA VIDA CRISTÃ</div>', unsafe_allow_html=True)
                n_nvc    = st.number_input("Nº de itens", 1, 10, 2, key="n_nvc")
                vida_crista = []
                base_nvc = int(n_tes) + int(n_min)
                for i in range(int(n_nvc)):
                    c1, c2 = st.columns([4, 1])
                    t     = c1.text_input(f"Item {base_nvc+i+1}", key=f"nvc_t_{i}",
                                          label_visibility="collapsed",
                                          placeholder=f"Item {base_nvc+i+1} – Título")
                    d_dur = c2.text_input("Dur.", key=f"nvc_d_{i}",
                                          label_visibility="collapsed",
                                          placeholder="30 min" if i == int(n_nvc)-1 else "")
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
                    if st.button("👁️ Pré-visualizar", use_container_width=True):
                        st.markdown(gerar_html_agenda(agenda_dados), unsafe_allow_html=True)
                with col_pub:
                    if st.button("📤 Publicar Agenda", use_container_width=True, type="primary"):
                        if not data_texto.strip():
                            st.error("Informe o período da semana.")
                        else:
                            html_agenda = gerar_html_agenda(agenda_dados)
                            salvar_anuncio({
                                "tipo": "agenda", "titulo": data_texto,
                                "conteudo_html": html_agenda,
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
                st.caption(f"{len(anuncios)} postagem(ns) • mais recente primeiro")
                for a in anuncios:
                    tipo_icon = {"texto": "📝", "imagem": "🖼️", "agenda": "📅"}.get(
                        a.get("tipo", ""), "📌")
                    titulo_a = a.get("titulo", "Sem título")
                    ts       = a.get("data_postagem")
                    data_str = ts.strftime("%d/%m/%Y %H:%M") if hasattr(ts, "strftime") else "–"
                    with st.expander(f"{tipo_icon} {titulo_a}  ·  {data_str}"):
                        if a.get("renderizar_markdown"):
                            st.markdown(a.get("conteudo_html", ""), unsafe_allow_html=False)
                        else:
                            st.markdown(a.get("conteudo_html", ""), unsafe_allow_html=True)
                        st.markdown("---")
                        if st.button(f"🗑️ Deletar esta postagem",
                                     key=f"del_an_{a['id']}", type="secondary"):
                            deletar_anuncio(a["id"])

    # ── ABA 4: CONFIGURAÇÃO ────────────────────────────────────────────────────
    with tabs[4]:
        sub_cfg = st.tabs(["✏️ EDITAR RELATÓRIOS", "👥 GERENCIAR MEMBROS",
                           "➕ NOVO MEMBRO", "📦 EXPORTAR ZIP"])

        # ── Sub-aba 0: Editar Relatórios ─────────────────────────────────────
        with sub_cfg[0]:
            if not df.empty:
                df_ok_mes = df[(df['mes_referencia'] == mes_sel) &
                               (df['status_validacao'] == "IDENTIFICADO")]
                for _, r in df_ok_mes.sort_values('nome_oficial').iterrows():
                    with st.expander(f"📝 {r['nome_oficial']} ({int(r['horas'])}h)"):
                        ce1, ce2, ce3 = st.columns([2, 1, 1])
                        idx_cat  = (categorias_lista.index(r['cat_oficial'])
                                    if r['cat_oficial'] in categorias_lista else 0)
                        nova_cat = ce1.selectbox("Categoria", categorias_lista,
                                                  index=idx_cat, key=f"e_c_{r['id']}")
                        novas_h  = ce2.number_input("Horas", value=int(r['horas']),
                                                     key=f"e_h_{r['id']}")
                        novos_e  = ce3.number_input("Estudos", value=int(r['estudos_biblicos']),
                                                     key=f"e_e_{r['id']}")
                        if st.button("Salvar Alterações", key=f"s_b_{r['id']}"):
                            inicializar_db().collection("relatorios_parque_alianca") \
                                .document(r['id']).update(
                                    {"horas": novas_h, "estudos_biblicos": novos_e})
                            atualizar_membro(r['nome_oficial'], nova_cat)
                            st.rerun()
                        if st.button("Deletar Relatório", key=f"del_{r['id']}"):
                            deletar_relatorio(r['id'])

        # ── Sub-aba 1: GERENCIAR MEMBROS (UPGRADE COMPLETO) ──────────────────
        with sub_cfg[1]:
            st.subheader("👥 Gerenciar Membros")
            st.caption("Clique no nome do membro para expandir e editar todos os dados.")

            _GENEROS  = ["", "Masculino", "Feminino"]
            _CLASSES  = ["", "Outras ovelhas", "Ungido"]
            _CARGOS   = ["", "Ancião", "Servo ministerial", "Pioneiro regular",
                         "Pioneiro especial", "Missionário em campo"]

            for nome in sorted(membros_db.keys()):
                m        = membros_db[nome]
                cat_icon = {"PUBLICADOR": "👤", "PIONEIRO AUXILIAR": "🌟",
                            "PIONEIRO REGULAR": "⭐"}.get(m.get('categoria', ''), "👤")

                with st.expander(f"{cat_icon} **{nome}** — {m.get('categoria', 'PUBLICADOR')}"):

                    col_a, col_b = st.columns(2)

                    # ── Coluna esquerda: dados pessoais ───────────────────────
                    with col_a:
                        st.markdown("##### 📋 Dados Pessoais")

                        cat_gravada = m.get('categoria', 'PUBLICADOR')
                        if cat_gravada not in categorias_lista:
                            cat_gravada = 'PUBLICADOR'
                        nova_cat = st.selectbox(
                            "Categoria de Serviço",
                            categorias_lista,
                            index=categorias_lista.index(cat_gravada),
                            key=f"cat_{nome}")

                        data_nasc = st.text_input(
                            "📅 Data de Nascimento",
                            value=m.get('data_nascimento', ''),
                            placeholder="DD/MM/AAAA",
                            key=f"nasc_{nome}")

                        data_bat = st.text_input(
                            "🕊️ Data de Batismo",
                            value=m.get('data_batismo', ''),
                            placeholder="DD/MM/AAAA",
                            key=f"bat_{nome}")

                        tel_emer = st.text_input(
                            "📞 Telefone de Emergência",
                            value=m.get('telefone_emergencia', ''),
                            placeholder="(XX) XXXXX-XXXX",
                            key=f"tel_{nome}")

                    # ── Coluna direita: classificação e cargo ─────────────────
                    with col_b:
                        st.markdown("##### 🏷️ Classificação & Cargo")

                        gen_val  = m.get('genero', '')
                        nova_gen = st.selectbox(
                            "Gênero",
                            _GENEROS,
                            index=_GENEROS.index(gen_val) if gen_val in _GENEROS else 0,
                            key=f"gen_{nome}")

                        cls_val  = m.get('classe', '')
                        nova_cls = st.selectbox(
                            "Classe",
                            _CLASSES,
                            index=_CLASSES.index(cls_val) if cls_val in _CLASSES else 0,
                            key=f"cls_{nome}")

                        cgo_val  = m.get('cargo', '')
                        novo_cgo = st.selectbox(
                            "Cargo / Privilégio",
                            _CARGOS,
                            index=_CARGOS.index(cgo_val) if cgo_val in _CARGOS else 0,
                            key=f"cgo_{nome}")

                        # ── Resumo do cartão S-21 ─────────────────────────────
                        st.markdown("##### 🗂️ Resumo p/ Cartão S-21")
                        flags = []
                        if nova_gen:    flags.append(nova_gen)
                        if nova_cls:    flags.append(nova_cls)
                        if novo_cgo:    flags.append(novo_cgo)
                        if data_nasc:   flags.append(f"Nasc: {data_nasc}")
                        if data_bat:    flags.append(f"Bat: {data_bat}")
                        if tel_emer:    flags.append(f"Tel: {tel_emer}")
                        if flags:
                            for f in flags:
                                st.markdown(f"• {f}")
                        else:
                            st.caption("Nenhum dado extra cadastrado ainda.")

                    st.divider()
                    if st.button("💾 Salvar Alterações", key=f"save_{nome}",
                                 use_container_width=True, type="primary"):
                        extra = {
                            "data_nascimento":     data_nasc,
                            "data_batismo":        data_bat,
                            "telefone_emergencia": tel_emer,
                            "genero":              nova_gen,
                            "classe":              nova_cls,
                            "cargo":               novo_cgo,
                        }
                        atualizar_membro(nome, nova_cat, extra=extra)
                        st.toast(f"✅ {nome} atualizado com sucesso!")
                        st.rerun()

        # ── Sub-aba 2: NOVO MEMBRO ────────────────────────────────────────────
        with sub_cfg[2]:
            st.subheader("➕ Cadastrar Novo Membro")
            with st.form("novo_membro", clear_on_submit=True):
                st.markdown("##### Dados Obrigatórios")
                c1, c2 = st.columns(2)
                nm = c1.text_input("Nome Completo *")
                ct = c2.selectbox("Categoria *", categorias_lista)

                st.markdown("##### Dados do Cartão S-21")
                c3, c4 = st.columns(2)
                data_nasc_n = c3.text_input("📅 Data de Nascimento", placeholder="DD/MM/AAAA")
                data_bat_n  = c4.text_input("🕊️ Data de Batismo",    placeholder="DD/MM/AAAA")

                c5, c6, c7 = st.columns(3)
                gen_n = c5.selectbox("Gênero", ["", "Masculino", "Feminino"])
                cls_n = c6.selectbox("Classe", ["", "Outras ovelhas", "Ungido"])
                cgo_n = c7.selectbox("Cargo / Privilégio",
                                      ["", "Ancião", "Servo ministerial",
                                       "Pioneiro regular", "Pioneiro especial",
                                       "Missionário em campo"])

                tel_n = st.text_input("📞 Telefone de Emergência",
                                       placeholder="(XX) XXXXX-XXXX")

                if st.form_submit_button("➕ Adicionar Membro", use_container_width=True):
                    if nm.strip():
                        extra_n = {
                            "data_nascimento":     data_nasc_n,
                            "data_batismo":        data_bat_n,
                            "telefone_emergencia": tel_n,
                            "genero":              gen_n,
                            "classe":              cls_n,
                            "cargo":               cgo_n,
                        }
                        atualizar_membro(nm.strip(), ct, novo=True, extra=extra_n)
                        st.success(f"✅ {nm.strip()} adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Informe o nome completo.")

        # ── Sub-aba 3: EXPORTAR ZIP ───────────────────────────────────────────
        with sub_cfg[3]:
            df_ok_zip = (df[(df['mes_referencia'] == mes_sel) &
                            (df['status_validacao'] == "IDENTIFICADO")]
                         if not df.empty else pd.DataFrame())
            if not df_ok_zip.empty and st.button("🚀 GERAR ZIP MENSAL"):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "a") as zf:
                    for _, r in df_ok_zip.iterrows():
                        mi  = membros_db.get(r['nome_oficial'], {})
                        pdf = gerar_pdf_padrao_s21(r['nome_oficial'], r['cat_oficial'],
                                                    pd.DataFrame([r]), membro_info=mi)
                        if pdf:
                            zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf)
                st.download_button("📥 Baixar ZIP", buf.getvalue(),
                                   f"S21_{mes_sel}.zip")

    st.caption("v4.0.0 | Parque Aliança | Gestão Completa")


if __name__ == "__main__":
    main()
