import streamlit as st
import pandas as pd
import json
import datetime
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin - Parque Aliança", layout="wide")

# --- CONEXÃO COM FIRESTORE ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            # Certifique-se de configurar a Secret 'textkey' também neste novo App no Streamlit Cloud
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
        try:
            # Busca todos da coleção 'relatorios_parque_alianca'
            docs = db.collection("relatorios_parque_alianca").order_by("data_envio", direction="DESCENDING").stream()
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
    return []

# --- INTERFACE ---
def main():
    st.title("📊 Painel de Controle - Relatórios Recebidos")
    st.write("Acesso restrito ao administrador do sistema.")

    # Carregamento dos dados
    with st.spinner("Buscando dados no Firebase..."):
        dados = carregar_relatorios()

    if dados:
        df = pd.DataFrame(dados)
        
        # Formata a data para leitura humana
        if "data_envio" in df.columns:
            df["data_envio"] = pd.to_datetime(df["data_envio"]).dt.strftime('%d/%m/%Y %H:%M')

        # Filtros rápidos na barra lateral
        st.sidebar.header("Filtros")
        filtro_nome = st.sidebar.text_input("Filtrar por nome:")
        
        if filtro_nome:
            df = df[df['nome'].str.contains(filtro_nome, case=False)]

        # --- MÉTRICAS RÁPIDAS ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Relatórios", len(df))
        c2.metric("Total de Estudos", int(df['estudos_biblicos'].sum()))
        c3.metric("Relatórios Pendentes PDF", len(df[df['status_pdf'] == 'PENDENTE']))

        st.divider()

        # --- TABELA DE DADOS ---
        # Definindo as colunas que você quer visualizar
        colunas_exibir = ["data_envio", "nome", "mes_referencia", "participou_ministerio", "estudos_biblicos", "horas", "status_pdf"]
        st.dataframe(df[colunas_exibir], use_container_width=True)

        # --- AÇÕES ---
        st.subheader("⚙️ Ações")
        
        col_down, col_pdf = st.columns(2)
        
        with col_down:
            # Exportar para Excel/CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Dados (CSV)",
                data=csv,
                file_name=f"relatorios_alianca_{datetime.date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col_pdf:
            if st.button("🚀 Iniciar Processamento de PDFs", use_container_width=True, type="primary"):
                st.info("Função em desenvolvimento: No próximo passo vamos conectar o preenchimento automático do S-4-T.")

    else:
        st.warning("Ainda não há dados registrados na coleção 'relatorios_parque_alianca'.")

if __name__ == "__main__":
    main()
