import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Unificada - Wendley", layout="wide", page_icon="📊")

# --- CONEXÃO FIREBASE ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            # Usando o projeto principal para usuários
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão: {e}"); return None
    return st.session_state.db

db = inicializar_db()

# --- SISTEMA DE USUÁRIOS ---
def verificar_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.user_data = None

    if not st.session_state.autenticado:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c2:
            st.markdown("<br><br><h2 style='text-align:center;'>Acesso Administrativo</h2>", unsafe_allow_html=True)
            user_input = st.text_input("Usuário").lower().strip()
            senha_input = st.text_input("Senha", type="password")
            
            if st.button("LOGAR", use_container_width=True, type="primary"):
                # Login Master (Backup)
                if user_input == "wendley" and senha_input == "master77":
                    st.session_state.autenticado = True
                    st.session_state.user_data = {"nome": "Wendley", "permissao": ["Relatórios", "Passagens"], "role": "admin"}
                    st.rerun()
                
                # Busca no Banco
                user_doc = db.collection("usuarios_app").document(user_input).get()
                if user_doc.exists:
                    dados = user_doc.to_dict()
                    if dados['senha'] == senha_input:
                        st.session_state.autenticado = True
                        st.session_state.user_data = dados
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado.")
        return False
    return True

# --- FUNÇÕES DE ADMINISTRAÇÃO ---
def criar_usuario(username, senha, permissoes):
    db.collection("usuarios_app").document(username.lower()).set({
        "username": username.lower(),
        "senha": senha,
        "permissao": permissoes,
        "role": "user"
    })

def excluir_usuario(username):
    db.collection("usuarios_app").document(username).delete()

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    </style>
""", unsafe_allow_html=True)

# --- LÓGICA DO MAIN ---
def main():
    if not verificar_login():
        st.stop()

    user_info = st.session_state.user_data
    
    # MENU LATERAL DINÂMICO
    with st.sidebar:
        st.title(f"Olá, {user_info['username'].capitalize()}")
        opcoes_menu = []
        if "Relatórios" in user_info['permissao']: opcoes_menu.append("📊 Gestão Parque Aliança")
        if "Passagens" in user_info['permissao']: opcoes_menu.append("🎫 Sistema de Passagens")
        
        app_mode = st.radio("Navegar para:", opcoes_menu)
        
        st.divider()
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    # --- ROTEAMENTO ---
    if app_mode == "📊 Gestão Parque Aliança":
        exibir_parque_alianca()
    elif app_mode == "🎫 Sistema de Passagens":
        from passagens import exibir_modulo_passagens # Assumindo que o código está em passagens.py
        exibir_modulo_passagens()

def exibir_parque_alianca():
    st.title("📊 Gestão Parque Aliança")
    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⚙️ CONFIGURAÇÃO"])

    with tabs[2]:
        st.subheader("Configurações do Sistema")
        
        # SESSÃO DE GERENCIAMENTO DE USUÁRIOS (SÓ ADMIN)
        if st.session_state.user_data.get('role') == 'admin' or st.session_state.user_data['username'] == 'wendley':
            with st.expander("🔐 Gestão de Usuários e Acessos", expanded=False):
                col_c1, col_c2 = st.columns(2)
                
                with col_c1:
                    st.markdown("### Criar Novo Usuário")
                    new_user = st.text_input("Novo Usuário").lower().strip()
                    new_pass = st.text_input("Senha Inicial", type="password")
                    perms = st.multiselect("Acessos", ["Relatórios", "Passagens"])
                    if st.button("Cadastrar Usuário"):
                        if new_user and new_pass and perms:
                            criar_usuario(new_user, new_pass, perms)
                            st.success(f"Usuário {new_user} criado!")
                        else:
                            st.warning("Preencha todos os campos.")

                with col_c2:
                    st.markdown("### Usuários Ativos")
                    usuarios = db.collection("usuarios_app").stream()
                    for u in usuarios:
                        dados = u.to_dict()
                        c_u1, c_u2 = st.columns([3, 1])
                        c_u1.write(f"👤 {dados['username']} ({', '.join(dados['permissao'])})")
                        if c_u2.button("Excluir", key=f"del_{dados['username']}"):
                            excluir_usuario(dados['username'])
                            st.rerun()

        st.divider()
        st.write("Outras configurações de exportação...")
        # (Aqui entra seu código de download de ZIP que já existia)

# --- EXECUÇÃO ---
if __name__ == "__main__":
    main()
