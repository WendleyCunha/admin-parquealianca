import streamlit as st
import pandas as pd
import json
import io
import os
import zipfile
import unicodedata
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account

# Bibliotecas para o S-21 Oficial
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# Bibliotecas para os Consolidados (Seus recursos antigos)
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- FUNÇÃO S-21 OFICIAL (ESQUADRO CORRIGIDO) ---
def gerar_pdf_registro_s21(row, mes_sel):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo s21.pdf base não encontrado!")
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # Nome (Ajustado para subir um pouco e alinhar na linha)
    can.setFont("Helvetica-Bold", 11)
    can.drawString(24*mm, 263.5*mm, str(row['nome_oficial']).upper())
    
    # Eixo Y corrigido para bater nos campos do formulário oficial
    y_map = {
        "SETEMBRO": 208.2, "OUTUBRO": 200.2, "NOVEMBRO": 192.2, "DEZEMBRO": 184.2,
        "JANEIRO": 176.2, "FEVEREIRO": 168.2, "MARÇO": 160.2, "ABRIL": 152.2,
        "MAIO": 144.2, "JUNHO": 136.2, "JULHO": 128.2, "AGOSTO": 120.2
    }
    
    mes_nome = str(mes_sel).split()[0].upper()
    y_pos = y_map.get(mes_nome, 152.2) * mm
    
    can.setFont("Helvetica-Bold", 10)
    # Participou (X) - Centralizado no box
    if int(row['horas']) > 0 or int(row['estudos_biblicos']) > 0:
        can.drawCentredString(53.8*mm, y_pos, "X")
    
    # Estudos Bíblicos
    can.drawCentredString(80.8*mm, y_pos, str(int(row['estudos_biblicos'])))
    
    # Pioneiro Auxiliar (X)
    if row['cat_oficial'] == "PIONEIRO AUXILIAR":
        can.drawCentredString(97.8*mm, y_pos, "X")
        
    # Horas
    can.drawCentredString(116.8*mm, y_pos, str(int(row['horas'])))
    
    # Observações
    obs = str(row.get('observacoes', ''))[:40]
    if obs:
        can.setFont("Helvetica", 7)
        can.drawString(133*mm, y_pos + 0.5*mm, obs)
    
    can.save()
    packet.seek(0)

    try:
        with open(path_original, "rb") as f:
            reader_original = PdfReader(f)
            writer = PdfWriter()
            pagina_base = reader_original.pages[0]
            overlay_pdf = PdfReader(packet)
            pagina_base.merge_page(overlay_pdf.pages[0])
            writer.add_page(pagina_base)
            output = io.BytesIO()
            writer.write(output)
            return output.getvalue()
    except Exception as e:
        st.error(f"Erro no merge: {e}")
        return None

# --- FUNÇÃO CONSOLIDADO (RECURSO ANTIGO) ---
def gerar_pdf_consolidado_geral(df_dados, titulo, subtitulo, label, valor):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(titulo, styles['Title']))
    elements.append(Paragraph(f"<b>{label}:</b> {valor} | {subtitulo}", styles['Normal']))
    elements.append(Spacer(1, 12))

    data = [["Mês", "Estudos", "Horas"]] + [[str(r['Mês']), str(int(r['Estudos'])), str(int(r['Horas']))] for _, r in df_dados.iterrows()]
    table = Table(data, colWidths=[200, 100, 100])
    table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()

# --- BANCO DE DADOS ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão: {e}"); return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db(); return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()} if db else {}

def carregar_relatorios():
    db = inicializar_db(); return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()] if db else []

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria, "nome_oficial": nome}, merge=True)

def deletar_relatorio(rel_id):
    db = inicializar_db()
    if db: db.collection("relatorios_parque_alianca").document(rel_id).delete(); st.rerun()

def normalizar_nome_no_banco(nome, lista):
    n_norm = normalizar_texto(nome)
    melhor, score_max = None, 0
    for oficial in lista:
        score = SequenceMatcher(None, n_norm, normalizar_texto(oficial)).ratio()
        if score > score_max: score_max, melhor = score, oficial
    return melhor if score_max >= 0.80 else None

# --- MAIN ---
def main():
    st.title("📊 Gestão Administrativa - Parque Aliança")
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()
    cats = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    
    df = pd.DataFrame(relatorios) if relatorios else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        
        def validar(row):
            oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if oficial: return pd.Series([oficial, membros_db[oficial].get('categoria', 'PUBLICADOR'), "OK"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status']] = df.apply(validar, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses = sorted(df['mes_referencia'].unique()) if not df.empty else ["MAIO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    t_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "⚙️ CONFIG"])

    # ABA 1: RELATÓRIOS
    with t_principal[0]:
        df_ok = df_mes[df_mes['status'] == "OK"]
        entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
        sub_t = st.tabs(cats + ["⏳ PENDÊNCIAS"])
        for i, c in enumerate(cats):
            with sub_t[i]:
                df_c = df_ok[df_ok['cat_oficial'] == c]
                if not df_c.empty:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Envios", len(df_c))
                    m2.metric("Horas", int(df_c['horas'].sum()))
                    m3.metric("Estudos", int(df_c['estudos_biblicos'].sum()))
                    
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_c.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><small>⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}</small></div>', unsafe_allow_html=True)
                            if st.button("🗑️", key=f"del_{r['id']}"): deletar_relatorio(r['id'])

    # ABA 2: TRIAGEM
    with t_principal[1]:
        df_tri = df_mes[df_mes['status'] == "TRIAGEM"]
        if df_tri.empty: st.success("Nomes validados!")
        else:
            for _, r in df_tri.iterrows():
                with st.container(border=True):
                    st.write(f"Digitado: **{r['nome']}**")
                    c1, c2 = st.columns(2)
                    n_f = c1.selectbox("Corrigir para:", ["-- Novo --"] + sorted(membros_db.keys()), key=f"tr_s_{r['id']}")
                    cat_f = c2.selectbox("Categoria:", cats, key=f"tr_c_{r['id']}")
                    if st.button("✅ Validar", key=f"tr_b_{r['id']}"):
                        nome_final = n_f if n_f != "-- Novo --" else r['nome']
                        atualizar_membro(nome_final, cat_f)
                        inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({"nome": nome_final})
                        st.rerun()

    # ABA 3: CONSOLIDADO (RECURSOS ANTIGOS RECUPERADOS)
    with t_principal[2]:
        c_tabs = st.tabs(["📊 CATEGORIA", "👤 INDIVIDUAL"])
        with c_tabs[0]:
            cat_sel = st.selectbox("Escolha a Categoria", cats)
            df_cons = df[(df['status'] == "OK") & (df['cat_oficial'] == cat_sel)]
            if not df_cons.empty:
                res = df_cons.groupby('mes_referencia').agg({'estudos_biblicos':'sum','horas':'sum'}).reset_index()
                res.columns = ['Mês', 'Estudos', 'Horas']
                st.table(res)
                pdf_c = gerar_pdf_consolidado_geral(res, "CONSOLIDADO", "2026", "Categoria", cat_sel)
                st.download_button("📥 Baixar PDF Categoria", pdf_c, f"Consol_{cat_sel}.pdf")

        with c_tabs[1]:
            p_sel = st.selectbox("Publicador", sorted(membros_db.keys()))
            df_p = df[(df['nome_oficial'] == p_sel) & (df['status'] == "OK")]
            if not df_p.empty:
                res_p = df_p.sort_values('mes_referencia')[['mes_referencia','estudos_biblicos','horas']]
                res_p.columns = ['Mês', 'Estudos', 'Horas']
                st.table(res_p)
                pdf_p = gerar_pdf_consolidado_geral(res_p, "CARTÃO DE REGISTRO", "2026", "Membro", p_sel)
                st.download_button("📥 Baixar Histórico PDF", pdf_p, f"S21_Historico_{p_sel}.pdf")

    # ABA 4: CONFIGURAÇÃO E EXPORTAÇÃO S-21
    with t_principal[3]:
        st.subheader("📦 Exportação em Massa (S-21 Oficial)")
        if not df_ok.empty:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a") as zf:
                for _, r in df_ok.iterrows():
                    p = gerar_pdf_registro_s21(r, mes_sel)
                    if p: zf.writestr(f"S21_{r['nome_oficial']}.pdf", p)
            st.download_button("📥 BAIXAR ZIP S-21 OFICIAL", zip_buf.getvalue(), f"S21_Massa_{mes_sel}.zip", use_container_width=True)
        
        st.divider()
        st.subheader("Novos Membros")
        nc1, nc2, nc3 = st.columns([2,1,1])
        nn = nc1.text_input("Nome")
        nct = nc2.selectbox("Cat", cats)
        if nc3.button("Cadastrar"): 
            atualizar_membro(nn, nct); st.rerun()

    st.caption("v2.5.0 | Esquadro S-21 Corrigido + Consolidados Antigos")

if __name__ == "__main__":
    main()
