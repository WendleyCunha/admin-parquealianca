import streamlit as st
import pandas as pd
import json
import io
import unicodedata
from datetime import datetime
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Unificada - King Star", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .main-title { color: #003399; font-weight: 800; letter-spacing: -1px; }
    .stTabs [aria-selected="true"] { background-color: #003399 !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO BANCO ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            # Definido como o servidor principal unificado
            st.session_state.db = firestore.Client(credentials=creds, project="bancowendley")
        except Exception as e:
            st.error(f"Erro de conexão Firebase: {e}")
            return None
    return st.session_state.db

db = inicializar_db()

# --- SEGURANÇA E LOGIN ---
def verificar_login():
    if "autenticado" not in st.session_state: 
        st.session_state.autenticado = False
        st.session_state.user_data = {}
    
    if not st.session_state.autenticado:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c2:
            st.markdown("<h2 style='text-align:center;'>Acesso Restrito</h2>", unsafe_allow_html=True)
            u = st.text_input("Usuário").lower().strip()
            p = st.text_input("Senha", type="password")
            if st.button("LOGAR", use_container_width=True, type="primary"):
                # Login Master
                if u == "wendley" and p == "master77":
                    st.session_state.autenticado = True
                    st.session_state.user_data = {"username": "wendley", "permissao": ["Relatórios", "Passagens"]}
                    st.rerun()
                
                # Login via Banco
                user_doc = db.collection("usuarios_app").document(u).get()
                if user_doc.exists:
                    dados = user_doc.to_dict()
                    if dados.get('senha') == p:
                        st.session_state.autenticado = True
                        st.session_state.user_data = dados
                        st.session_state.user_data['username'] = u
                        st.rerun()
                    else: st.error("Senha incorreta.")
                else: st.error("Usuário não encontrado.")
        return False
    return True

# --- MÓDULO PASSAGENS (LOGICA REVISADA) ---
def carregar_eventos_passagens():
    docs = db.collection("eventos").where("status", "==", "ativo").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_passageiros(id_evento):
    paxs = db.collection("eventos").document(id_evento).collection("passageiros").stream()
    return [p.to_dict() for p in paxs]

def salvar_pax(id_ev, dados):
    pax_id = f"{dados['nome']}_{dados.get('rg', 'reserva')}".lower().replace(" ", "")
    db.collection("eventos").document(id_ev).collection("passageiros").document(pax_id).set(dados)

def modulo_passagens():
    st.markdown("<h1 class='main-title'>🚌 Passagens VGP</h1>", unsafe_allow_html=True)
    eventos = carregar_eventos_passagens()
    
    if not eventos:
        st.info("Nenhum evento ativo. Crie um em Configurações."); return

    id_sel = st.sidebar.selectbox("Selecione o Evento", list(eventos.keys()), format_func=lambda x: eventos[x]['nome'])
    evento = eventos[id_sel]
    pax_lista = carregar_passageiros(id_sel)
    
    # Criar DataFrame com proteção contra colunas ausentes
    df = pd.DataFrame(pax_lista)
    colunas_finais = ['nome', 'grupo', 'pago', 'valor_total']
    for col in colunas_finais:
        if col not in df.columns: df[col] = "" if col != 'pago' else False

    t1, t2, t3 = st.tabs(["📝 Reserva", "📊 Dashboard", "👥 Lista"])

    with t1:
        with st.form("f_reserva"):
            nome = st.text_input("Nome")
            rg = st.text_input("RG")
            grp = st.selectbox("Grupo", ["Rosas", "Engenho", "Cohab", "Geral"])
            viagens = []
            for d in evento.get('datas', []):
                if st.checkbox(f"Viaja {d}"): viagens.append({"dia": d, "bus": 1})
            if st.form_submit_button("Confirmar Reserva"):
                if nome and viagens:
                    val = len(viagens) * evento['valor']
                    salvar_pax(id_sel, {"nome": nome, "rg": rg, "grupo": grp, "dias_onibus": viagens, "pago": False, "valor_total": val})
                    st.success("Salvo!"); st.rerun()

    with t2:
        st.metric("Total de Reservas", len(df))
        st.progress(min(len(df)/46, 1.0))

    with t3:
        st.dataframe(df[colunas_finais], use_container_width=True)

# --- MÓDULO RELATÓRIOS ---
def modulo_relatorios():
    st.markdown("<h1 class='main-title'>📊 Relatórios Parque Aliança</h1>", unsafe_allow_html=True)
    st.info("Módulo de relatórios sincronizado com o banco 'bancowendley'.")

# --- CONFIGURAÇÕES ---
def aba_configuracoes(user_info):
    st.header("⚙️ Painel de Controle")
    
    with st.expander("🔐 Alterar Senhas de Acesso", expanded=True):
        users_ref = db.collection("usuarios_app").stream()
        lista_users = [doc.id for doc in users_ref]
        
        c1, c2, c3 = st.columns(3)
        alvo = c1.selectbox("Usuário", lista_users)
        nova_s = c2.text_input("Nova Senha", type="password")
        if c3.button("Atualizar Senha"):
            if nova_s:
                db.collection("usuarios_app").document(alvo).update({"senha": nova_s})
                st.success("Senha alterada!")
            else: st.warning("Digite a senha.")

# --- MAIN ---
def main():
    if not verificar_login(): return

    user = st.session_state.user_data
    permissoes = user.get("permissao", ["Passagens"]) # Fallback para Passagens
    
    with st.sidebar:
        st.markdown(f"### Olá, {user['username'].upper()}")
        menu = []
        if "Relatórios" in permissoes: menu.append("Relatórios")
        if "Passagens" in permissoes: menu.append("Passagens")
        menu.append("Configurações")
        
        escolha = st.radio("Navegação", menu)
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    if escolha == "Relatórios": modulo_relatorios()
    elif escolha == "Passagens": modulo_passagens()
    else: aba_configuracoes(user)

if __name__ == "__main__":
    main()
