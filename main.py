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
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
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

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()

def editar_nome_membro(nome_antigo, nome_novo, categoria):
    db = inicializar_db()
    if db and nome_antigo != nome_novo:
        db.collection("membros_v2").document(nome_novo).set({"categoria": categoria})
        db.collection("membros_v2").document(nome_antigo).delete()

# --- INTELIGÊNCIA DE CONFRONTO DE NOMES ---
def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada = str(nome_recebido).strip().lower()
    if not entrada: return None
    for nome_oficial in lista_membros:
        if entrada in nome_oficial.lower():
            return nome_oficial
    return None

def main():
    st.title("📊 Gestão Parque Aliança")
    
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()

    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame(columns=['nome', 'mes_referencia', 'horas', 'id'])

    # Processamento e Validação
    if not df.empty and 'nome' in df.columns:
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)

    # Filtro de Mês
    if not df.empty and 'mes_referencia' in df.columns:
        df['mes_referencia'] = df['mes_referencia'].str.upper()
    
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["MARÇO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_triagem, tab_pendencias, tab_config = st.tabs([
        "📋 RELATÓRIOS RECEBIDOS", "⚠️ TRIAGEM DE NOMES", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"
    ])

    # --- ABA 1: RECEBIDOS ---
    with tab_recebidos:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        if df_ok.empty:
            st.info("Nenhum relatório identificado para este mês.")
        else:
            cats = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
            sub_tabs = st.tabs(cats)
            for i, cat in enumerate(cats):
                with sub_tabs[i]:
                    df_cat = df_ok[df_ok['cat_oficial'] == cat]
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {r["horas"]}h</div></div>', unsafe_allow_html=True)

    # --- ABA 2: TRIAGEM (NOVA FUNCIONALIDADE) ---
    with tab_triagem:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        
        if df_triagem.empty:
            st.success("✨ Nenhum nome pendente de triagem!")
        else:
            st.warning(f"Existem {len(df_triagem)} relatórios com nomes não reconhecidos.")
            
            for index, row in df_triagem.iterrows():
                with st.container():
                    st.markdown(f"""<div class="triagem-box">
                        <b>Nome Digitado:</b> {row['nome']} | <b>Horas:</b> {row['horas']} | <b>Obs:</b> {row.get('observacoes', '-')}
                    </div>""", unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                    
                    nome_correto = c1.text_input("Nome Oficial para o Banco:", value=row['nome'], key=f"tri_n_{row['id']}")
                    cat_nova = c2.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], key=f"tri_c_{row['id']}")
                    
                    if c3.button("✅ VALIDAR", key=f"btn_v_{row['id']}", use_container_width=True):
                        # 1. Salva o novo membro no banco
                        atualizar_membro(nome_correto, cat_nova)
                        # 2. O relatório já existe, na próxima atualização o sistema vai reconhecê-lo pelo nome oficial
                        st.success(f"{nome_correto} cadastrado e relatório validado!")
                        st.rerun()
                        
                    if c4.button("🗑️ RECUSAR", key=f"btn_r_{row['id']}", use_container_width=True):
                        deletar_relatorio(row['id'])
                        st.warning("Relatório excluído.")
                        st.rerun()
                st.markdown("---")

    # --- ABA 3: PENDÊNCIAS ---
    with tab_pendencias:
        entregaram = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty else []
        cats_pend = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
        p_tabs = st.tabs(cats_pend)
        for i, cat in enumerate(cats_pend):
            with p_tabs[i]:
                membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
                pendentes = sorted([n for n in membros_cat if n not in entregaram])
                for p_nome in pendentes:
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"⚠️ {p_nome}")
                    nova_cat = c2.selectbox("Mover", cats_pend + ["INATIVO"], index=cats_pend.index(cat), key=f"pend_{p_nome}")
                    if c3.button("Atualizar", key=f"btn_p_{p_nome}"):
                        atualizar_membro(p_nome, nova_cat)
                        st.rerun()

    # --- ABA 4: CONFIGURAÇÃO ---
    with tab_config:
        st.write(f"Total de Membros no Banco: {len(membros_db)}")
        # (Mantive a lógica de edição/exclusão que já tínhamos)
        for m_nome in sorted(membros_db.keys()):
            with st.expander(f"👤 {m_nome}"):
                ca, cb = st.columns(2)
                with ca:
                    edit_n = st.text_input("Editar Nome:", value=m_nome, key=f"cfg_n_{m_nome}")
                    edit_c = st.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], 
                                         index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(membros_db[m_nome].get('categoria', 'PUBLICADOR')),
                                         key=f"cfg_c_{m_nome}")
                    if st.button("Salvar Alterações", key=f"cfg_s_{m_nome}"):
                        if edit_n != m_nome: editar_nome_membro(m_nome, edit_n, edit_c)
                        else: atualizar_membro(m_nome, edit_c)
                        st.rerun()
                with cb:
                    if st.button(f"Excluir {m_nome}", key=f"cfg_d_{m_nome}"):
                        db = inicializar_db()
                        db.collection("membros_v2").document(m_nome).delete()
                        st.rerun()

if __name__ == "__main__":
    main()
