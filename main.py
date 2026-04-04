import streamlit as st
import pandas as pd
import json
import datetime
import time
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Parque Aliança", layout="wide", page_icon="📊")

# --- LISTAS OFICIAIS (Baseadas nos seus anexos) ---
LISTA_PIONEIROS_REGULARES = [
    "Ana Dilma Cardoso", "Cintia Aparecida Travaglin", "Diva Cordeiro de Souza", 
    "Edna Alves Secundo", "Ivan Rodrigues Vieira da Silva", "Jessica Melo da Silva", 
    "Joselita Maria dos Santos", "Katia Almeida Nunes Dantas", "Marcia Rocha de Oliveira", 
    "Maria Dalia Silva Oliveira", "Marilele de Andrade e Melo Silva", "Marilene Lopes Araujo", 
    "Miriam Silva Oliveira", "Rene Fonseca Cardoso", "Romys Ferreira Primo", 
    "Ruth Almeida Nunes", "Sirlene Rodrigues Calado", "Thalita Lopes de Oliveira", "Zelia Pereira Santos"
] #

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
        dados = [{"id": doc.id, **doc.to_dict()} for doc in docs]
        return dados
    return []

def atualizar_status(doc_id, nova_categoria):
    db = inicializar_db()
    db.collection("relatorios_parque_alianca").document(doc_id).update({"categoria": nova_categoria})
    st.rerun()

def deletar_registro(doc_id):
    db = inicializar_db()
    db.collection("relatorios_parque_alianca").document(doc_id).delete()
    st.rerun()

# --- AUTOMAÇÃO: CORREÇÃO DE NOME ---
def automacao_corrigir_nome(nome_bruto):
    """Corrige o nome automaticamente sem clique de botão."""
    nome_limpo = nome_bruto.strip().lower()
    # Lista estendida de nomes conhecidos para busca
    todos_nomes_conhecidos = LISTA_PIONEIROS_REGULARES + [
        "Airton Pereira da Silva", "Anderson de Almeida Silva", "Cecilia Geremias Cunha", 
        "Wendley Leite Cunha", "Maria Aparecida Dias"
    ] # Exemplos baseados nas imagens
    
    for oficial in todos_nomes_conhecidos:
        if nome_limpo in oficial.lower():
            return oficial
    return nome_bruto

# --- INTERFACE PRINCIPAL ---
def main():
    st.title("📋 Painel de Gestão de Publicadores")
    
    dados = carregar_dados()
    if not dados:
        st.warning("Nenhum dado encontrado.")
        return

    df = pd.DataFrame(dados)

    # 1. Automação de Nomes no Carregamento
    # Se o nome não estiver no formato oficial, ele sugere a correção silenciosa
    df['nome'] = df['nome'].apply(automacao_corrigir_nome)

    # Garantir que todos tenham uma categoria (Padrão: PUBLICADOR)
    if 'categoria' not in df.columns:
        df['categoria'] = "PUBLICADOR"
    df['categoria'] = df['categoria'].fillna("PUBLICADOR")

    # --- SISTEMA DE ABAS ---
    aba_pub, aba_aux, aba_reg, aba_ina = st.tabs([
        "👥 PUBLICADORES", 
        "🏃 PIONEIROS AUXILIARES", 
        "⭐ PIONEIROS REGULARES", 
        "⚠️ INATIVOS"
    ])

    categorias = {
        "PUBLICADOR": aba_pub,
        "PIONEIRO AUXILIAR": aba_aux,
        "PIONEIRO REGULAR": aba_reg,
        "INATIVO": aba_ina
    }

    for cat_nome, aba_objeto in categorias.items():
        with aba_objeto:
            df_filtro = df[df['categoria'] == cat_nome]
            
            if df_filtro.empty:
                st.write(f"Nenhum registro em {cat_nome}.")
            else:
                for idx, row in df_filtro.iterrows():
                    with st.expander(f"📌 {row['nome']} - {row.get('mes_referencia', 'N/A')}"):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        
                        with c1:
                            st.write(f"**Nome Corrigido:** {row['nome']}")
                            st.caption(f"ID: {row['id']}")
                        
                        with c2:
                            # Mudança de categoria rápida
                            nova_escolha = st.selectbox(
                                "Mover para:", 
                                ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"],
                                index=list(categorias.keys()).index(cat_nome),
                                key=f"sel_{row['id']}"
                            )
                            if nova_escolha != cat_nome:
                                atualizar_status(row['id'], nova_escolha)

                        with c3:
                            if st.button("🗑️ Excluir", key=f"del_{row['id']}"):
                                deletar_registro(row['id'])
                        
                        if cat_nome == "INATIVO":
                            st.error("❗ Este publicador está marcado como INATIVO.")

    # Métrica de Alerta para Inativos na Barra Lateral
    total_inativos = len(df[df['categoria'] == "INATIVO"])
    if total_inativos > 0:
        st.sidebar.error(f"🚨 Alerta: {total_inativos} Publicador(es) Inativo(s)!")

if __name__ == "__main__":
    main()
