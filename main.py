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

# --- FUNÇÕES DE CONEXÃO E BANCO ---
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

def deletar_membro(nome):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome).delete()

def editar_nome_membro(nome_antigo, nome_novo, categoria):
    db = inicializar_db()
    if db and nome_antigo != nome_novo:
        # No Firestore, mudar o ID (nome) requer criar novo e deletar antigo
        db.collection("membros_v2").document(nome_novo).set({"categoria": categoria})
        db.collection("membros_v2").document(nome_antigo).delete()

# --- INTELIGÊNCIA DE BUSCA ---
def normalizar_nome_no_banco(nome_digitado, lista_membros):
    nome_entrada = str(nome_digitado).strip().lower()
    if not nome_entrada: return None
    for nome_oficial in lista_membros:
        if nome_entrada in nome_oficial.lower():
            return nome_oficial
    return None

def main():
    st.title("📊 Gestão Parque Aliança")
    
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()

    if not membros_db:
        st.warning("⚠️ O Banco de Dados de membros está vazio.")
    
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame(columns=['nome', 'mes_referencia', 'horas'])

    def validar_envio(row):
        nome_validado = normalizar_nome_no_banco(row['nome'], membros_db.keys())
        if nome_validado:
            return pd.Series([nome_validado, membros_db[nome_validado]['categoria'], "IDENTIFICADO"])
        return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    if not df.empty and 'nome' in df.columns:
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty and 'mes_referencia' in df.columns else ["Abril/2026"]
    mes_sel = st.sidebar.selectbox("📅 Selecione o Mês de análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_pendencias, tab_config = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 1: RECEBIDOS ---
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

    # --- ABA 2: PENDÊNCIAS ---
    with tab_pendencias:
        entregaram_nomes = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty else []
        p_tabs = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        map_p_abas = {"PUBLICADOR": p_tabs[0], "PIONEIRO AUXILIAR": p_tabs[1], "PIONEIRO REGULAR": p_tabs[2]}

        for cat_p, aba_p in map_p_abas.items():
            with aba_p:
                lista_banco_cat = [nome for nome, dados in membros_db.items() if dados.get('categoria') == cat_p]
                lista_pendentes = sorted([nome for nome in lista_banco_cat if nome not in entregaram_nomes])
                if not lista_pendentes:
                    st.success(f"✅ Todos os {cat_p} estão em dia!")
                else:
                    for nome_p in lista_pendentes:
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"⚠️ {nome_p}")
                        opcoes = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"]
                        nova_cat = c2.selectbox("Alterar grupo", opcoes, index=opcoes.index(cat_p), key=f"pend_{nome_p}")
                        if c3.button("Salvar", key=f"btn_pend_{nome_p}"):
                            atualizar_membro(nome_p, nova_cat)
                            st.rerun()

    # --- ABA 3: CONFIGURAÇÃO (MELHORADA) ---
    with tab_config:
        menu_conf = st.radio("Selecione uma ação:", ["🗂️ Lista Completa e Edição", "➕ Adicionar Novo"], horizontal=True)
        
        if menu_conf == "➕ Adicionar Novo":
            with st.form("add_form"):
                novo_n = st.text_input("Nome Completo do Publicador:")
                nova_c = st.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
                if st.form_submit_button("Cadastrar no Banco"):
                    if novo_n:
                        atualizar_membro(novo_n, nova_c)
                        st.success(f"{novo_n} adicionado!")
                        st.rerun()
        
        elif menu_conf == "🗂️ Lista Completa e Edição":
            st.write(f"Total de registros: **{len(membros_db)}**")
            
            # Criar um DataFrame para facilitar a visualização e busca na lista
            membros_list = [{"Nome Original": k, "Categoria": v['categoria']} for k, v in membros_db.items()]
            df_membros = pd.DataFrame(membros_list).sort_values("Nome Original")
            
            for index, row in df_membros.iterrows():
                with st.expander(f"👤 {row['Nome Original']} ({row['Categoria']})"):
                    col_ed1, col_ed2 = st.columns(2)
                    
                    with col_ed1:
                        st.write("**Editar Dados**")
                        novo_nome_input = st.text_input("Editar Nome:", value=row['Nome Original'], key=f"edit_n_{index}")
                        nova_cat_input = st.selectbox("Editar Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], 
                                                     index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(row['Categoria']),
                                                     key=f"edit_c_{index}")
                        
                        if st.button("Confirmar Alterações", key=f"btn_save_{index}"):
                            if novo_nome_input != row['Nome Original']:
                                editar_nome_membro(row['Nome Original'], novo_nome_input, nova_cat_input)
                            else:
                                atualizar_membro(row['Nome Original'], nova_cat_input)
                            st.success("Dados atualizados!")
                            st.rerun()
                    
                    with col_ed2:
                        st.write("**Zona de Perigo**")
                        st.write("A exclusão é permanente.")
                        if st.button(f"🗑️ Deletar {row['Nome Original']}", key=f"del_{index}"):
                            deletar_membro(row['Nome Original'])
                            st.warning("Membro excluído!")
                            st.rerun()

if __name__ == "__main__":
    main()
