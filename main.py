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

# --- INTELIGÊNCIA DE CONFRONTO DE NOMES ---
def normalizar_nome_no_banco(nome_recebido, lista_membros):
    """
    Compara o nome vindo do formulário com a lista do banco.
    Se o usuário escreveu 'Cardoso', ele encontra 'Rene Fonseca Cardoso'.
    """
    entrada = str(nome_recebido).strip().lower()
    if not entrada: return None
    
    # Busca por correspondência parcial (Case Insensitive)
    for nome_oficial in lista_membros:
        if entrada in nome_oficial.lower():
            return nome_oficial
    return None

def main():
    st.title("📊 Gestão Parque Aliança")
    
    # 1. Carrega dados do Banco
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()

    # 2. Processamento dos Relatórios
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame(columns=['nome', 'mes_referencia', 'horas'])

    # 3. Lógica de Validação e Cruzamento (Ajustada)
    if not df.empty and 'nome' in df.columns:
        def validar_envio(row):
            # Tenta encontrar o nome oficial no banco usando a lógica de confronto
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            
            if nome_oficial:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            else:
                return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        
        # Aplicamos o cruzamento de dados
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)

    # 4. Filtro de Mês (Normalizado para MAIÚSCULAS para evitar erros de digitação)
    if not df.empty and 'mes_referencia' in df.columns:
        df['mes_referencia'] = df['mes_referencia'].str.upper()
    
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["MARÇO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_pendencias, tab_config = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 1: RECEBIDOS ---
    with tab_recebidos:
        if df_mes.empty or "status_validacao" not in df_mes.columns:
            st.info(f"Nenhum relatório processado para {mes_sel}.")
        else:
            df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
            df_erro = df_mes[df_mes['status_validacao'] == "TRIAGEM"]

            if not df_erro.empty:
                st.warning(f"⚠️ Existem {len(df_erro)} nomes que o sistema não reconheceu. Verifique a aba Configuração ou peça para corrigirem o nome.")

            cats = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
            sub_tabs = st.tabs(cats)
            for i, cat in enumerate(cats):
                with sub_tabs[i]:
                    df_cat = df_ok[df_ok['cat_oficial'] == cat]
                    if df_cat.empty:
                        st.write("Nenhum relatório entregue.")
                    else:
                        cols = st.columns(4)
                        for idx, (_, r) in enumerate(df_cat.iterrows()):
                            with cols[idx % 4]:
                                st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {r["horas"]}h</div></div>', unsafe_allow_html=True)

    # --- ABA 2: PENDÊNCIAS ---
    with tab_pendencias:
        st.subheader(f"Não enviaram em {mes_sel}")
        entregaram_nomes = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty else []
        
        cats_pend = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
        p_tabs = st.tabs(cats_pend)
        
        for i, cat in enumerate(cats_pend):
            with p_tabs[i]:
                membros_da_categoria = [nome for nome, dados in membros_db.items() if dados.get('categoria') == cat]
                pendentes = sorted([n for n in membros_da_categoria if n not in entregaram_nomes])
                
                if not pendentes:
                    st.success(f"✅ Todos os {cat} entregaram!")
                else:
                    for p_nome in pendentes:
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"⚠️ {p_nome}")
                        nova_cat = c2.selectbox("Mudar categoria", cats_pend + ["INATIVO"], index=cats_pend.index(cat), key=f"p_sel_{p_nome}_{cat}")
                        if c3.button("Atualizar", key=f"p_btn_{p_nome}_{cat}"):
                            atualizar_membro(p_nome, nova_cat)
                            st.rerun()

    # --- ABA 3: CONFIGURAÇÃO ---
    with tab_config:
        menu = st.radio("Selecione:", ["🗂️ Gerenciar Lista do Banco", "➕ Novo Membro"], horizontal=True)
        
        if menu == "➕ Novo Membro":
            with st.form("form_novo"):
                n_nome = st.text_input("Nome Completo (Identificador):")
                n_cat = st.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
                if st.form_submit_button("Salvar no Firestore"):
                    if n_nome:
                        atualizar_membro(n_nome, n_cat)
                        st.success("Membro adicionado!")
                        st.rerun()
        else:
            st.write(f"Total de registros: {len(membros_db)}")
            for m_nome in sorted(membros_db.keys()):
                with st.expander(f"👤 {m_nome}"):
                    ca, cb = st.columns(2)
                    with ca:
                        edit_n = st.text_input("Nome:", value=m_nome, key=f"inp_n_{m_nome}")
                        opcoes = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"]
                        atual_cat = membros_db[m_nome].get('categoria', 'PUBLICADOR')
                        edit_c = st.selectbox("Categoria:", opcoes, index=opcoes.index(atual_cat), key=f"inp_c_{m_nome}")
                        if st.button("Salvar", key=f"btn_s_{m_nome}"):
                            if edit_n != m_nome:
                                editar_nome_membro(m_nome, edit_n, edit_c)
                            else:
                                atualizar_membro(m_nome, edit_c)
                            st.rerun()
                    with cb:
                        st.write("---")
                        if st.button(f"🗑️ Deletar Registro", key=f"btn_d_{m_nome}"):
                            deletar_membro(m_nome)
                            st.rerun()

if __name__ == "__main__":
    main()
