import streamlit as st
import pandas as pd
import json
import datetime
import time
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin - Parque Aliança", layout="wide", page_icon="📊")

# --- LISTA MESTRA DE NOMES E CATEGORIAS (BASEADO NAS SUAS FOTOS) ---
# Aqui incluí a lógica de normalização para corrigir nomes incompletos
NOMES_OFICIAIS = {
    "PIONEIROS REGULARES": [
        "Cintia Aparecida Travaglin", "Diva Cordeiro de Souza", "Edna Alves Secundo",
        "Ivan Rodrigues Vieira da Silva", "Jessica Melo da Silva", "Joselita Maria dos Santos",
        "Katia Almeida Nunes Dantas", "Marcia Rocha de Oliveira", "Maria Dalia Silva Oliveira",
        "Marilele de Andrade e Melo Silva", "Marilene Lopes Araujo", "Miriam Silva Oliveira",
        "Rene Fonseca Cardoso", "Romys Ferreira Primo", "Ruth Almeida Nunes",
        "Sirlene Rodrigues Calado", "Thalita Lopes de Oliveira", "Zelia Pereira Santos",
        "Ana Dilma Cardoso" # Adicionada conforme solicitado
    ],
    "PUBLICADORES": [
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
}

# --- FUNÇÕES DE APOIO ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro ao conectar ao banco de dados: {e}")
            return None
    return st.session_state.db

def carregar_relatorios():
    db = inicializar_db()
    if db:
        docs = db.collection("relatorios_parque_alianca").order_by("data_envio", direction="DESCENDING").stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    return []

def deletar_registro(doc_id):
    db = inicializar_db()
    try:
        db.collection("relatorios_parque_alianca").document(doc_id).delete()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")
        return False

def atualizar_registro(doc_id, novos_dados):
    db = inicializar_db()
    try:
        db.collection("relatorios_parque_alianca").document(doc_id).update(novos_dados)
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
        return False

def sugerir_nome_correto(nome_digitado):
    """Tenta encontrar o nome completo baseado em partes do nome digitado."""
    nome_buscado = nome_digitado.lower()
    todos_nomes = NOMES_OFICIAIS["PIONEIROS REGULARES"] + NOMES_OFICIAIS["PUBLICADORES"]
    for oficial in todos_nomes:
        if nome_buscado in oficial.lower():
            return oficial
    return nome_digitado

# --- INTERFACE ---
def main():
    st.title("📊 Painel de Controle - Admin Parque Aliança")
    
    dados = carregar_relatorios()

    if dados:
        df = pd.DataFrame(dados)
        
        # Filtros e Categorização Visual
        st.sidebar.header("Filtros de Gestão")
        categoria_filtro = st.sidebar.multiselect("Filtrar por Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"], default=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
        
        # --- TABELA PRINCIPAL ---
        st.subheader("Registros Recebidos")
        
        for index, row in df.iterrows():
            with st.expander(f"📌 {row['nome']} - {row['mes_referencia']}"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    novo_nome = st.text_input("Editar Nome:", value=row['nome'], key=f"nome_{row['id']}")
                    if st.button("Corrigir Nome Automaticamente", key=f"btn_corr_{row['id']}"):
                        sugestao = sugerir_nome_correto(novo_nome)
                        st.info(f"Sugestão aplicada: {sugestao}")
                        atualizar_registro(row['id'], {"nome": sugestao})
                        st.rerun()

                with col2:
                    # ITEM 3: Classificação
                    opcoes_cat = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
                    index_cat = opcoes_cat.index(row.get('categoria', "PUBLICADOR")) if row.get('categoria') in opcoes_cat else 0
                    nova_cat = st.selectbox("Classificação:", opcoes_cat, index=index_cat, key=f"cat_{row['id']}")
                
                with col3:
                    st.write(f"**Horas:** {row['horas']}")
                    st.write(f"**Estudos:** {row['estudos_biblicos']}")

                # BOTÕES DE AÇÃO
                c_save, c_del = st.columns(2)
                with c_save:
                    if st.button("💾 Salvar Alterações", key=f"sv_{row['id']}", use_container_width=True):
                        if atualizar_registro(row['id'], {"nome": novo_nome, "categoria": nova_cat}):
                            st.success("Atualizado!")
                            time.sleep(1)
                            st.rerun()
                
                with c_del:
                    # ITEM 1: Deletar
                    if st.button("🗑️ Deletar Registro", key=f"del_{row['id']}", type="secondary", use_container_width=True):
                        if deletar_registro(row['id']):
                            st.warning("Registro removido.")
                            time.sleep(1)
                            st.rerun()

        st.divider()
        # Visualização em Tabela para Exportação
        st.subheader("Visualização em Grade")
        st.dataframe(df, use_container_width=True)

    else:
        st.info("Nenhum relatório encontrado no banco de dados.")

if __name__ == "__main__":
    main()
