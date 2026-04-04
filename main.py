import streamlit as st
import pandas as pd
import json
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- 1. BASE DE DADOS MESTRA (CONSOLIDADA) ---
LISTA_MESTRA_NOMES = [
    # Pioneiros Regulares
    "Ana Dilma Cardoso", "Cintia Aparecida Travaglin", "Diva Cordeiro de Souza", 
    "Edna Alves Secundo", "Ivan Rodrigues Vieira da Silva", "Jessica Melo da Silva", 
    "Joselita Maria dos Santos", "Katia Almeida Nunes Dantas", "Marcia Rocha de Oliveira", 
    "Maria Dalia Silva Oliveira", "Marilele de Andrade e Melo Silva", "Marilene Lopes Araujo", 
    "Miriam Silva Oliveira", "Rene Fonseca Cardoso", "Romys Ferreira Primo", 
    "Ruth Almeida Nunes", "Sirlene Rodrigues Calado", "Thalita Lopes de Oliveira", "Zelia Pereira Santos",
    # Publicadores (Extraídos das suas listas)
    "Airton Pereira da Silva", "Anderson de Almeida Silva", "Anderson Vieira Dantas",
    "Antonia Cordeiro Silva", "Aparecida Cruz dos Santos", "Ariana Rodrigues Calado Oliveira",
    "Beatriz Dantas dos Santos", "Brenda Vieira Dantas", "Bruno Oliveira da Silva",
    "Cecilia Geremias Cunha", "Celidalva de Souza Santos", "Clauberto de Oliveira Silva",
    "Cosme Ferreira Primo", "Dalva Dias de Queiroz", "Deise Santana Nogueira Fernandes",
    "Doralice Carlos Souza Silva", "Edna Oliveira Sales Gomes", "Edney da Cruz Barbosa",
    "Eduardo Ferreira Fernandes", "Emerson Vieira Dantas", "Franciele Coelho Barbosa",
    "Francisco Antonio da Silva Oliveira", "Francisco das Chagas Oliveira", "Francisco de Assis Angelos",
    "Gabriela Carlos Batista", "Gabriela Pereira Santos", "Giovanna Coelho Barbosa",
    "Heloisa Eduarda Santana Fernandes", "Hosana de Souza Primo", "Jacqueline Melo da Silva",
    "Janete Pereira Oliveira", "Jaqueline Freitas de Souza", "Joaquim Antonio Barbosa",
    "Jose Augusto Silva", "Jose Carlos Alves da Silva", "Jose Claudio de Oliveira Silva",
    "Jose Pereira da Silva", "Jose Severino", "Josefa Santos Araujo", "Joyce Araujo Campos",
    "Julia Melo da Silva", "Juliana Gabriel Pereira Primo", "Julio Cesar da Silva Matos",
    "Kelvin Travaglin Andrade", "Laurinda Cipriano de Souza Oliveira", "Lidiane Maria Rocha Lima",
    "Lucilene Carlos Silva Batista", "Lucilia Cassimiro da Silva", "Manoel Messias Andrade de Oliveira",
    "Maria Almeida Nunes Couto", "Maria Aparecida Coelho F Barbosa", "Maria Aparecida Gonçalves Dias",
    "Maria Elena Oliveira Felipe", "Maria Jussara Vilela Santos", "Maria Lucineide Araujo Silva",
    "Maria Vilma do Nascimento", "Mateus Jean Silva Oliveira", "Olavo Amanço Batista",
    "Pedro Vitor de Queiroz Freitas", "Renato Ferreira Primo", "Roberta Vieira Dantas",
    "Rosemeire Pereira Barauna", "Sebastiao Souza Almeida", "Selma Geremias Cunha",
    "Tiago da Silva Oliveira", "Valdete Carlene Borges", "Vanuza Rocha Silva",
    "Vilma Pereira da Silva", "Wendley Leite Cunha"
]

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
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
    
    # Se o banco estiver vazio, ele popula com os 95+ nomes agora
    if not membros:
        with st.status("Configurando Base de Dados inicial..."):
            for nome in LISTA_MESTRA_NOMES:
                # Lógica inicial: Se já estava na sua lista de pioneiros, mantém, senão Publicador
                categoria = "PIONEIRO REGULAR" if nome in LISTA_MESTRA_NOMES[-19:] else "PUBLICADOR"
                db.collection("membros_v2").document(nome).set({"categoria": categoria})
                membros[nome] = {"categoria": categoria}
    return membros

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

# --- 3. LÓGICA DE INTELIGÊNCIA DE NOMES (FUZZY SEARCH) ---
def normalizar_nome_inteligente(nome_digitado, lista_membros):
    nome_entrada = str(nome_digitado).strip().lower()
    if not nome_entrada: return None
    
    # Busca por correspondência parcial (Ex: "Lopes" encontra "Marilene Lopes Araujo")
    for nome_oficial in lista_membros:
        if nome_entrada in nome_oficial.lower():
            return nome_oficial
    return None

def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()

    if not relatorios:
        st.warning("Nenhum relatório encontrado no banco de dados.")
        return

    df = pd.DataFrame(relatorios)
    
    # Aplica a normalização inteligente em todos os envios
    def processar_envio(row):
        nome_final = normalizar_nome_inteligente(row['nome'], membros_db.keys())
        if nome_final:
            return pd.Series([nome_final, membros_db[nome_final]['categoria'], "OK"])
        else:
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    df[['nome_correto', 'categoria_correta', 'status']] = df.apply(processar_envio, axis=1)

    # Filtro de Mês
    meses = sorted(df['mes_referencia'].unique())
    mes_sel = st.sidebar.selectbox("📅 Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel]

    tab_vis, tab_pend, tab_triagem = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⏳ PENDÊNCIAS", "⚠️ TRIAGEM"])

    # --- ABA 1: RECEBIDOS ---
    with tab_vis:
        df_ok = df_mes[df_mes['status'] == "OK"]
        s_pub, s_aux, s_reg = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        abas = {"PUBLICADOR": s_pub, "PIONEIRO AUXILIAR": s_aux, "PIONEIRO REGULAR": s_reg}
        
        for cat, aba in abas.items():
            with aba:
                df_cat = df_ok[df_ok['categoria_correta'] == cat]
                cols = st.columns(4)
                for i, (_, r) in enumerate(df_cat.iterrows()):
                    with cols[i % 4]:
                        st.markdown(f'<div class="card"><div class="card-header">{r["nome_correto"]}</div><div style="font-size:0.8rem;">⏱️ {r["horas"]}h | 📖 {r["estudos_biblicos"]} Est.</div></div>', unsafe_allow_html=True)

    # --- ABA 2: PENDÊNCIAS (LÓGICA SOLICITADA) ---
    with tab_pend:
        entregaram = df_mes[df_mes['status'] == "OK"]['nome_correto'].unique()
        p_pub, p_aux, p_reg = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        abas_p = {"PUBLICADOR": p_pub, "PIONEIRO AUXILIAR": p_aux, "PIONEIRO REGULAR": p_reg}

        for cat, aba in abas_p.items():
            with aba:
                # Filtra do banco quem é desta categoria e não está na lista de quem entregou
                membros_da_cat = [n for n, d in membros_db.items() if d['categoria'] == cat]
                pendentes = [n for n in membros_da_cat if n not in entregaram]
                
                if not pendentes:
                    st.success(f"Todos os {cat}s entregaram!")
                else:
                    for p_nome in pendentes:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        col1.write(f"❌ {p_nome}")
                        nova_cat = col2.selectbox("Alterar grupo", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(cat), key=f"p_{p_nome}")
                        if col3.button("Salvar", key=f"btn_{p_nome}"):
                            atualizar_membro(p_nome, nova_cat)
                            st.rerun()

    # --- ABA 3: TRIAGEM ---
    with tab_triagem:
        df_erro = df_mes[df_mes['status'] == "TRIAGEM"]
        if df_erro.empty:
            st.info("Nenhum nome desconhecido este mês.")
        else:
            for _, r in df_erro.iterrows():
                st.warning(f"Nome não reconhecido: {r['nome']}")
                if st.button(f"Adicionar {r['nome']} como novo Publicador", key=f"add_{r['id']}"):
                    atualizar_membro(r['nome'], "PUBLICADOR")
                    st.rerun()

if __name__ == "__main__":
    main()
