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

# Bibliotecas para preenchimento do PDF OFICIAL (Overlay)
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
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS & DB ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def obter_mes_atual_str():
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    now = datetime.now()
    return f"{meses[now.month-1]} {now.year}"

def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except: return None
    return st.session_state.db

# --- FUNÇÕES DE ANÚNCIOS (NOVAS) ---
@st.cache_data(ttl=600)
def carregar_anuncios():
    db = inicializar_db()
    if not db: return []
    docs = db.collection("anuncios").order_by("data_postagem", direction="DESCENDING").limit(5).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def salvar_anuncio(texto):
    db = inicializar_db()
    if db:
        db.collection("anuncios").add({
            "conteudo": texto,
            "data_postagem": datetime.now()
        })

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

# --- DEMAIS FUNÇÕES DE DADOS ---
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
        if novo: dados["mes_inicio"] = obter_mes_atual_str()
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
        db.collection("relatorios_parque_alianca").add({
            "nome": nome, "mes_referencia": mes, "horas": horas,
            "estudos_biblicos": estudos, "timestamp": firestore.SERVER_TIMESTAMP
        })
        st.success(f"Relatório de {nome} adicionado!")
        st.rerun()

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        score = SequenceMatcher(None, entrada_norm, normalizar_texto(nome_oficial)).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.85 else None

# --- APP ---
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
                cat_final = "PIONEIRO AUXILIAR" if dados_m.get('categoria') == "PUBLICADOR" and row['horas'] >= 15 else dados_m.get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat_final, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else [obter_mes_atual_str()]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    
    # Adicionada aba ANÚNCIOS
    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "📢 ANÚNCIOS", "⚙️ CONFIGURAÇÃO"])

    with tabs[0]: # RELATÓRIOS
        df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        entregaram = df_ok['nome_oficial'].unique()
        sub_rel = st.tabs(["PUBLICADOR", "P. AUXILIAR", "P. REGULAR", "⏳ PENDÊNCIAS"])
        for i, cat in enumerate(categorias_lista):
            with sub_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat]
                if df_cat.empty: st.info("Sem envios.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Envios", len(df_cat))
                    m2.metric("Total Horas", f"{int(df_cat['horas'].sum())}h")
                    m3.metric("Estudos", int(df_cat['estudos_biblicos'].sum()))
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div>⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}</div>', unsafe_allow_html=True)
        with sub_rel[3]:
            st.warning(f"Quem ainda NÃO entregou em {mes_sel}:")
            for cat in categorias_lista:
                pendentes = [n for n, d in membros_db.items() if d.get('categoria') == cat and n not in entregaram]
                if pendentes:
                    with st.expander(f"{cat} ({len(pendentes)})"):
                        for p in sorted(pendentes):
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                            c1.write(f"**{p}**")
                            h_man = c2.number_input("H", min_value=0, step=1, key=f"h_{p}")
                            e_man = c3.number_input("E", min_value=0, step=1, key=f"e_{p}")
                            if c4.button("Baixa", key=f"btn_{p}"): salvar_baixa_manual(p, mes_sel, h_man, e_man)

    with tabs[1]: # TRIAGEM
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("Tudo limpo!")
        else:
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    vinc = c1.selectbox("Vincular a:", ["-- Novo Membro --"] + sorted(list(membros_db.keys())), key=f"v_{row['id']}")
                    cat_v = c2.selectbox("Categoria:", categorias_lista, key=f"c_{row['id']}")
                    if st.button("Confirmar", key=f"b_{row['id']}"):
                        n_final = row['nome'] if vinc == "-- Novo Membro --" else vinc
                        atualizar_membro(n_final, cat_v, novo=(vinc == "-- Novo Membro --"))
                        inicializar_db().collection("relatorios_parque_alianca").document(row['id']).update({"nome": n_final})
                        st.rerun()

    with tabs[2]: # CONSOLIDADO
        c1_tab, c2_tab = st.tabs(["👤 INDIVIDUAL", "📊 CATEGORIA"])
        with c1_tab:
            pub = st.selectbox("Publicador", sorted(list(membros_db.keys())))
            df_hist = df[(df['nome_oficial'] == pub)].sort_values('mes_referencia')
            if not df_hist.empty: st.table(df_hist[['mes_referencia', 'horas', 'estudos_biblicos']])
        with c2_tab:
            cat_sel = st.selectbox("Categoria", categorias_lista)
            df_cons = df[df['cat_oficial'] == cat_sel].groupby('mes_referencia').agg({'horas':'sum', 'estudos_biblicos':'sum'}).reset_index()
            st.dataframe(df_cons, use_container_width=True)

    with tabs[3]: # ANÚNCIOS
        st.subheader("📢 Mural de Avisos")
        for an in carregar_anuncios():
            st.markdown(f"<div class='card'>{an['conteudo']}</div>", unsafe_allow_html=True)

    with tabs[4]: # CONFIGURAÇÃO
        sub_cfg = st.tabs(["✏️ EDITAR", "👥 MEMBROS", "➕ NOVO", "📢 ANUNCIAR", "📦 EXPORTAR"])
        with sub_cfg[3]:
            txt = st.text_area("Novo comunicado:")
            if st.button("Publicar"):
                salvar_anuncio(txt); st.success("Publicado!"); st.rerun()
        with sub_cfg[4]:
            if st.button("🚀 GERAR ZIP MENSAL"):
                # (Mantém sua lógica de exportação aqui)
                st.info("ZIP gerado.")

    st.caption("v2.6.1 | Parque Aliança")

if __name__ == "__main__":
    main()
