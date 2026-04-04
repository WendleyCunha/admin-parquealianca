import streamlit as st
import pandas as pd
import json
import unicodedata
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def remover_acentos(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

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
        st.toast("Relatório removido!")

def editar_nome_membro(nome_antigo, nome_novo, categoria):
    db = inicializar_db()
    if db and nome_antigo != nome_novo:
        db.collection("membros_v2").document(nome_novo).set({"categoria": categoria})
        db.collection("membros_v2").document(nome_antigo).delete()

# --- FUNÇÃO CRUCIAL PARA O SEU PEDIDO ---
def validar_e_vincular(relatorio_id, nome_final, categoria):
    db = inicializar_db()
    if db:
        # 1. Garante que o nome está no banco de membros
        db.collection("membros_v2").document(nome_final).set({"categoria": categoria}, merge=True)
        # 2. Atualiza o NOME no relatório original para o nome idêntico ao do banco
        db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_final})
        st.toast(f"Vinculado: {nome_final}")

# --- INTELIGÊNCIA DE CONFRONTO MELHORADA ---
def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada = remover_acentos(nome_recebido)
    if not entrada: return None
    
    # Busca por igualdade sem acento
    for nome_oficial in lista_membros:
        if entrada == remover_acentos(nome_oficial):
            return nome_oficial
            
    # Busca por parte do nome (Contém)
    for nome_oficial in lista_membros:
        if entrada in remover_acentos(nome_oficial):
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

        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
        
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tab_recebidos, tab_triagem, tab_pendencias, tab_config = st.tabs([
        "📋 RELATÓRIOS RECEBIDOS", "⚠️ TRIAGEM DE NOMES", "⏳ PENDÊNCIAS", "⚙️ CONFIGURAÇÃO"
    ])

    with tab_recebidos:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        if df_ok.empty:
            st.info("Nenhum relatório identificado.")
        else:
            cats = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
            sub_tabs = st.tabs(cats)
            for i, cat in enumerate(cats):
                with sub_tabs[i]:
                    df_cat = df_ok[df_ok['cat_oficial'] == cat]
                    if not df_cat.empty:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Envios", len(df_cat))
                        m2.metric("Total Horas", f"{int(df_cat['horas'].sum())}h")
                        m3.metric("Estudos", int(df_cat['estudos_biblicos'].sum()))
                        
                        cols = st.columns(4)
                        for idx, (_, r) in enumerate(df_cat.iterrows()):
                            with cols[idx % 4]:
                                st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div>⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}</div>', unsafe_allow_html=True)
                                if st.button("🗑️", key=f"del_{r['id']}"):
                                    deletar_relatorio(r['id'])
                                    st.rerun()

    with tab_triagem:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty:
            st.success("✨ Triagem limpa!")
        else:
            for index, row in df_triagem.iterrows():
                with st.container():
                    st.markdown(f'<div class="triagem-box"><b>Digitado:</b> {row["nome"]}</div>', unsafe_allow_html=True)
                    c1, c2, c3 = st.columns([2, 1, 1])
                    nome_correto = c1.text_input("Confirmar Nome Oficial:", value=row['nome'], key=f"t_n_{row['id']}")
                    cat_nova = c2.selectbox("Cat:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"], key=f"t_c_{row['id']}")
                    if c3.button("✅ VALIDAR", key=f"btn_v_{row['id']}"):
                        validar_e_vincular(row['id'], nome_correto, cat_nova)
                        st.rerun()

    with tab_pendencias:
        entregaram = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty else []
        membros_cat = [n for n, d in membros_db.items() if d.get('categoria') in ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]]
        pendentes = sorted([n for n in membros_cat if n not in entregaram])
        
        if not pendentes:
            st.success("🙌 Nenhuma pendência!")
        else:
            for p_nome in pendentes:
                st.write(f"⚠️ {p_nome}")

    with tab_config:
        st.write(f"Membros no Banco: {len(membros_db)}")
        # ... (lógica de configuração mantida)

if __name__ == "__main__":
    main()
