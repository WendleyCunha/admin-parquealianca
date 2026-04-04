import streamlit as st

import pandas as pd

import json

import datetime

import time

from google.cloud import firestore

from google.oauth2 import service_account

from io import BytesIO

from reportlab.pdfgen import canvas

from reportlab.lib.pagesizes import letter

from pdfrw import PdfReader, PdfWriter, PageMerge



# --- CONFIGURAÇÃO DA PÁGINA ---

st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")



# --- ESTILIZAÇÃO VISUAL (CARDS) ---

st.markdown("""

    <style>

    .publicador-card {

        background-color: #ffffff;

        padding: 20px;

        border-radius: 12px;

        border-left: 6px solid #002366;

        box-shadow: 0 4px 6px rgba(0,0,0,0.07);

        margin-bottom: 20px;

    }

    .metric-label { color: #64748b; font-size: 0.85rem; font-weight: bold; text-transform: uppercase; }

    .metric-value { color: #1e293b; font-size: 1.1rem; font-weight: bold; margin-bottom: 10px; }

    </style>

""", unsafe_allow_html=True)



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



# --- FUNÇÕES DE NÚCLEO ---

def gerar_pdf_s4t(dados):

    try:

        packet = BytesIO()

        can = canvas.Canvas(packet, pagesize=letter)

        

        # Mapeamento simplificado de Y por mês (Exemplo de calibração para o S-4-T)

        meses_y = {

            "SETEMBRO": 455, "OUTUBRO": 438, "NOVEMBRO": 421, "DEZEMBRO": 404,

            "JANEIRO": 387, "FEVEREIRO": 370, "MARÇO": 353, "ABRIL": 336,

            "MAIO": 319, "JUNHO": 302, "JULHO": 285, "AGOSTO": 268

        }

        

        mes_puro = dados['mes_referencia'].split()[0].upper()

        y = meses_y.get(mes_puro, 100)

        

        can.setFont("Helvetica-Bold", 10)

        if dados['participou_ministerio']:

            can.drawString(168, y, "X")

        

        can.drawString(220, y, str(dados['estudos_biblicos']))

        can.drawString(340, y, str(dados['horas']))

        

        can.save()

        packet.seek(0)

        

        new_pdf = PdfReader(packet)

        existing_pdf = PdfReader("S-4-T_Template.pdf") # O arquivo deve estar na mesma pasta

        output = PdfWriter()

        

        page = existing_pdf.pages[0]

        PageMerge(page).add(new_pdf.pages[0]).render()

        output.addpage(page)

        

        result = BytesIO()

        output.write(result)

        return result.getvalue()

    except Exception as e:

        st.error(f"Erro ao processar template PDF: {e}")

        return None



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

    

    for n in (PIONEIROS_REGULARES + TODOS_PUBLICADORES):

        if nome_original in n.lower():

            nome_oficial = n

            break

            

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



    meses_disponiveis = sorted(df['mes_referencia'].unique())

    mes_selecionado = st.selectbox("📅 Selecione o Mês para Visualizar:", meses_disponiveis, index=len(meses_disponiveis)-1)

    

    df_mes = df[df['mes_referencia'] == mes_selecionado]



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



    aba_pub, aba_aux, aba_reg = st.tabs(["👥 PUBLICADORES", "🏃 PIONEIROS AUXILIARES", "⭐ PIONEIROS REGULARES"])



    categorias_map = {

        "PUBLICADOR": aba_pub,

        "PIONEIRO AUXILIAR": aba_aux,

        "PIONEIRO REGULAR": aba_reg

    }



    for cat, aba in categorias_map.items():

        with aba:

            df_cat = df_mes[df_mes['categoria'] == cat]

            

            col_t1, col_t2, col_t3 = st.columns(3)

            col_t1.metric("Total Relatórios", len(df_cat))

            col_t2.metric("Soma Horas", int(df_cat['horas'].sum()))

            col_t3.metric("Soma Estudos", int(df_cat['estudos_biblicos'].sum()))

            

            st.markdown("---")



            if df_cat.empty:

                st.info(f"Nenhum relatório de {cat} para o mês de {mes_selecionado}.")

            else:

                for _, row in df_cat.iterrows():

                    # --- ESTILO CARD "QUADRADO" ---

                    st.markdown(f"""

                        <div class="publicador-card">

                            <div class="metric-label">Publicador</div>

                            <div class="metric-value">{row['nome']}</div>

                            <div class="metric-label">Status do Mês</div>

                            <div class="metric-value">{'✅ Participou' if row['participou_ministerio'] else '❌ Não participou'}</div>

                        </div>

                    """, unsafe_allow_html=True)

                    

                    with st.expander(f"Detalhes de {row['nome']}"):

                        col_a, col_b = st.columns(2)

                        with col_a:

                            st.write(f"**Horas:** {row['horas']}")

                            st.write(f"**Estudos:** {row['estudos_biblicos']}")

                        with col_b:

                            st.write(f"**Data Envio:** {row['data_envio'].strftime('%d/%m/%Y %H:%M') if hasattr(row['data_envio'], 'strftime') else row['data_envio']}")

                        

                        if row['observacoes']:

                            st.info(f"**Obs:** {row['observacoes']}")

                        

                        # --- BOTÃO DE PDF COM LÓGICA DE DOWNLOAD ---

                        pdf_data = gerar_pdf_s4t(row)

                        if pdf_data:

                            st.download_button(

                                label="🖨️ Baixar PDF S-4-T Preenchido",

                                data=pdf_data,

                                file_name=f"S4T_{row['nome']}_{row['mes_referencia']}.pdf",

                                mime="application/pdf",

                                key=f"pdf_{row['id']}"

                            )



    st.caption("Sistema de Gestão S-4-T | Parque Aliança")



if __name__ == "__main__":

    main()
