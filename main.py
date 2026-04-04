import streamlit as st
import pandas as pd
import json
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- LISTAS MESTRAS BASE ---
PIONEIROS_REGULARES_BASE = [
    "Ana Dilma Cardoso", "Cintia Aparecida Travaglin", "Diva Cordeiro de Souza", 
    "Edna Alves Secundo", "Ivan Rodrigues Vieira da Silva", "Jessica Melo da Silva", 
    "Joselita Maria dos Santos", "Katia Almeida Nunes Dantas", "Marcia Rocha de Oliveira", 
    "Maria Dalia Silva Oliveira", "Marilele de Andrade e Melo Silva", "Marilene Lopes Araujo", 
    "Miriam Silva Oliveira", "Rene Fonseca Cardoso", "Romys Ferreira Primo", 
    "Ruth Almeida Nunes", "Sirlene Rodrigues Calado", "Thalita Lopes de Oliveira", "Zelia Pereira Santos"
]

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 5px solid #002366;
    }
    .card-pendente { border-left: 5px solid #e74a3b; background-color: #fffcfc; }
    .card-inativo { border-left: 5px solid #94a3b8; background-color: #f1f5f9; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE BANCO DE DADOS ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except: return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    if not db: return {}
    docs = db.collection("membros_v2").stream()
    membros = {doc.id: doc.to_dict() for doc in docs}
    if not membros:
        for nome in PIONEIROS_REGULARES_BASE:
            db.collection("membros_v2").document(nome).set({"categoria": "PIONEIRO REGULAR"})
            membros[nome] = {"categoria": "PIONEIRO REGULAR"}
    return membros

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

# --- INTELIGÊNCIA DE NOMES ---
def normalizar_nome(nome_digitado, lista_membros):
    nome_busca = str(nome_digitado).strip().lower()
    for nome_oficial in lista_membros:
        if nome_busca in nome_oficial.lower():
            return nome_oficial
    return nome_digitado

def main():
    st.title("📊 Gestão Parque Aliança")
    
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()
    
    if not relatorios:
        st.info("Aguardando relatórios no banco...")
        return

    df = pd.DataFrame(relatorios)
    
    # Processa nomes e categorias com base na sua gestão manual
    def processar_dados(row):
        nome_corrigido = normalizar_nome(row['nome'], membros_db.keys())
        categoria = membros_db.get(nome_corrigido, {}).get('categoria', 'PUBLICADOR')
        return pd.Series([nome_corrigido, categoria])

    df[['nome', 'categoria']] = df.apply(processar_dados, axis=1)

    meses = sorted(df['mes_referencia'].unique())
    mes_sel = st.sidebar.selectbox("📅 Selecione o Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel]

    tab_recebidos, tab_gestao, tab_inativos = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⚙️ PENDENTES E CLASSIFICAÇÃO", "💤 INATIVOS"])

    # --- ABA 1: RECEBIDOS (GRID LADO A LADO) ---
    with tab_recebidos:
        s_pub, s_aux, s_reg = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        map_abas = {"PUBLICADOR": s_pub, "PIONEIRO AUXILIAR": s_aux, "PIONEIRO REGULAR": s_reg}
        
        for cat_id, aba in map_abas.items():
            with aba:
                df_cat = df_mes[df_mes['categoria'] == cat_id]
                cols = st.columns(4)
                for i, (_, r) in enumerate(df_cat.iterrows()):
                    with cols[i % 4]:
                        st.markdown(f"""<div class="card"><div class="card-header">{r['nome']}</div>
                        <div style='font-size:0.85rem;'>⏱️ {r['horas']}h | 📖 {r['estudos_biblicos']} Est.</div></div>""", unsafe_allow_html=True)

    # --- ABA 2: PENDENTES (ORGANIZADO POR CATEGORIA) ---
    with tab_gestao:
        st.subheader(f"Pendentes de {mes_sel}")
        entregaram = df_mes['nome'].unique()
        
        # Sub-abas dentro de Pendentes
        p_pub, p_aux, p_reg = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        map_pendentes = {"PUBLICADOR": p_pub, "PIONEIRO AUXILIAR": p_aux, "PIONEIRO REGULAR": p_reg}

        for cat_id, aba in map_pendentes.items():
            with aba:
                # Pega membros dessa categoria que não entregaram e não são inativos
                membros_da_cat = [n for n, d in membros_db.items() if d['categoria'] == cat_id]
                lista_pendente = [n for n in membros_da_cat if n not in entregaram]

                if not lista_pendente:
                    st.success(f"Nenhum {cat_id} pendente!")
                else:
                    for p_nome in lista_pendente:
                        c1, c2, c3 = st.columns([2, 2, 1])
                        c1.write(f"⚠️ **{p_nome}**")
                        nova_cat = c2.selectbox("Alterar para:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], 
                                                index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(cat_id), 
                                                key=f"p_sel_{p_nome}")
                        if c3.button("Salvar", key=f"p_btn_{p_nome}"):
                            atualizar_membro(p_nome, nova_cat)
                            st.rerun()

    # --- ABA 3: INATIVOS ---
    with tab_inativos:
        inativos = [n for n, d in membros_db.items() if d['categoria'] == "INATIVO"]
        if not inativos:
            st.info("Nenhum inativo cadastrado.")
        else:
            cols_in = st.columns(4)
            for i, n_in in enumerate(inativos):
                with cols_in[i % 4]:
                    st.markdown(f"""<div class="card card-inativo"><div class="card-header">{n_in}</div></div>""", unsafe_allow_html=True)
                    if st.button(f"Reativar", key=f"re_{n_in}"):
                        atualizar_membro(n_in, "PUBLICADOR")
                        st.rerun()

if __name__ == "__main__":
    main()
