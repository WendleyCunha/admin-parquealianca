import streamlit as st
import pandas as pd
import json
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO (Mantida 100% conforme seu original) ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    .stButton>button.del-btn {
        padding: 0px 5px;
        height: 25px;
        width: 25px;
        min-width: 25px;
        font-size: 12px;
        border-radius: 5px;
        background-color: #fee2e2;
        color: #ef4444;
        border: 1px solid #fecaca;
        float: right;
    }
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
        st.toast("Relatório removido com sucesso!")

def editar_nome_membro(nome_antigo, nome_novo, categoria):
    db = inicializar_db()
    if db and nome_antigo != nome_novo:
        db.collection("membros_v2").document(nome_novo).set({"categoria": categoria})
        db.collection("membros_v2").document(nome_antigo).delete()

# --- NOVA FUNÇÃO ESTRUTURAL PARA ATENDER SEU PEDIDO ---
def validar_e_gravar_novo_membro(relatorio_id, nome_correto, categoria):
    db = inicializar_db()
    if db:
        # 1. Cadastra o nome no banco de dados (Aumenta o Total de Membros)
        db.collection("membros_v2").document(nome_correto).set({"categoria": categoria}, merge=True)
        # 2. Atualiza o relatório recebido com este novo nome oficial
        # Isso faz ele sair da Triagem e ir para Recebidos automaticamente
        db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_correto})
        st.toast(f"✅ {nome_correto} cadastrado e relatório validado!")

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

    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame(columns=['nome', 'mes_referencia', 'horas', 'id', 'estudos_biblicos'])
    
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)

    if not df.empty and 'nome' in df.columns:
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)

    if not df.empty and 'mes_referencia' in df.columns:
        df['mes_referencia'] = df['mes_referencia'].str.upper()
    
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_triagem, tab_pendencias, tab_config = st.tabs([
        "📋 RELATÓRIOS RECEBIDOS", "⚠️ TRIAGEM DE NOMES", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"
    ])

    # --- ABA 1: RECEBIDOS (Mantida Integralmente) ---
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
                    if not df_cat.empty:
                        t_envios = len(df_cat)
                        t_horas = df_cat['horas'].sum()
                        t_estudos = df_cat['estudos_biblicos'].sum()
                        m1, m2, m3 = st.columns(3)
                        m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{t_envios}</div></div>', unsafe_allow_html=True)
                        m2.markdown(f'<div class="metric-container"><div class="metric-label">Total Horas</div><div class="metric-value">{int(t_horas)}h</div></div>', unsafe_allow_html=True)
                        m3.markdown(f'<div class="metric-container"><div class="metric-label">Total Estudos</div><div class="metric-value">{int(t_estudos)}</div></div>', unsafe_allow_html=True)
                        st.write("")
                        cols = st.columns(4)
                        for idx, (_, r) in enumerate(df_cat.iterrows()):
                            with cols[idx % 4]:
                                with st.container():
                                    st.markdown(f"""<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>""", unsafe_allow_html=True)
                                    if st.button(f"🗑️ Deletar", key=f"del_ok_{r['id']}", use_container_width=True):
                                        deletar_relatorio(r['id'])
                                        st.rerun()

    # --- ABA 2: TRIAGEM (ALTERADA PARA ATENDER SEU PEDIDO) ---
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
                    # Aqui você ajusta o nome antes de validar
                    nome_para_gravar = c1.text_input("Ajustar para Nome Oficial:", value=row['nome'], key=f"tri_n_{row['id']}")
                    cat_nova = c2.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], key=f"tri_c_{row['id']}")
                    
                    if c3.button("✅ VALIDAR", key=f"btn_v_{row['id']}", use_container_width=True):
                        # Chamada da nova função: Grava no banco E atualiza o relatório
                        validar_e_gravar_novo_membro(row['id'], nome_para_gravar, cat_nova)
                        st.rerun()
                    
                    if c4.button("🗑️ RECUSAR", key=f"btn_r_{row['id']}", use_container_width=True):
                        deletar_relatorio(row['id'])
                        st.rerun()
                st.markdown("---")

    # --- ABA 3: PENDÊNCIAS (Mantida Integralmente) ---
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

    # --- ABA 4: CONFIGURAÇÃO (Mantida Integralmente) ---
    with tab_config:
        st.write(f"Total de Membros no Banco: {len(membros_db)}")
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
                        else: atualizar_membro(edit_n, edit_c)
                        st.rerun()
                with cb:
                    if st.button(f"Excluir {m_nome}", key=f"cfg_d_{m_nome}"):
                        db = inicializar_db()
                        db.collection("membros_v2").document(m_nome).delete()
                        st.rerun()

if __name__ == "__main__":
    main()
