import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account

# Bibliotecas para o S-21 Oficial (Overlay)
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# Bibliotecas para os Consolidados (Tabelas dinâmicas)
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- FUNÇÃO MESTRA: PREENCHER PDF S-21 OFICIAL ---
def gerar_pdf_registro_s21(row, mes_sel):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # Nome (Ajustado para o formulário)
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24*mm, 258*mm, str(row['nome_oficial']).upper())
    
    # Mapeamento do Eixo Y (Coordenadas enviadas por você)
    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5
    }
    
    mes_nome = str(mes_sel).split()[0].upper()
    y_pos = y_map.get(mes_nome, 148.5) * mm
    
    if int(row['horas']) > 0 or int(row['estudos_biblicos']) > 0:
        can.drawCentredString(53.5*mm, y_pos, "X")
    
    can.drawCentredString(80.5*mm, y_pos, str(int(row['estudos_biblicos'])))
    
    if row['cat_oficial'] == "PIONEIRO AUXILIAR":
        can.drawCentredString(97.5*mm, y_pos, "X")
        
    can.drawCentredString(116.5*mm, y_pos, str(int(row['horas'])))
    
    obs = str(row.get('observacoes', ''))[:30]
    if obs:
        can.setFont("Helvetica", 8)
        can.drawString(133*mm, y_pos, obs)
    
    can.save()
    packet.seek(0)

    try:
        reader_original = PdfReader(open(path_original, "rb"))
        writer = PdfWriter()
        pagina_base = reader_original.pages[0]
        overlay_pdf = PdfReader(packet)
        pagina_base.merge_page(overlay_pdf.pages[0])
        writer.add_page(pagina_base)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
    except Exception as e:
        st.error(f"Erro no PDF: {e}")
        return None

# --- FUNÇÃO PARA CONSOLIDADO (Recurso antigo recuperado) ---
def gerar_pdf_consolidado(df_dados, titulo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(titulo, styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Cabeçalho da Tabela
    data = [["Mês", "Estudos", "Horas"]]
    for _, r in df_dados.iterrows():
        data.append([str(r['mes_referencia']), str(int(r['estudos_biblicos'])), str(int(r['horas']))])
    
    t = Table(data, colWidths=[200, 100, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(t)
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
    db = inicializar_db()
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()} if db else {}

def carregar_relatorios():
    db = inicializar_db()
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()] if db else []

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
            # Lógica de match corrigida do seu código
            nomes_existentes = list(membros_db.keys())
            oficial = next((n for n in nomes_existentes if normalizar_texto(n) == normalizar_texto(row['nome'])), None)
            if not oficial:
                # Fallback para SequenceMatcher se não for exato
                for n in nomes_existentes:
                    if SequenceMatcher(None, normalizar_texto(n), normalizar_texto(row['nome'])).ratio() > 0.8:
                        oficial = n; break
            
            if oficial:
                return pd.Series([oficial, membros_db[oficial].get('categoria', 'PUBLICADOR'), "OK"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status']] = df.apply(validar, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    t_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "⚙️ CONFIG"])

    # ABA 1: RELATÓRIOS
    with t_principal[0]:
        df_ok = df_mes[df_mes['status'] == "OK"]
        sub_t = st.tabs(cats + ["⏳ PENDÊNCIAS"])
        for i, c in enumerate(cats):
            with sub_t[i]:
                df_c = df_ok[df_ok['cat_oficial'] == i] # Ajuste se for índice ou nome
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

    # ABA 3: CONSOLIDADO (Recuperado)
    with t_principal[2]:
        st.subheader("Análise Individual e Histórica")
        p_sel = st.selectbox("Selecione o Publicador", sorted(membros_db.keys()))
        df_p = df[df['nome_oficial'] == p_sel].sort_values('mes_referencia')
        if not df_p.empty:
            st.table(df_p[['mes_referencia', 'horas', 'estudos_biblicos']])
            
            # Exportação Individual S-21 Oficial
            pdf_ind = gerar_pdf_registro_s21(df_p[df_p['mes_referencia'] == mes_sel].iloc[0], mes_sel) if not df_p[df_p['mes_referencia'] == mes_sel].empty else None
            if pdf_ind:
                st.download_button(f"📥 Baixar S-21 Oficial ({mes_sel})", pdf_ind, f"S21_{p_sel}.pdf")

    # ABA 4: CONFIG E EXPORTAÇÃO ZIP
    with t_principal[3]:
        st.subheader("Exportação em Massa")
        if not df_ok.empty:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a") as zf:
                for _, r in df_ok.iterrows():
                    p = gerar_pdf_registro_s21(r, mes_sel)
                    if p: zf.writestr(f"S21_{r['nome_oficial']}.pdf", p)
            st.download_button("📥 BAIXAR TUDO ZIP (S-21 OFICIAL)", zip_buf.getvalue(), f"S21_Massa_{mes_sel}.zip", use_container_width=True)

if __name__ == "__main__":
    main()
