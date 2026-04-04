import streamlit as st
import pandas as pd
import json
import datetime
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO CSS PARA CARDS QUADRADOS ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f8fafc;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .custom-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 10px;
        height: 100%;
    }
    .card-header {
        font-weight: bold;
        color: #1e293b;
        border-bottom: 2px solid #f1f5f9;
        margin-bottom: 10px;
        padding-bottom: 5px;
        font-size: 1.1rem;
    }
    .card-body { font-size: 0.9rem; color: #475569; }
    .status-label { font-weight: bold; text-transform: uppercase; font-size: 0.7rem; color: #64748b; }
    </style>
""", unsafe_allow_html=True)

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

def carregar_membros():
    db = inicializar_db()
    if db:
        docs = db.collection("membros_parque_alianca").stream()
        return {doc.id: doc.to_dict() for doc in docs}
    return {}

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_parque_alianca").document(nome).set({"categoria": categoria})

def carregar_relatorios():
    db = inicializar_db()
    if db:
        docs = db.collection("relatorios_parque_alianca").stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    return []

def main():
    st.title("📊 Gestão Parque Aliança")

    # 1. CARREGAR DADOS
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()
    
    if not relatorios:
        st.info("Aguardando dados...")
        return

    df = pd.DataFrame(relatorios)
    
    # Vincular categoria do Banco de Membros ao Relatório
    def get_cat(nome):
        return membros_db.get(nome, {}).get('categoria', 'PUBLICADOR')
    
    df['categoria'] = df['nome'].apply(get_cat)

    # 2. FILTRO DE MÊS
    meses = sorted(df['mes_referencia'].unique())
    mes_sel = st.sidebar.selectbox("📅 Mês de Referência", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel]

    # 3. ABAS PRINCIPAIS
    tab_relatorios, tab_pendentes, tab_inativos = st.tabs([
        "📝 RELATÓRIOS RECEBIDOS", 
        "⏳ PENDENTES / CLASSIFICAÇÃO", 
        "💤 INATIVOS"
    ])

    # --- ABA 1: RELATÓRIOS RECEBIDOS (CARDS LADO A LADO) ---
    with tab_relatorios:
        sub_tab_pub, sub_tab_aux, sub_tab_reg = st.tabs(["PUBLICADORES", "PIONEIROS AUXILIARES", "PIONEIROS REGULARES"])
        
        cat_map = {
            "PUBLICADOR": sub_tab_pub,
            "PIONEIRO AUXILIAR": sub_tab_aux,
            "PIONEIRO REGULAR": sub_tab_reg
        }

        for cat_nome, aba in cat_map.items():
            with aba:
                df_cat = df_mes[df_mes['categoria'] == cat_nome]
                if df_cat.empty:
                    st.info(f"Nenhum relatório nesta categoria em {mes_sel}.")
                else:
                    # GRID DE 4 COLUNAS
                    cols = st.columns(4)
                    for i, (_, row) in enumerate(df_cat.iterrows()):
                        with cols[i % 4]:
                            st.markdown(f"""
                                <div class="custom-card">
                                    <div class="card-header">{row['nome']}</div>
                                    <div class="card-body">
                                        ⏱️ <b>Horas:</b> {row['horas']}<br>
                                        📖 <b>Estudos:</b> {row['estudos_biblicos']}<br>
                                        ✅ <b>Participou:</b> {'Sim' if row['participou_ministerio'] else 'Não'}<br>
                                        <small>{row['observacoes'] if row['observacoes'] else ''}</small>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            st.button("📄 PDF", key=f"pdf_{row['id']}")

    # --- ABA 2: PENDENTES E CLASSIFICAÇÃO ---
    with tab_pendentes:
        st.subheader(f"Quem ainda não enviou em {mes_sel}")
        
        entregaram = df_mes['nome'].unique()
        # Consideramos todos os que estão no banco e não são inativos
        lista_gestao = [n for n, d in membros_db.items() if d.get('categoria') != 'INATIVO']
        pendentes = [n for n in lista_gestao if n not in entregaram]

        if not pendentes:
            st.success("Tudo em dia!")
        else:
            for p_nome in pendentes:
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{p_nome}**")
                
                # Opção de Reclassificar
                nova_cat = c2.selectbox(
                    "Mudar Categoria", 
                    ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"],
                    key=f"sel_{p_nome}",
                    index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(get_cat(p_nome))
                )
                
                if c3.button("Salvar", key=f"btn_{p_nome}"):
                    atualizar_membro(p_nome, nova_cat)
                    st.toast(f"{p_nome} atualizado!")
                    st.rerun()

    # --- ABA 3: INATIVOS ---
    with tab_inativos:
        inativos = [n for n, d in membros_db.items() if d.get('categoria') == 'INATIVO']
        if not inativos:
            st.info("Nenhum membro marcado como inativo.")
        else:
            cols_in = st.columns(4)
            for i, n_inativo in enumerate(inativos):
                with cols_in[i % 4]:
                    st.markdown(f"""
                        <div class="custom-card" style="border-left: 5px solid #cbd5e1;">
                            <div class="card-header" style="color: #94a3b8;">{n_inativo}</div>
                            <div class="status-label">STATUS: INATIVO</div>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button("Reativar", key=f"re_{n_inativo}"):
                        atualizar_membro(n_inativo, "PUBLICADOR")
                        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados"):
        st.rerun()

if __name__ == "__main__":
    main()
