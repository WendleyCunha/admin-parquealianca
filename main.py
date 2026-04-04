import streamlit as st
import pandas as pd
import json
import datetime
import time
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- LISTAS MESTRAS ---
PIONEIROS_REGULARES = [
    "Ana Dilma Cardoso", "Cintia Aparecida Travaglin", "Diva Cordeiro de Souza", 
    "Edna Alves Secundo", "Ivan Rodrigues Vieira da Silva", "Jessica Melo da Silva", 
    "Joselita Maria dos Santos", "Katia Almeida Nunes Dantas", "Marcia Rocha de Oliveira", 
    "Maria Dalia Silva Oliveira", "Marilele de Andrade e Melo Silva", "Marilene Lopes Araujo", 
    "Miriam Silva Oliveira", "Rene Fonseca Cardoso", "Romys Ferreira Primo", 
    "Ruth Almeida Nunes", "Sirlene Rodrigues Calado", "Thalita Lopes de Oliveira", "Zelia Pereira Santos"
]

TODOS_PUBLICADORES = [
    "Airton Pereira da Silva", "Anderson de Almeida Silva", "Anderson Vieira Dantas",
    "Antonia Cordeiro Silva", "Aparecida Cruz dos Santos", "Ariana Rodrigues Calado Oliveira",
    "Beatriz Dantas dos Santos", "Brenda Vieira Dantas", "Bruno Oliveira da Silva",
    "Cecilia Geremias Cunha", "Celidalva de Souza Santos", "Clauberto de Oliveira Silva",
    "Cosme Ferreira Primo", "Dalva Dias de Queiroz", "Deise Santana Nogueira Fernandes",
    "Doralice Carlos Souza Silva", "Edna Olibeira Sales Gomes", "Edney da Cruz Barbosa",
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

# --- FUNÇÕES DE BANCO DE DADOS ---
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

def carregar_dados():
    db = inicializar_db()
    if db:
        docs = db.collection("relatorios_parque_alianca").stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    return []

# --- LÓGICA DE CATEGORIA E NOME ---
def processar_registro(row):
    nome_original = row['nome'].strip().lower()
    
    # Busca o nome oficial
    nome_oficial = row['nome']
    for n in (PIONEIROS_REGULARES + TODOS_PUBLICADORES):
        if nome_original in n.lower():
            nome_oficial = n
            break
            
    # Atribui Categoria Automática (Item 1)
    if nome_oficial in PIONEIROS_REGULARES:
        categoria = "PIONEIRO REGULAR"
    else:
        # Se não estiver no banco como algo específico, assume Publicador ou mantém a salva
        categoria = row.get('categoria', "PUBLICADOR")
        
    return nome_oficial, categoria

def main():
    st.title("📊 Gestão e Totais - Parque Aliança")
    
    dados_brutos = carregar_dados()
    if not dados_brutos:
        st.info("Aguardando primeiros relatórios...")
        return

    df_recebidos = pd.DataFrame(dados_brutos)
    
    # Aplica processamento automático de nomes e categorias
    df_recebidos[['nome', 'categoria']] = df_recebidos.apply(
        lambda x: pd.Series(processar_registro(x)), axis=1
    )

    # --- 1. PAINEL DE PENDÊNCIAS (Item 2) ---
    st.header("📋 Status de Entrega do Mês")
    nomes_que_entregaram = df_recebidos['nome'].unique()
    lista_completa = list(set(PIONEIROS_REGULARES + TODOS_PUBLICADORES))
    
    pendentes = [n for n in lista_completa if n not in nomes_que_entregaram]
    
    c1, c2 = st.columns(2)
    with c1:
        st.success(f"✅ Entregues: {len(nomes_que_entregaram)}")
    with c2:
        st.error(f"⏳ Pendentes: {len(pendentes)}")
    
    if st.checkbox("Ver lista de quem ainda não enviou"):
        st.write(pendentes)

    st.divider()

    # --- 2. SOMA DE ATIVIDADES POR GRUPO (Item 4) ---
    st.header("📈 Resumo por Categoria")
    grupos = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    cols = st.columns(3)
    
    for i, g in enumerate(grupos):
        df_g = df_recebidos[df_recebidos['categoria'] == g]
        with cols[i]:
            st.subheader(g)
            st.metric("Relatórios", len(df_g))
            st.metric("Total Horas", int(df_g['horas'].sum()))
            st.metric("Total Estudos", int(df_g['estudos_biblicos'].sum()))

    st.divider()

    # --- 3. RESUMO INDIVIDUAL (Item 3) ---
    st.header("📄 Resumo dos Relatórios")
    for idx, row in df_recebidos.iterrows():
        with st.expander(f"📝 {row['nome']} - {row['mes_referencia']}"):
            st.markdown(f"""
            **Categoria:** {row['categoria']} | **Part. Ministério:** {'Sim' if row['participou_ministerio'] else 'Não'}
            
            - **Estudos Bíblicos:** {row['estudos_biblicos']}
            - **Horas:** {row['horas']}
            - **Observações:** {row['observacoes'] if row['observacoes'] else 'Nenhuma'}
            """)
            
            # Aqui no futuro entrará o botão de Gerar PDF (Item 5)
            if st.button("🖨️ Preparar PDF (S-4-T)", key=f"pdf_{row['id']}"):
                st.info("Conectando ao modelo S-4-T para preenchimento...")

if __name__ == "__main__":
    main()
