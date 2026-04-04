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



def processar_registro(row):

    nome_original = str(row['nome']).strip().lower()

    nome_oficial = row['nome']

    

    # Busca automática na lista oficial

    for n in (PIONEIROS_REGULARES + TODOS_PUBLICADORES):

        if nome_original in n.lower():

            nome_oficial = n

            break

            

    # Classificação Automática (Ponto 1)

    if nome_oficial in PIONEIROS_REGULARES:

        categoria = "PIONEIRO REGULAR"

    else:

        categoria = row.get('categoria', "PUBLICADOR")

        

    return nome_oficial, categoria



def main():

    st.title("📊 Painel Administrativo - Parque Aliança")

    

    dados_brutos = carregar_dados()

    if not dados_brutos:

        st.info("Aguardando primeiros relatórios...")

        return



    df = pd.DataFrame(dados_brutos)

    df[['nome', 'categoria']] = df.apply(lambda x: pd.Series(processar_registro(x)), axis=1)



    # --- FILTRO POR MÊS (Ponto 2) ---

    meses_disponiveis = sorted(df['mes_referencia'].unique())

    mes_selecionado = st.selectbox("📅 Selecione o Mês para Visualizar:", meses_disponiveis, index=len(meses_disponiveis)-1)

    

    df_mes = df[df['mes_referencia'] == mes_selecionado]



    # --- STATUS DE ENTREGA ---

    st.divider()

    entregaram = df_mes['nome'].unique()

    lista_total = list(set(PIONEIROS_REGULARES + TODOS_PUBLICADORES))

    pendentes = [n for n in lista_total if n not in entregaram]



    c1, c2, c3 = st.columns(3)

    c1.metric("Entregues", len(entregaram))

    c2.metric("Pendentes", len(pendentes))

    c3.metric("Mês Filtrado", mes_selecionado)



    if st.checkbox("Ver lista de nomes pendentes"):

        st.warning(f"Total de {len(pendentes)} pessoas ainda não enviaram o relatório em {mes_selecionado}:")

        st.write(", ".join(pendentes))



    st.divider()



    # --- 3 ABAS POR CATEGORIA (Ponto 1 e 2) ---

    aba_pub, aba_aux, aba_reg = st.tabs(["👥 PUBLICADORES", "🏃 PIONEIROS AUXILIARES", "⭐ PIONEIROS REGULARES"])



    categorias_map = {

        "PUBLICADOR": aba_pub,

        "PIONEIRO AUXILIAR": aba_aux,

        "PIONEIRO REGULAR": aba_reg

    }



    for cat, aba in categorias_map.items():

        with aba:

            df_cat = df_mes[df_mes['categoria'] == cat]

            

            # Totais do Grupo (Ponto 4 do pedido anterior mantido)

            col_t1, col_t2, col_t3 = st.columns(3)

            col_t1.metric("Total Relatórios", len(df_cat))

            col_t2.metric("Soma Horas", int(df_cat['horas'].sum()))

            col_t3.metric("Soma Estudos", int(df_cat['estudos_biblicos'].sum()))

            

            st.markdown("---")



            if df_cat.empty:

                st.info(f"Nenhum relatório de {cat} para o mês de {mes_selecionado}.")

            else:

                # Cada um "dentro do seu quadrado" (Cards Individuais)

                for _, row in df_cat.iterrows():

                    with st.expander(f"📋 {row['nome']}"):

                        col_a, col_b = st.columns(2)

                        with col_a:

                            st.write(f"**Participou:** {'Sim' if row['participou_ministerio'] else 'Não'}")

                            st.write(f"**Horas:** {row['horas']}")

                        with col_b:

                            st.write(f"**Estudos:** {row['estudos_biblicos']}")

                            st.write(f"**Data Envio:** {row['data_envio'].strftime('%d/%m/%Y %H:%M') if hasattr(row['data_envio'], 'strftime') else row['data_envio']}")

                        

                        if row['observacoes']:

                            st.info(f"**Obs:** {row['observacoes']}")

                        

                        if st.button("🖨️ Gerar PDF S-4-T", key=f"pdf_{row['id']}"):

                            st.write("Em breve: Preenchimento automático do arquivo...")



    st.caption("Sistema de Gestão S-4-T | Parque Aliança")



if __name__ == "__main__":

    main()
