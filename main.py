import streamlit as st
import pandas as pd
import json
from google.cloud import firestore
from google.oauth2 import service_account

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- LISTA MESTRA DE TODOS OS PUBLICADORES (EXTRAÍDA DAS SUAS FOTOS) ---
LISTA_COMPLETA_NOMES = [
    "Airton Pereira da Silva", "Anderson de Almeida Silva", "Anderson Vieira Dantas",
    "Antonia Cordeiro Silva", "Aparecida Cruz dos Santos", "Ariana Rodrigues Calado Oliveira",
    "Beatriz Dantas dos Santos", "Brenda Vieira Dantas", "Bruno Oliveira da Silva",
    "Cecilia Geremias Cunha", "Celidalva de Souza Santos", "Clauberto de Oliveira Silva",
    "Cosme Ferreira Primo", "Dalva Dias de Queiroz", "Deise Santana Nogueira Fernandes",
    "Doralice Carlos Souza Silva", "Edna Oliveira Sales Gomes", "Edney da Cruz Barbosa",
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
    "Vilma Pereira da Silva", "Wendley Leite Cunha",
    "Ana Dilma Cardoso", "Cintia Aparecida Travaglin", "Diva Cordeiro de Souza", 
    "Edna Alves Secundo", "Ivan Rodrigues Vieira da Silva", "Jessica Melo da Silva", 
    "Joselita Maria dos Santos", "Katia Almeida Nunes Dantas", "Marcia Rocha de Oliveira", 
    "Maria Dalia Silva Oliveira", "Marilele de Andrade e Melo Silva", "Marilene Lopes Araujo", 
    "Miriam Silva Oliveira", "Rene Fonseca Cardoso", "Romys Ferreira Primo", 
    "Ruth Almeida Nunes", "Sirlene Rodrigues Calado", "Thalita Lopes de Oliveira", "Zelia Pereira Santos"
]

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-triagem { border-left: 5px solid #f39c12; background-color: #fff9f0; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DB ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except: return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    if not db: return {}
    docs = db.collection("membros_v2").stream()
    membros = {doc.id: doc.to_dict() for doc in docs}
    
    # IMPORTAÇÃO INICIAL SE VAZIO (Agora com todos os nomes)
    if not membros:
        with st.spinner("Populando banco de dados pela primeira vez..."):
            for nome in LISTA_COMPLETA_NOMES:
                # Lógica: Se estiver na lista de pioneiros, marca como tal, senão Publicador
                cat = "PIONEIRO REGULAR" if "Rene Fonseca" in nome or "Ana Dilma" in nome else "PUBLICADOR" 
                # (Ajuste fino manual depois na aba de gestão)
                db.collection("membros_v2").document(nome).set({"categoria": cat})
                membros[nome] = {"categoria": cat}
    return membros

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def normalizar_nome_estrito(nome_digitado, lista_oficial):
    nome_busca = str(nome_digitado).strip().lower()
    for oficial in lista_oficial:
        if nome_busca == oficial.lower() or (len(nome_busca) > 4 and nome_busca in oficial.lower()):
            return oficial
    return None # Retorna None se não achar ninguém parecido

def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios = carregar_relatorios()
    if not relatorios: return st.info("Sem relatórios.")

    df = pd.DataFrame(relatorios)
    
    # Processamento com Identificação de "Novos/Desconhecidos"
    def identificar_status(row):
        nome_corrigido = normalizar_nome_estrito(row['nome'], membros_db.keys())
        if nome_corrigido:
            return pd.Series([nome_corrigido, membros_db[nome_corrigido]['categoria'], "IDENTIFICADO"])
        else:
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    df[['nome_final', 'categoria_final', 'status_processo']] = df.apply(identificar_status, axis=1)

    meses = sorted(df['mes_referencia'].unique())
    mes_sel = st.sidebar.selectbox("Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel]

    tab_vis, tab_gestao, tab_triagem, tab_inativos = st.tabs(["📋 RELATÓRIOS", "⚙️ PENDÊNCIAS", "⚠️ TRIAGEM (NOVOS)", "💤 INATIVOS"])

    # --- ABA RELATÓRIOS (SÓ MOSTRA QUEM FOI IDENTIFICADO) ---
    with tab_vis:
        df_ok = df_mes[df_mes['status_processo'] == "IDENTIFICADO"]
        s_pub, s_aux, s_reg = st.tabs(["PUBLICADORES", "AUXILIARES", "REGULARES"])
        map_v = {"PUBLICADOR": s_pub, "PIONEIRO AUXILIAR": s_aux, "PIONEIRO REGULAR": s_reg}
        for c, aba in map_v.items():
            with aba:
                d_cat = df_ok[df_ok['categoria_final'] == c]
                cols = st.columns(4)
                for i, (_, r) in enumerate(d_cat.iterrows()):
                    with cols[i % 4]:
                        st.markdown(f'<div class="card"><div class="card-header">{r["nome_final"]}</div><div style="font-size:0.8rem;">⏱️ {r["horas"]}h | 📖 {r["estudos_biblicos"]} Est.</div></div>', unsafe_allow_html=True)

    # --- ABA TRIAGEM (NOMES QUE NÃO ESTÃO NO BANCO) ---
    with tab_triagem:
        st.subheader("Relatórios com nomes não reconhecidos")
        df_desconhecido = df_mes[df_mes['status_processo'] == "TRIAGEM"]
        
        if df_desconhecido.empty:
            st.success("Nenhum nome novo para processar.")
        else:
            for _, r_novo in df_desconhecido.iterrows():
                with st.expander(f"Resolver: {r_novo['nome']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Opção A: Combinar com existente**")
                        alvo = st.selectbox("Escolha o nome correto:", [""] + list(membros_db.keys()), key=f"comb_{r_novo['id']}")
                        if st.button("Combinar Nome", key=f"btn_comb_{r_novo['id']}"):
                            # Aqui você atualizaria o relatório no banco com o nome correto
                            st.info("Funcionalidade de update de ID do relatório em desenvolvimento...")
                    
                    with c2:
                        st.write("**Opção B: Novo Publicador**")
                        cat_nova = st.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"], key=f"new_cat_{r_novo['id']}")
                        if st.button("Adicionar ao Banco", key=f"btn_add_{r_novo['id']}"):
                            atualizar_membro(r_novo['nome'], cat_nova)
                            st.success(f"{r_novo['nome']} adicionado!")
                            st.rerun()

    # --- ABA PENDÊNCIAS (AGORA MOSTRA OS PUBLICADORES DAS FOTOS) ---
    with tab_gestao:
        entregaram = df_mes[df_mes['status_processo'] == "IDENTIFICADO"]['nome_final'].unique()
        p_pub, p_aux, p_reg = st.tabs(["PUBLICADORES", "AUXILIARES", "REGULARES"])
        map_p = {"PUBLICADOR": p_pub, "PIONEIRO AUXILIAR": p_aux, "PIONEIRO REGULAR": p_reg}
        
        for cid, aba in map_p.items():
            with aba:
                membros_cat = [n for n, d in membros_db.items() if d['categoria'] == cid]
                pendentes = [n for n in membros_cat if n not in entregaram]
                
                if not pendentes: st.success("Tudo em dia!")
                for p_nome in pendentes:
                    col1, col2, col3 = st.columns([2,2,1])
                    col1.write(p_nome)
                    n_cat = col2.selectbox("Mover:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], index=["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(cid), key=f"p_{p_nome}")
                    if col3.button("OK", key=f"b_{p_nome}"):
                        atualizar_membro(p_nome, n_cat)
                        st.rerun()

    with tab_inativos:
        # Lógica de inativos igual ao anterior
        inativos = [n for n, d in membros_db.items() if d['categoria'] == "INATIVO"]
        cols_in = st.columns(4)
        for i, n_in in enumerate(inativos):
            with cols_in[i % 4]:
                st.markdown(f'<div class="card card-inativo">{n_in}</div>', unsafe_allow_html=True)
                if st.button("Reativar", key=f"re_{n_in}"):
                    atualizar_membro(n_in, "PUBLICADOR")
                    st.rerun()

if __name__ == "__main__":
    main()
