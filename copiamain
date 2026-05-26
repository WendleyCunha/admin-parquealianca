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
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    .anuncio-preview { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 8px; background: #f8fafc; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def obter_mes_atual_str():
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    now = datetime.now()
    return f"{meses[now.month-1]} {now.year}"

# --- MOTOR DE PDF ---
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
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5
    }

    for _, row in dados_rows.iterrows():
        mes_key = str(row['mes_referencia']).split()[0].upper()
        if mes_key in y_map:
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

# --- BANCO DE DADOS ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except:
            return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    if not db: return {}
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()]

def atualizar_membro(nome, categoria, novo=False):
    db = inicializar_db()
    if db:
        dados = {"categoria": categoria, "nome_oficial": nome}
        if novo:
            dados["mes_inicio"] = obter_mes_atual_str()
        db.collection("membros_v2").document(nome).set(dados, merge=True)

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório Deletado!")
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
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.85 else None

# ─────────────────────────────────────────────
# FUNÇÕES DE ANÚNCIOS
# ─────────────────────────────────────────────

def carregar_anuncios():
    db = inicializar_db()
    if not db: return []
    try:
        docs = db.collection("anuncios") \
                 .order_by("data_postagem", direction=firestore.Query.DESCENDING) \
                 .stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception as e:
        st.warning(f"Erro ao carregar anúncios: {e}")
        return []

def salvar_anuncio(dados):
    db = inicializar_db()
    if not db: return False
    dados["data_postagem"] = firestore.SERVER_TIMESTAMP
    db.collection("anuncios").add(dados)
    return True

def deletar_anuncio(anuncio_id):
    db = inicializar_db()
    if db:
        db.collection("anuncios").document(anuncio_id).delete()
        st.toast("✅ Anúncio deletado!")
        st.rerun()

# ─────────────────────────────────────────────
# GERADOR DE HTML DA AGENDA
# ─────────────────────────────────────────────

def gerar_html_agenda(d):
    """
    Gera HTML da agenda de reunião no estilo do Manual da Congregação JW.
    d = dicionário com: data_texto, escritura, cantico_abertura, cantico_meio,
        cantico_final, tesouros (list), ministerio (list), vida_crista (list)
    Cada item de lista: {"num": int, "titulo": str, "duracao": str}
    """
    C_CANT  = "#1a78b4"   # azul-teal para cânticos e links
    C_TES   = "#1a3566"   # azul-escuro: cabeçalho TESOUROS
    C_TES_I = "#1a5fa8"   # azul médio: itens TESOUROS
    C_MIN   = "#8a6200"   # âmbar escuro: cabeçalho MINISTÉRIO
    C_MIN_I = "#a07800"   # âmbar médio: itens MINISTÉRIO
    C_NVC   = "#cc0000"   # vermelho: cabeçalho NOSSA VIDA CRISTÃ
    C_NVC_I = "#1a5fa8"   # azul médio: itens NVC (igual ao workbook)

    def row(num, titulo, duracao, bg, cor_item):
        if not str(titulo).strip():
            return ""
        dur = f'<br><span style="font-size:12px;color:#888;margin-left:4px;">({duracao})</span>' if str(duracao).strip() else ""
        return (f'<div style="padding:6px 14px;background:{bg};border-bottom:1px solid #e8e8e8;">'
                f'<span style="color:{cor_item};font-weight:bold;">{num}. {titulo}</span>{dur}'
                f'</div>')

    def sec_header(texto, bg):
        return (f'<div style="background:{bg};color:white;padding:9px 14px;'
                f'font-weight:bold;font-size:14.5px;letter-spacing:0.3px;">'
                f'{texto}</div>')

    html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;'
        'border:1px solid #ccc;border-radius:10px;overflow:hidden;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.12);margin:auto;">'
    )

    # ── Cabeçalho ──
    html += f'<div style="padding:12px 14px 8px;background:#ffffff;">'
    html += f'<div style="font-size:19px;font-weight:bold;color:#111;">{d.get("data_texto","")}</div>'
    if d.get("escritura"):
        html += f'<div style="color:{C_CANT};font-size:13px;font-weight:bold;margin-top:2px;">{d["escritura"]}</div>'
    html += '</div>'
    html += '<hr style="margin:0;border:0;border-top:1px solid #ddd;">'

    # ── Abertura ──
    if d.get("cantico_abertura"):
        html += (f'<div style="padding:7px 14px;font-size:13px;background:#fff;">'
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_abertura"]}</span>'
                 f' e oração | <strong>Comentários iniciais</strong> (1 min)</div>')

    # ── TESOUROS ──
    html += '<div style="margin-top:8px;">'
    html += sec_header("TESOUROS DA PALAVRA DE DEUS", C_TES)
    for it in d.get("tesouros", []):
        html += row(it["num"], it["titulo"], it.get("duracao",""), "#f0f4ff", C_TES_I)
    html += '</div>'

    # ── FAÇA SEU MELHOR ──
    html += '<div style="margin-top:8px;">'
    html += sec_header("FAÇA SEU MELHOR NO MINISTÉRIO", C_MIN)
    for it in d.get("ministerio", []):
        html += row(it["num"], it["titulo"], it.get("duracao",""), "#fffcf0", C_MIN_I)
    html += '</div>'

    # ── NOSSA VIDA CRISTÃ ──
    html += '<div style="margin-top:8px;">'
    html += sec_header("NOSSA VIDA CRISTÃ", C_NVC)
    if d.get("cantico_meio"):
        html += (f'<div style="padding:6px 14px;background:#fff5f5;border-bottom:1px solid #e8e8e8;">'
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_meio"]}</span></div>')
    for it in d.get("vida_crista", []):
        html += row(it["num"], it["titulo"], it.get("duracao",""), "#fff5f5", C_NVC_I)
    html += '</div>'

    # ── Encerramento ──
    if d.get("cantico_final"):
        html += (f'<hr style="margin:0;border:0;border-top:1px solid #ddd;">'
                 f'<div style="padding:9px 14px;font-size:13px;background:#fff;">'
                 f'<strong>Comentários finais</strong> (3 min) | '
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_final"]}</span>'
                 f' e oração</div>')

    html += '</div>'
    return html

# ─────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────

def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    meses_referencia_ordem = ["SETEMBRO 2025", "OUTUBRO 2025", "NOVEMBRO 2025", "DEZEMBRO 2025",
                               "JANEIRO 2026", "FEVEREIRO 2026", "MARÇO 2026", "ABRIL 2026", "MAIO 2026"]

    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)

        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial:
                dados_m = membros_db[nome_oficial]
                cat_original = dados_m.get('categoria', 'PUBLICADOR')
                cat_final = "PIONEIRO AUXILIAR" if cat_original == "PUBLICADOR" and row['horas'] >= 15 else cat_original
                return pd.Series([nome_oficial, cat_final, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else [obter_mes_atual_str()]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)

    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "📢 ANÚNCIOS", "⚙️ CONFIGURAÇÃO"])

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
                                f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div>'
                                f'⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}</div>',
                                unsafe_allow_html=True)

        with sub_rel[3]:
            st.warning(f"Quem ainda NÃO entregou em {mes_sel}:")
            idx_mes_sel = meses_referencia_ordem.index(mes_sel) if mes_sel in meses_referencia_ordem else 99
            for cat in categorias_lista:
                pendentes = []
                for n, d_m in membros_db.items():
                    inicio = d_m.get('mes_inicio', 'SETEMBRO 2025')
                    idx_ini = meses_referencia_ordem.index(inicio) if inicio in meses_referencia_ordem else 0
                    if d_m.get('categoria') == cat and n not in entregaram and idx_mes_sel >= idx_ini:
                        pendentes.append(n)
                if pendentes:
                    with st.expander(f"{cat} ({len(pendentes)})"):
                        for p in sorted(pendentes):
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                            c1.write(f"**{p}**")
                            h_manual = c2.number_input("H", min_value=0, step=1, key=f"h_man_{p}_{mes_sel}")
                            e_manual = c3.number_input("E", min_value=0, step=1, key=f"e_man_{p}_{mes_sel}")
                            if c4.button("Dar Baixa", key=f"btn_man_{p}_{mes_sel}"):
                                salvar_baixa_manual(p, mes_sel, h_manual, e_manual)

    # ── ABA 1: TRIAGEM ─────────────────────────────────────────────────────────
    with tabs[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty:
            st.success("Tudo limpo!")
        else:
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.write(f"**Digitado:** {row['nome']} | **Horas:** {row['horas']}")
                    nomes_db = sorted(list(membros_db.keys()))
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_db)
                    idx_sug = nomes_db.index(sugestao) + 1 if sugestao else 0
                    c1, c2 = st.columns(2)
                    vincular = c1.selectbox("Vincular a:", ["-- Novo Membro --"] + nomes_db, index=idx_sug, key=f"v_{row['id']}")
                    cat_v = c2.selectbox("Categoria:", categorias_lista, key=f"c_{row['id']}")
                    if st.button("Confirmar", key=f"b_{row['id']}"):
                        nome_final = row['nome'] if vincular == "-- Novo Membro --" else vincular
                        atualizar_membro(nome_final, cat_v, novo=(vincular == "-- Novo Membro --"))
                        inicializar_db().collection("relatorios_parque_alianca").document(row['id']).update({"nome": nome_final})
                        st.rerun()

    # ── ABA 2: CONSOLIDADO ─────────────────────────────────────────────────────
    with tabs[2]:
        c1_tab, c2_tab = st.tabs(["👤 INDIVIDUAL (HISTÓRICO)", "📊 CATEGORIA"])
        with c1_tab:
            publicador = st.selectbox("Escolha o Publicador", sorted(list(membros_db.keys())))
            if publicador:
                df_hist = df[(df['nome_oficial'] == publicador) & (df['status_validacao'] == "IDENTIFICADO")].sort_values('mes_referencia')
                if not df_hist.empty:
                    st.table(df_hist[['mes_referencia', 'horas', 'estudos_biblicos']])
                    pdf = gerar_pdf_padrao_s21(publicador, membros_db[publicador].get('categoria'), df_hist)
                    st.download_button("📥 Baixar Cartão S-21 Completo", pdf, f"S21_{publicador}.pdf")

        with c2_tab:
            cat_sel = st.selectbox("Consolidado por Categoria", categorias_lista)
            df_cons = df[(df['status_validacao'] == "IDENTIFICADO") & (df['cat_oficial'] == cat_sel)]
            if not df_cons.empty:
                resumo = df_cons.groupby('mes_referencia').agg(
                    {'id': 'count', 'horas': 'sum', 'estudos_biblicos': 'sum'}
                ).reset_index().rename(columns={'id': 'relatorios_enviados', 'horas': 'total_horas', 'estudos_biblicos': 'total_estudos'})
                st.dataframe(resumo, use_container_width=True)
                pdf_c = gerar_pdf_padrao_s21(
                    f"CONSOLIDADO {cat_sel}S", cat_sel,
                    resumo.rename(columns={'total_horas': 'horas', 'total_estudos': 'estudos_biblicos'})
                )
                st.download_button(f"📥 Baixar Cartão {cat_sel}", pdf_c, f"S21_Consolidado_{cat_sel}.pdf")

    # ══════════════════════════════════════════════════════════════════════════
    # ── ABA 3: ANÚNCIOS ───────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    with tabs[3]:
        sub_an = st.tabs(["✏️ Nova Postagem", "🗂️ Gerenciar Postagens"])

        # ── Sub-aba: Nova Postagem ──────────────────────────────────────────
        with sub_an[0]:
            tipo = st.radio(
                "Tipo de postagem",
                ["📝 Texto / Markdown", "🖼️ Imagem (JPEG/PNG)", "📅 Agenda de Reunião"],
                horizontal=True
            )

            # ── TEXTO / MARKDOWN ──────────────────────────────────────────
            if tipo == "📝 Texto / Markdown":
                st.info("Use Markdown: **negrito**, *itálico*, listas com `-`, títulos com `#`.")
                titulo_txt = st.text_input("Título do anúncio (opcional)")
                conteudo_md = st.text_area("Conteúdo", height=200, placeholder="Digite o texto do anúncio aqui...")
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

            # ── IMAGEM ────────────────────────────────────────────────────
            elif tipo == "🖼️ Imagem (JPEG/PNG)":
                titulo_img = st.text_input("Legenda / Título da imagem (opcional)")
                arquivo = st.file_uploader("Enviar imagem", type=["jpg", "jpeg", "png"])
                if arquivo:
                    st.image(arquivo, caption=titulo_img or "Pré-visualização", use_column_width=True)
                    if st.button("📤 Publicar Imagem", use_container_width=True):
                        img_bytes = arquivo.read()
                        mime = "image/png" if arquivo.name.endswith(".png") else "image/jpeg"
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        # Gerar HTML com a imagem embutida
                        html_img = (
                            f'<div style="text-align:center;padding:10px;">'
                            f'<img src="data:{mime};base64,{b64}" style="max-width:100%;border-radius:8px;" />'
                            + (f'<p style="margin-top:8px;color:#555;font-size:14px;">{titulo_img}</p>' if titulo_img else "")
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

            # ── AGENDA DE REUNIÃO ─────────────────────────────────────────
            elif tipo == "📅 Agenda de Reunião":
                st.markdown("#### 📋 Preencha a Agenda")

                col_a, col_b = st.columns(2)
                data_texto = col_a.text_input("📅 Período", placeholder="18-24 DE MAIO")
                escritura  = col_b.text_input("📖 Escritura", placeholder="ISAÍAS 62-64")

                col_c, col_d, col_e = st.columns(3)
                cant_ab  = col_c.text_input("🎵 Cântico Abertura", placeholder="44")
                cant_meio = col_d.text_input("🎵 Cântico NVC",      placeholder="115")
                cant_fin  = col_e.text_input("🎵 Cântico Final",    placeholder="151")

                st.markdown("---")

                # ── Seção 1: TESOUROS ──
                st.markdown(
                    '<div style="background:#1a3566;color:white;padding:7px 12px;'
                    'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                    'TESOUROS DA PALAVRA DE DEUS</div>', unsafe_allow_html=True
                )
                n_tes = st.number_input("Nº de itens", 1, 6, 3, key="n_tes",
                                        help="Quantos itens nesta seção?")
                tesouros = []
                for i in range(int(n_tes)):
                    c1, c2 = st.columns([4, 1])
                    t = c1.text_input(f"Item {i+1}", key=f"tes_t_{i}", label_visibility="collapsed",
                                      placeholder=f"Item {i+1} – Título")
                    d_dur = c2.text_input("Dur.", key=f"tes_d_{i}", label_visibility="collapsed",
                                          placeholder="10 min")
                    tesouros.append({"num": i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")

                # ── Seção 2: FAÇA SEU MELHOR ──
                st.markdown(
                    '<div style="background:#8a6200;color:white;padding:7px 12px;'
                    'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                    'FAÇA SEU MELHOR NO MINISTÉRIO</div>', unsafe_allow_html=True
                )
                n_min = st.number_input("Nº de itens", 1, 6, 3, key="n_min")
                ministerio = []
                base_min = int(n_tes)
                for i in range(int(n_min)):
                    c1, c2 = st.columns([4, 1])
                    t = c1.text_input(f"Item {base_min+i+1}", key=f"min_t_{i}",
                                      label_visibility="collapsed",
                                      placeholder=f"Item {base_min+i+1} – Título")
                    d_dur = c2.text_input("Dur.", key=f"min_d_{i}", label_visibility="collapsed",
                                          placeholder="")
                    ministerio.append({"num": base_min + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")

                # ── Seção 3: NOSSA VIDA CRISTÃ ──
                st.markdown(
                    '<div style="background:#cc0000;color:white;padding:7px 12px;'
                    'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                    'NOSSA VIDA CRISTÃ</div>', unsafe_allow_html=True
                )
                n_nvc = st.number_input("Nº de itens", 1, 10, 2, key="n_nvc")
                vida_crista = []
                base_nvc = int(n_tes) + int(n_min)
                for i in range(int(n_nvc)):
                    c1, c2 = st.columns([4, 1])
                    t = c1.text_input(f"Item {base_nvc+i+1}", key=f"nvc_t_{i}",
                                      label_visibility="collapsed",
                                      placeholder=f"Item {base_nvc+i+1} – Título")
                    d_dur = c2.text_input("Dur.", key=f"nvc_d_{i}", label_visibility="collapsed",
                                          placeholder="30 min" if i == int(n_nvc)-1 else "")
                    vida_crista.append({"num": base_nvc + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")

                agenda_dados = {
                    "data_texto": data_texto,
                    "escritura": escritura,
                    "cantico_abertura": cant_ab,
                    "cantico_meio": cant_meio,
                    "cantico_final": cant_fin,
                    "tesouros": tesouros,
                    "ministerio": ministerio,
                    "vida_crista": vida_crista,
                }

                col_prev, col_pub = st.columns(2)

                with col_prev:
                    if st.button("👁️ Pré-visualizar", use_container_width=True):
                        html_agenda = gerar_html_agenda(agenda_dados)
                        st.markdown(html_agenda, unsafe_allow_html=True)

                with col_pub:
                    if st.button("📤 Publicar Agenda", use_container_width=True, type="primary"):
                        if not data_texto.strip():
                            st.error("Informe o período da semana.")
                        else:
                            html_agenda = gerar_html_agenda(agenda_dados)
                            salvar_anuncio({
                                "tipo": "agenda",
                                "titulo": data_texto,
                                "conteudo_html": html_agenda,
                                "renderizar_markdown": False,
                                "dados_agenda": agenda_dados,
                            })
                            st.success(f"✅ Agenda '{data_texto}' publicada!")
                            st.rerun()

        # ── Sub-aba: Gerenciar Postagens ────────────────────────────────────
        with sub_an[1]:
            anuncios = carregar_anuncios()
            if not anuncios:
                st.info("Nenhuma postagem encontrada.")
            else:
                st.caption(f"{len(anuncios)} postagem(ns) encontrada(s) • mais recente primeiro")
                for a in anuncios:
                    tipo_icon = {"texto": "📝", "imagem": "🖼️", "agenda": "📅"}.get(a.get("tipo",""), "📌")
                    titulo_a  = a.get("titulo", "Sem título")
                    ts = a.get("data_postagem")
                    data_str = ts.strftime("%d/%m/%Y %H:%M") if hasattr(ts, "strftime") else "–"

                    with st.expander(f"{tipo_icon} {titulo_a}  ·  {data_str}"):
                        # Pré-visualização
                        if a.get("renderizar_markdown"):
                            st.markdown(a.get("conteudo_html", ""), unsafe_allow_html=False)
                        else:
                            st.markdown(a.get("conteudo_html", ""), unsafe_allow_html=True)

                        st.markdown("---")
                        if st.button(f"🗑️ Deletar esta postagem", key=f"del_an_{a['id']}",
                                     type="secondary"):
                            deletar_anuncio(a["id"])

    # ── ABA 4: CONFIGURAÇÃO ────────────────────────────────────────────────────
    with tabs[4]:
        sub_cfg = st.tabs(["✏️ EDITAR RELATÓRIOS", "👥 GERENCIAR MEMBROS", "➕ NOVO MEMBRO", "📦 EXPORTAR ZIP"])

        with sub_cfg[0]:
            if not df.empty:
                df_ok_mes = df[(df['mes_referencia'] == mes_sel) & (df['status_validacao'] == "IDENTIFICADO")]
                for _, r in df_ok_mes.sort_values('nome_oficial').iterrows():
                    with st.expander(f"📝 {r['nome_oficial']} ({int(r['horas'])}h)"):
                        ce1, ce2, ce3 = st.columns([2, 1, 1])
                        idx_cat = categorias_lista.index(r['cat_oficial']) if r['cat_oficial'] in categorias_lista else 0
                        nova_cat = ce1.selectbox("Categoria", categorias_lista, index=idx_cat, key=f"e_c_{r['id']}")
                        novas_h  = ce2.number_input("Horas", value=int(r['horas']), key=f"e_h_{r['id']}")
                        novos_e  = ce3.number_input("Estudos", value=int(r['estudos_biblicos']), key=f"e_e_{r['id']}")
                        if st.button("Salvar Alterações", key=f"s_b_{r['id']}"):
                            inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update(
                                {"horas": novas_h, "estudos_biblicos": novos_e})
                            atualizar_membro(r['nome_oficial'], nova_cat)
                            st.rerun()
                        if st.button("Deletar Relatório", key=f"del_{r['id']}"):
                            deletar_relatorio(r['id'])

        with sub_cfg[1]:
            for nome in sorted(membros_db.keys()):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"**{nome}**")
                    cat_gravada = membros_db[nome].get('categoria', 'PUBLICADOR')
                    if cat_gravada not in categorias_lista:
                        cat_gravada = "PUBLICADOR"
                    idx_m = categorias_lista.index(cat_gravada)
                    nova_c = c2.selectbox("Alterar", categorias_lista, index=idx_m, key=f"cfg_{nome}")
                    if c3.button("Atualizar", key=f"btn_up_{nome}"):
                        atualizar_membro(nome, nova_c)
                        st.toast("Atualizado!")

        with sub_cfg[2]:
            with st.form("novo_membro"):
                nm, ct = st.text_input("Nome Completo"), st.selectbox("Categoria", categorias_lista)
                if st.form_submit_button("Adicionar"):
                    if nm:
                        atualizar_membro(nm, ct, novo=True)
                        st.rerun()

        with sub_cfg[3]:
            df_ok_zip = df[(df['mes_referencia'] == mes_sel) & (df['status_validacao'] == "IDENTIFICADO")] if not df.empty else pd.DataFrame()
            if not df_ok_zip.empty and st.button("🚀 GERAR ZIP MENSAL"):
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "a") as zf:
                    for _, r in df_ok_zip.iterrows():
                        pdf = gerar_pdf_padrao_s21(r['nome_oficial'], r['cat_oficial'], pd.DataFrame([r]))
                        zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf)
                st.download_button("📥 Baixar ZIP", buf.getvalue(), f"S21_{mes_sel}.zip")

    st.caption("v3.0.0 | Parque Aliança | Gestão Completa")


if __name__ == "__main__":
    main()
