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
# CSS PREMIUM (Estilização consolidada)
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    [data-testid="stAppViewContainer"] { background-color: #f8fafc; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #00112b 0%, #001f5e 100%); color: white; }
    
    /* Métricas */
    .mbox { background: white; padding: 20px; border-radius: 12px; border-top: 4px solid #002d80; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); text-align: center; }
    .mnum { font-size: 1.8rem; font-weight: 800; color: #001a4d; }
    .mlbl { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Cards */
    .rcard { background: white; padding: 15px; border-radius: 10px; border-left: 4px solid #002d80; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .bulk-bar { background: #002d80; color: white; padding: 10px 20px; border-radius: 8px; font-weight: 600; margin-bottom: 10px; }
    
    #MainMenu, footer, .stDeployButton { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÕES DE DADOS E CACHE (Lógica Funcional)
# ============================================================

def inicializar_db():
    if 'db' not in st.session_state:
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        st.session_state.db = firestore.Client(credentials=creds)
    return st.session_state.db

@st.cache_data(ttl=600)
def carregar_membros():
    db = inicializar_db()
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}

@st.cache_data(ttl=600)
def carregar_relatorios():
    db = inicializar_db()
    return [{**doc.to_dict(), "id": doc.id} for doc in db.collection("relatorios_parque_alianca").stream()]

def normalizar_texto(texto):
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def calcular_score_match(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    melhor_match, maior_score = None, 0.0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score:
            maior_score, melhor_match = score, nome_oficial
    return melhor_match, maior_score

def processar_df(relatorios_brutos, membros_db):
    df = pd.DataFrame(relatorios_brutos)
    df['horas'] = pd.to_numeric(df.get('horas', 0), errors='coerce').fillna(0)
    df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
    
    def validar(row):
        match, score = calcular_score_match(row['nome'], list(membros_db.keys()))
        if score >= 0.75: # Threshold otimizado
            cat = membros_db[match].get('categoria', 'PUBLICADOR')
            return pd.Series([match, cat, "IDENTIFICADO"])
        return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
    
    df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar, axis=1)
    return df

# ============================================================
# APP PRINCIPAL (Estrutura de Visualização)
# ============================================================

def main():
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()
    df = processar_df(relatorios, membros_db)
    
    st.sidebar.title("⛪ Parque Aliança")
    mes_sel = st.sidebar.selectbox("Mês de Análise", sorted(df['mes_referencia'].unique(), reverse=True))
    
    if st.sidebar.button("🔄 Atualizar"):
        st.cache_data.clear()
        st.rerun()

    st.title(f"Gestão - {mes_sel}")
    
    # Aba de Relatórios Premium
    tab1, tab2 = st.tabs(["📋 Relatórios", "⚠️ Triagem"])
    
    with tab1:
        df_mes = df[df['mes_referencia'] == mes_sel]
        df_ok = df_mes[df_mes['status_validacao'] == 'IDENTIFICADO']
        
        # Métricas Dashboard
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="mbox"><div class="mnum">{len(df_ok)}</div><div class="mlbl">Total Enviados</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="mbox"><div class="mnum">{int(df_ok["horas"].sum())}</div><div class="mlbl">Horas Totais</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="mbox"><div class="mnum">{int(df_ok["estudos_biblicos"].sum())}</div><div class="mlbl">Estudos</div></div>', unsafe_allow_html=True)
        
        st.divider()
        
        for _, r in df_ok.iterrows():
            st.markdown(f"""
            <div class="rcard">
                <strong>{r['nome_oficial']}</strong> · {int(r['horas'])}h · {r['cat_oficial']}
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        df_triagem = df_mes[df_mes['status_validacao'] == 'TRIAGEM']
        st.write(f"Itens pendentes: {len(df_triagem)}")
        st.dataframe(df_triagem[['nome', 'horas', 'estudos_biblicos']], use_container_width=True)

if __name__ == "__main__":
    main()
