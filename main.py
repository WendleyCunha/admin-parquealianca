import streamlit as st
import pandas as pd
import json
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- LISTAS MESTRAS INICIAIS (USADAS CASO O BANCO ESTEJA VAZIO) ---
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
    .card-inativo { border-left: 5px solid #94a3b8; background-color: #f1f5f9; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-bottom: 5px; }
    .card-data { font-size: 0.85rem; color: #475569; }
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
    
    # Se o banco estiver vázio, popula com a lista de Pioneiros Regulares base
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

# --- LÓGICA DE INTELIGÊNCIA DE NOMES ---
def normalizar_nome(nome_digitado, lista_membros):
    """
    Se a pessoa digitar 'REne', o sistema busca na lista de membros 
    cadastrados o nome oficial 'Rene Fonseca Cardoso'.
    """
    nome_busca = str(nome_digitado).strip().lower()
    for nome_oficial in lista_membros:
        if nome_busca in nome_oficial.lower():
            return nome_oficial
    return nome_digitado

def main():
    st.title("📊 Gestão Inteligente - Parque Aliança")
    
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    
    if not relatorios_brutos:
        st.info("Aguardando relatórios...")
        return

    # Processamento de Dados
    df = pd.DataFrame(relatorios_brutos)
    
    # APLICA A LÓGICA DE NOME AUTOMÁTICO E CATEGORIA DO BANCO
    def processar_cada_linha(row):
        nome_corrigido = normalizar_nome(row['nome'], membros_db.keys())
        # Se o nome corrigido existe no banco, assume a categoria do banco (Prioridade)
        categoria = membros_db.get(nome_corrigido, {}).get('categoria', 'PUBLICADOR')
        return pd.Series([nome_corrigido, categoria])

    df[['nome', 'categoria']] = df.apply(processar_cada_linha, axis=1)

    # Filtro de Mês
    meses = sorted(df['mes_referencia'].unique())
    mes_sel = st.sidebar.selectbox("📅 Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel]

    tab_vis, tab_gestao, tab_inativos = st.tabs(["📋 RELATÓRIOS", "⚙️ PENDENTES E CLASSIFICAÇÃO", "💤 INATIVOS"])

    # --- ABA 1: VISUALIZAÇÃO EM CARDS QUADRADOS ---
    with tab_vis:
        sub_pub, sub_aux, sub_reg = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        mapeamento = {"PUBLICADOR": sub_pub, "PIONEIRO AUXILIAR": sub_aux, "PIONEIRO REGULAR": sub_reg}
        
        for cat_id, aba in mapeamento.items():
            with aba:
                df_cat = df_mes[df_mes['categoria'] == cat_id]
                cols = st.columns(4)
                for i, (_, r) in enumerate(df_cat.iterrows()):
                    with cols[i % 4]:
                        st.markdown(f"""
                            <div class="card">
                                <div class="card-header">{r['nome']}</div>
                                <div class="card-data">
                                    ⏱️ {r['horas']}h | 📖 {r['estudos_biblicos']} Est.<br>
                                    { '✅ Participou' if r['participou_ministerio'] else '❌ Não Participou' }
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

    # --- ABA 2: PENDENTES E GESTÃO DE CLASSIFICAÇÃO ---
    with tab_gestao:
        st.subheader("Lista de Pendentes e Ajuste de Grupo")
        entregaram = df_mes['nome'].unique()
        # Filtra apenas quem NÃO é inativo
        ativos = [n for n, d in membros_db.items() if d['categoria'] != "INATIVO"]
        pendentes = [n for n in ativos if n not in entregaram]

        for p_nome in pendentes:
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{p_nome}**")
                
                cat_atual = membros_db[p_nome]['categoria']
                opcoes = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"]
                
                nova_cat = c2.selectbox("Mover para:", opcoes, index=opcoes.index(cat_atual), key=f"gest_{p_nome}")
                
                if c3.button("Atualizar", key=f"btn_{p_nome}"):
                    atualizar_membro(p_nome, nova_cat)
                    st.success(f"{p_nome} agora é {nova_cat}")
                    st.rerun()

    # --- ABA 3: INATIVOS ---
    with tab_inativos:
        inativos = [n for n, d in membros_db.items() if d['categoria'] == "INATIVO"]
        if not inativos:
            st.info("Nenhum inativo.")
        else:
            cols_in = st.columns(4)
            for i, n_in in enumerate(inativos):
                with cols_in[i % 4]:
                    st.markdown(f"""<div class="card card-inativo"><div class="card-header">{n_in}</div></div>""", unsafe_allow_html=True)
                    if st.button(f"Reativar {n_in.split()[0]}", key=f"re_{n_in}"):
                        atualizar_membro(n_in, "PUBLICADOR")
                        st.rerun()

if __name__ == "__main__":
    main()
