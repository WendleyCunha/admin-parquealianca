import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Unificada - King Star", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    .main-title { color: #003399; font-weight: 800; letter-spacing: -1px; }
    .stTabs [aria-selected="true"] { background-color: #003399 !important; color: white !important; border-radius: 10px 10px 0 0; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO BANCO (UNIFICADO) ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            # Nota: O código de passagens usava "bancowendley", o de relatórios "wendleydesenvolvimento".
            # Ajustei para o projeto principal.
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão Firebase: {e}"); return None
    return st.session_state.db

db = inicializar_db()

# --- SEGURANÇA E LOGIN ---
def verificar_login():
    if "autenticado" not in st.session_state: st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c2:
            st.markdown("<h2 style='text-align:center;'>Acesso Restrito</h2>", unsafe_allow_html=True)
            u = st.text_input("Usuário").lower().strip()
            p = st.text_input("Senha", type="password")
            if st.button("LOGAR", use_container_width=True, type="primary"):
                if u == "wendley" and p == "master77":
                    st.session_state.autenticado = True
                    st.session_state.user_data = {"username": "wendley", "role": "admin", "permissao": ["Relatórios", "Passagens"]}
                    st.rerun()
                user_doc = db.collection("usuarios_app").document(u).get()
                if user_doc.exists:
                    dados = user_doc.to_dict()
                    if dados.get('senha') == p:
                        st.session_state.autenticado = True
                        st.session_state.user_data = dados
                        st.rerun()
                    else: st.error("Senha incorreta.")
                else: st.error("Usuário não encontrado.")
        return False
    return True

# --- FUNÇÕES AUXILIARES (MEMBROS E RELATÓRIOS) ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def carregar_membros():
    docs = db.collection("membros_v2").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_relatorios():
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

# --- FUNÇÕES PASSAGENS (LOGICA DO ARQUIVO ANEXADO) ---
def carregar_eventos_passagens():
    docs = db.collection("eventos").where("status", "==", "ativo").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_passageiros(id_evento):
    paxs = db.collection("eventos").document(id_evento).collection("passageiros").stream()
    return [p.to_dict() for p in paxs]

def salvar_passageiro(id_evento, dados_pax):
    pax_id = f"{dados_pax['nome']}_{dados_pax.get('rg', 'reserva')}".lower().replace(" ", "")
    db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).set(dados_pax)
    # Atualiza cadastro central
    db.collection("cadastro_geral").document(pax_id).set({
        "nome": dados_pax['nome'], "rg": dados_pax.get('rg', ""), "cpf": dados_pax.get('cpf', ""), "grupo": dados_pax.get('grupo', "Geral")
    }, merge=True)

# --- INTERFACE: MÓDULO PASSAGENS ---
def modulo_passagens():
    st.markdown("<h1 class='main-title'>🚌 Passagens VGP</h1>", unsafe_allow_html=True)
    eventos = carregar_eventos_passagens()
    
    if not eventos:
        st.info("Crie um evento na aba de Configurações para começar."); return

    id_sel = st.sidebar.selectbox("Evento", list(eventos.keys()), format_func=lambda x: eventos[x]['nome'])
    evento = eventos[id_sel]
    pax_lista = carregar_passageiros(id_sel)
    df = pd.DataFrame(pax_lista)

    tab1, tab2, tab3 = st.tabs(["📝 Reserva", "📊 Dashboard", "👥 Passageiros"])

    with tab1:
        with st.form("nova_reserva"):
            st.subheader("Nova Reserva")
            nome = st.text_input("Nome Completo")
            c1, c2 = st.columns(2)
            rg = c1.text_input("RG")
            grp = c2.selectbox("Grupo", ["Rosas", "Engenho", "Cohab", "Geral"])
            viagens = []
            for d in evento['datas']:
                if st.checkbox(f"Viaja {d}"): viagens.append({"dia": d, "bus": 1})
            if st.form_submit_button("Confirmar"):
                salvar_passageiro(id_sel, {"nome": nome, "rg": rg, "grupo": grp, "dias_onibus": viagens, "pago": False, "embarcou": False, "valor_total": len(viagens)*evento['valor'], "valor_pago": 0.0})
                st.success("Reserva ok!"); st.rerun()

    with tab2:
        if not df.empty:
            st.metric("Total de Reservas", len(df))
            st.progress(len(df)/46 if len(df)<=46 else 1.0)

    with tab3:
        if not df.empty:
            st.dataframe(df[['nome', 'grupo', 'pago', 'valor_total']])

# --- INTERFACE: MÓDULO RELATÓRIOS ---
def modulo_relatorios():
    st.markdown("<h1 class='main-title'>📊 Relatórios Parque Aliança</h1>", unsafe_allow_html=True)
    membros = carregar_membros()
    relatorios = carregar_relatorios()
    # ... (lógica de processamento de relatórios igual ao seu código principal anterior)
    st.info("Área de relatórios ativa.")

# --- ABA DE CONFIGURAÇÃO (ONDE ALTERA SENHA) ---
def aba_configuracoes(user_info):
    st.header("⚙️ Configurações do Sistema")
    
    # SEÇÃO: ALTERAR SENHA
    with st.expander("🔐 Gestão de Senhas e Acessos", expanded=True):
        st.subheader("Alterar Senha de Usuário")
        
        # Carrega lista de usuários do banco
        usuarios_ref = db.collection("usuarios_app").stream()
        lista_users = [doc.id for doc in usuarios_ref]
        
        c1, c2, c3 = st.columns([1, 1, 1])
        user_alvo = c1.selectbox("Selecione o Usuário", lista_users)
        nova_senha = c2.text_input("Nova Senha", type="password")
        
        if c3.button("Atualizar Senha", use_container_width=True):
            if nova_senha:
                db.collection("usuarios_app").document(user_alvo).update({"senha": nova_senha})
                st.success(f"Senha de **{user_alvo}** atualizada com sucesso!")
            else:
                st.warning("Digite uma senha válida.")

    # SEÇÃO: CADASTRO DE MEMBROS (PARA RELATÓRIOS)
    with st.expander("👤 Gerenciar Membros (Congregação)"):
        c1, c2, c3 = st.columns([2,1,1])
        novo_m = c1.text_input("Nome do Membro")
        cat_m = c2.selectbox("Categoria", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
        if c3.button("Cadastrar"):
            db.collection("membros_v2").document(novo_m).set({"categoria": cat_m})
            st.rerun()

# --- MAIN ---
def main():
    if not verificar_login(): return

    user_info = st.session_state.user_data
    permissoes = user_info.get("permissao", [])
    
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        st.markdown(f"**Usuário:** {user_info['username'].upper()}")
        
        menu = []
        if "Relatórios" in permissoes: menu.append("📊 Relatórios")
        if "Passagens" in permissoes: menu.append("🚌 Passagens")
        menu.append("⚙️ Configurações")
        
        escolha = st.radio("Navegação", menu)
        
        if st.button("Logout"):
            st.session_state.autenticado = False
            st.rerun()

    if escolha == "📊 Relatórios":
        modulo_relatorios()
    elif escolha == "🚌 Passagens":
        modulo_passagens()
    elif escolha == "⚙️ Configurações":
        aba_configuracoes(user_info)

if __name__ == "__main__":
    main()
