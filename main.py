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

    # Processamento de Dados
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame(columns=['nome', 'mes_referencia', 'horas'])

    if not df.empty and 'nome' in df.columns:
        def validar_envio(row):
            nome_validado = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_validado:
                return pd.Series([nome_validado, membros_db[nome_validado].get('categoria', 'PUBLICADOR'), "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)

    # Filtro Global de Mês
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty and 'mes_referencia' in df.columns else ["Abril/2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_pendencias, tab_config = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 1: RECEBIDOS ---
    with tab_recebidos:
        if df_mes.empty or "status_validacao" not in df_mes.columns:
            st.info("Nenhum relatório recebido para este mês.")
        else:
            df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
            cats = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
            sub_tabs = st.tabs(cats)
            for i, cat in enumerate(cats):
                with sub_tabs[i]:
                    df_cat = df_ok[df_ok['cat_oficial'] == cat]
                    if df_cat.empty:
                        st.write("Nenhum relatório nesta categoria.")
                    else:
                        cols = st.columns(4)
                        for idx, (_, r) in enumerate(df_cat.iterrows()):
                            with cols[idx % 4]:
                                st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {r["horas"]}h</div></div>', unsafe_allow_html=True)

    # --- ABA 2: PENDÊNCIAS (Lógica Corrigida) ---
    with tab_pendencias:
        st.subheader(f"Pendentes: {mes_sel}")
        entregaram_nomes = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty and "status_validacao" in df_mes.columns else []
        
        cats_pend = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
        p_tabs = st.tabs(cats_pend)
        
        for i, cat in enumerate(cats_pend):
            with p_tabs[i]:
                # Busca no banco quem pertence a essa categoria
                membros_da_categoria = [nome for nome, dados in membros_db.items() if dados.get('categoria') == cat]
                pendentes = sorted([n for n in membros_da_categoria if n not in entregaram_nomes])
                
                if not pendentes:
                    st.success(f"✅ Tudo em dia para {cat}!")
                else:
                    for p_nome in pendentes:
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"⚠️ {p_nome}")
                        nova_cat = c2.selectbox("Mover para", cats_pend + ["INATIVO"], index=cats_pend.index(cat), key=f"p_sel_{p_nome}")
                        if c3.button("Atualizar", key=f"p_btn_{p_nome}"):
                            atualizar_membro(p_nome, nova_cat)
                            st.rerun()

    # --- ABA 3: CONFIGURAÇÃO ---
    with tab_config:
        menu = st.radio("Ação:", ["🗂️ Lista Completa e Edição", "➕ Adicionar Novo"], horizontal=True)
        
        if menu == "➕ Adicionar Novo":
            with st.form("new_member"):
                n_nome = st.text_input("Nome:")
                n_cat = st.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
                if st.form_submit_button("Salvar no Banco"):
                    if n_nome:
                        atualizar_membro(n_nome, n_cat)
                        st.success("Adicionado!")
                        st.rerun()

        else:
            st.write(f"Membros no Banco: {len(membros_db)}")
            lista_ordenada = sorted(membros_db.keys())
            for m_nome in lista_ordenada:
                with st.expander(f"👤 {m_nome} ({membros_db[m_nome].get('categoria', 'N/A')})"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        edit_n = st.text_input("Nome:", value=m_nome, key=f"ed_n_{m_nome}")
                        edit_c = st.selectbox("Cat:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], 
                                            index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(membros_db[m_nome].get('categoria', 'PUBLICADOR')),
                                            key=f"ed_c_{m_nome}")
                        if st.button("Salvar Alterações", key=f"ed_bt_{m_nome}"):
                            if edit_n != m_nome:
                                editar_nome_membro(m_nome, edit_n, edit_c)
                            else:
                                atualizar_membro(m_nome, edit_c)
                            st.rerun()
                    with col_b:
                        st.write("---")
                        if st.button(f"🗑️ Excluir {m_nome}", key=f"del_{m_nome}"):
                            deletar_membro(m_nome)
                            st.rerun()

if __name__ == "__main__":
    main()
