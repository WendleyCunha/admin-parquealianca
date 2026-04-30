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

# Bibliotecas de Manipulação de PDF (Padrão Oficial)
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# --- CONFIGURAÇÃO E ESTILO (Mantidos) ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- MOTOR DE PREENCHIMENTO PADRÃO (S-21 OFICIAL) ---
def gerar_pdf_padrao(nome_cabecalho, categoria_label, dados_rows):
    """
    Função Única para gerar o PDF Oficial.
    nome_cabecalho: Nome do Publicador ou "PUBLICADORES / PIONEIROS"
    categoria_label: A categoria para o cabeçalho
    dados_rows: Lista de dicionários ou DataFrame com os dados de cada mês
    """
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado.")
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # 1. Cabeçalho Fixo
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24*mm, 258*mm, str(nome_cabecalho).upper())
    
    # 2. Mapeamento de Linhas (Coordenadas Y oficiais)
    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5
    }
    
    # 3. Preenchimento de Múltiplas Linhas (Loop pelos meses fornecidos)
    for _, row in dados_rows.iterrows():
        mes_key = str(row['mes_referencia']).split()[0].upper()
        if mes_key in y_map:
            y_pos = y_map[mes_key] * mm
            
            # Participou (X)
            if int(row.get('horas', 0)) > 0 or int(row.get('estudos_biblicos', 0)) > 0:
                can.drawCentredString(53.5*mm, y_pos, "X")
            
            # Estudos
            can.drawCentredString(80.5*mm, y_pos, str(int(row.get('estudos_biblicos', 0))))
            
            # Auxiliar (X) - Verifica se no mês específico ele foi auxiliar
            if row.get('cat_oficial') == "PIONEIRO AUXILIAR" or categoria_label == "PIONEIROS AUXILIARES":
                can.drawCentredString(97.5*mm, y_pos, "X")
                
            # Horas
            can.drawCentredString(116.5*mm, y_pos, str(int(row.get('horas', 0))))
            
            # Observações (Apenas se houver espaço)
            obs = str(row.get('observacoes', ''))[:30]
            if obs and obs != 'nan':
                can.setFont("Helvetica", 7)
                can.drawString(133*mm, y_pos, obs)
                can.setFont("Helvetica-Bold", 10) # Volta para o padrão

    can.save()
    packet.seek(0)

    # Merge com o PDF Oficial
    reader = PdfReader(open(path_original, "rb"))
    writer = PdfWriter()
    page = reader.pages[0]
    overlay = PdfReader(packet)
    page.merge_page(overlay.pages[0])
    writer.add_page(page)
    
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

# --- FUNÇÕES DE BANCO (Mantidas Integralmente) ---
def inicializar_db():
    if "db" not in st.session_state:
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    docs = db.collection("membros_v2").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_relatorios():
    db = inicializar_db()
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

# --- MAIN APP ---
def main():
    st.title("📊 Gestão Parque Aliança - Unificada")
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()
    df = pd.DataFrame(relatorios) if relatorios else pd.DataFrame()
    
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        df['mes_referencia'] = df['mes_referencia'].str.upper()
        # Lógica de identificação simplificada para o exemplo
        df['nome_oficial'] = df['nome'].apply(lambda x: next((m for m in membros_db if x.lower() in m.lower()), x))
        df['cat_oficial'] = df['nome_oficial'].apply(lambda x: membros_db.get(x, {}).get('categoria', 'PUBLICADOR'))

    tabs = st.tabs(["📋 RELATÓRIOS", "📈 CONSOLIDADO", "⚙️ CONFIG"])

    # ABA CONSOLIDADO (Onde aplicamos o padrão)
    with tabs[1]:
        c_sub1, c_sub2 = st.tabs(["📊 POR CATEGORIA", "👤 POR PESSOA"])
        
        with c_sub1:
            cat_sel = st.selectbox("Escolha a Categoria", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
            df_cat = df[df['cat_oficial'] == cat_sel]
            if not df_cat.empty:
                # Agrupa por mês para o PDF de categoria
                resumo_cat = df_cat.groupby('mes_referencia').agg({'horas': 'sum', 'estudos_biblicos': 'sum'}).reset_index()
                pdf_cat = gerar_pdf_padrao(f"CONSOLIDADO: {cat_sel}ES", cat_sel, resumo_cat)
                st.download_button(f"📥 Baixar S-21 Consolidado ({cat_sel})", pdf_cat, f"Consolidado_{cat_sel}.pdf")
        
        with c_sub2:
            pessoa_sel = st.selectbox("Escolha o Publicador", sorted(list(membros_db.keys())))
            df_pessoa = df[df['nome_oficial'] == pessoa_sel].sort_values('mes_referencia')
            if not df_pessoa.empty:
                st.table(df_pessoa[['mes_referencia', 'horas', 'estudos_biblicos']])
                # Aqui o PDF preenche TODAS as linhas dos meses que ele entregou
                pdf_pessoal = gerar_pdf_padrao(pessoa_sel, membros_db[pessoa_sel].get('categoria'), df_pessoa)
                st.download_button(f"📥 Baixar Cartão S-21: {pessoa_sel}", pdf_pessoal, f"S21_{pessoa_sel}.pdf")

    # ABA CONFIG (Exportação Mensal Unitária)
    with tabs[2]:
        mes_f = st.sidebar.selectbox("Mês de Exportação", df['mes_referencia'].unique() if not df.empty else ["AGOSTO"])
        if st.button("Gerar ZIP Mensal (Todos S-21 Oficiais)"):
            df_mes = df[df['mes_referencia'] == mes_f]
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "a") as zf:
                for _, r in df_mes.iterrows():
                    # Para o unitário, passamos um DataFrame de uma linha só
                    p = gerar_pdf_padrao(r['nome_oficial'], r['cat_oficial'], pd.DataFrame([r]))
                    if p: zf.writestr(f"S21_{r['nome_oficial']}.pdf", p)
            st.download_button("📥 Baixar ZIP", zip_buf.getvalue(), "Massa_S21.zip")

if __name__ == "__main__":
    main()
