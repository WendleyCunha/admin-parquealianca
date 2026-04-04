import streamlit as st
import pandas as pd
import json
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE CONEXÃO ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")
            return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    if not db: return {}
    # Busca TODOS os membros cadastrados no banco
    docs = db.collection("membros_v2").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

# --- INTELIGÊNCIA DE BUSCA ---
def normalizar_nome_no_banco(nome_digitado, lista_membros):
    """Busca se o que foi digitado existe dentro de algum nome oficial do banco."""
    nome_entrada = str(nome_digitado).strip().lower()
    if not nome_entrada: return None
    
    for nome_oficial in lista_membros:
        if nome_entrada in nome_oficial.lower():
            return nome_oficial
    return None

def main():
    st.title("📊 Gestão Parque Aliança")
    
    # 1. Carrega dados do Banco (Zero nomes no código)
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()

    if not membros_db:
        st.warning("⚠️ O Banco de Dados de membros está vazio. Adicione membros na aba 'Gestão'.")
    
    if not relatorios_brutos:
        st.info("Aguardando os primeiros relatórios...")
        # Mesmo sem relatórios, precisamos processar para mostrar as pendências
        df = pd.DataFrame(columns=['nome', 'mes_referencia', 'horas'])
    else:
        df = pd.DataFrame(relatorios_brutos)

    # 2. Processamento de Identificação
    # Criamos colunas baseadas na validação contra o banco de dados
    def validar_envio(row):
        nome_validado = normalizar_nome_no_banco(row['nome'], membros_db.keys())
        if nome_validado:
            return pd.Series([nome_validado, membros_db[nome_validado]['categoria'], "IDENTIFICADO"])
        return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    if not df.empty:
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)

    # 3. Filtro de Mês
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["Março/2026"] # Default caso vazio
    mes_sel = st.sidebar.selectbox("📅 Selecione o Mês de análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_pendencias, tab_config = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 1: RECEBIDOS (Quem já enviou e foi identificado) ---
    with tab_recebidos:
        if df_mes.empty:
            st.write("Nenhum relatório para este mês.")
        else:
            df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
            sub_tabs = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
            map_abas = {"PUBLICADOR": sub_tabs[0], "PIONEIRO AUXILIAR": sub_tabs[1], "PIONEIRO REGULAR": sub_tabs[2]}
            
            for cat, aba in map_abas.items():
                with aba:
                    df_cat = df_ok[df_ok['cat_oficial'] == cat]
                    cols = st.columns(4)
                    for i, (_, r) in enumerate(df_cat.iterrows()):
                        with cols[i % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {r["horas"]}h</div></div>', unsafe_allow_html=True)

    # --- ABA 2: PENDÊNCIAS (A lógica que você pediu) ---
    with tab_pendencias:
        st.subheader(f"Não enviaram relatório em: {mes_sel}")
        
        # Quem já entregou este mês (nomes oficiais)
        entregaram_nomes = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty else []
        
        p_tabs = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        map_p_abas = {"PUBLICADOR": p_tabs[0], "PIONEIRO AUXILIAR": p_tabs[1], "PIONEIRO REGULAR": p_tabs[2]}

        for cat_p, aba_p in map_p_abas.items():
            with aba_p:
                # Pega todos os membros desta categoria no banco que NÃO estão na lista de quem entregou
                lista_banco_cat = [nome for nome, dados in membros_db.items() if dados['categoria'] == cat_p]
                lista_pendentes = [nome for nome in lista_banco_cat if nome not in entregaram_nomes]
                
                if not lista_pendentes:
                    st.success(f"✅ Todos os {cat_p} estão em dia!")
                else:
                    for nome_p in lista_pendentes:
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"⚠️ {nome_p}")
                        nova_cat = c2.selectbox("Alterar para:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(cat_p), key=f"sel_{nome_p}")
                        if c3.button("Atualizar", key=f"btn_{nome_p}"):
                            atualizar_membro(nome_p, nova_cat)
                            st.rerun()

    # --- ABA 3: CONFIGURAÇÃO (Para você gerenciar o banco) ---
    with tab_config:
        st.subheader("Gerenciar Banco de Membros")
        with st.expander("➕ Adicionar Novo Membro Manualmente"):
            novo_n = st.text_input("Nome Completo:")
            nova_c = st.selectbox("Categoria Inicial:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
            if st.button("Cadastrar no Banco"):
                atualizar_membro(novo_n, nova_c)
                st.success("Cadastrado!")
                st.rerun()
        
        st.write("---")
        st.write(f"Total de membros cadastrados no banco: **{len(membros_db)}**")

if __name__ == "__main__":
    main()
