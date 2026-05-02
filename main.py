import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from datetime import datetime

# Bibliotecas para preenchimento do PDF OFICIAL (Overlay)
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO CUSTOMIZADA ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .stButton > button { width: 100%; }
    /* Botão de Deletar Vermelho */
    div.stButton > button:first-child[key^="del_"] {
        background-color: #ff4b4b;
        color: white;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- MOTOR DE PDF (S-21 OFICIAL) ---
def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado.")
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24*mm, 258*mm, str(nome_cabecalho).upper())
    
    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5
    }
    
    for _, row in dados_rows.iterrows():
        mes_key = str(row['mes_referencia']).split()[0].upper()
        if mes_key in y_map:
            y_pos = y_map[mes_key] * mm
            if int(row.get('horas', 0)) > 0 or int(row.get('estudos_biblicos', 0)) > 0:
                can.drawCentredString(53.5*mm, y_pos, "X")
            can.drawCentredString(80.5*mm, y_pos, str(int(row.get('estudos_biblicos', 0))))
            if row.get('cat_oficial') == "PIONEIRO AUXILIAR" or "AUXILIAR" in str(categoria_label).upper():
                can.drawCentredString(97.5*mm, y_pos, "X")
            can.drawCentredString(116.5*mm, y_pos, str(int(row.get('horas', 0))))
            obs = str(row.get('observacoes', ''))[:30]
            if obs and obs.lower() != 'nan':
                can.setFont("Helvetica", 7)
                can.drawString(133*mm, y_pos, obs)
                can.setFont("Helvetica-Bold", 10)

    can.save()
    packet.seek(0)
    reader_original = PdfReader(open(path_original, "rb"))
    writer = PdfWriter()
    pagina_base = reader_original.pages[0]
    pagina_base.merge_page(PdfReader(packet).pages[0])
    writer.add_page(pagina_base)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()

# --- BANCO DE DADOS ---
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
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()]

def atualizar_membro_completo(nome, dados_dict):
    db = inicializar_db()
    if db:
        dados_dict["nome_oficial"] = nome
        db.collection("membros_v2").document(nome).set(dados_dict, merge=True)

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db: 
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório Deletado!")
        st.rerun()

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.85 else None

# --- APP ---
def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    designacoes_lista = ["ANCIÃO", "SERVO MINISTERIAL", "UNGIDO", "OUTRAS OVELHAS"]
    
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
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
    
    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "⚙️ CONFIGURAÇÃO"])

    # --- ABAS DE VISUALIZAÇÃO (Mantidas) ---
    with tabs[0]:
        df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        if df_ok.empty: st.info("Sem dados identificados para este mês.")
        else:
            st.subheader(f"Relatórios de {mes_sel}")
            st.dataframe(df_ok[['nome_oficial', 'cat_oficial', 'horas', 'estudos_biblicos']])

    with tabs[1]:
        st.info("Área de Triagem de nomes não reconhecidos.")

    with tabs[2]:
        st.info("Consolidado e Histórico S-21.")

    # --- ABA 3: CONFIG & EDIÇÃO (FOCO DO AJUSTE) ---
    with tabs[3]:
        sub_cfg = st.tabs(["✏️ EDITAR RELATÓRIOS", "👥 GESTÃO DE MEMBROS", "📦 EXPORTAR ZIP"])
        
        # 1 - EDITAR RELATÓRIOS (COM BOTÃO DELETAR)
        with sub_cfg[0]:
            st.write(f"### Edição de Relatórios - {mes_sel}")
            if not df.empty:
                df_edit = df[df['mes_referencia'] == mes_sel]
                for _, r in df_edit.sort_values('nome_oficial').iterrows():
                    with st.expander(f"📝 {r['nome_oficial']} ({int(r['horas'])}h)"):
                        col1, col2, col3 = st.columns([2,1,1])
                        
                        # Fallback para categoria caso não esteja na lista
                        idx_cat = categorias_lista.index(r['cat_oficial']) if r['cat_oficial'] in categorias_lista else 0
                        
                        nova_cat = col1.selectbox("Categoria", categorias_lista, index=idx_cat, key=f"cat_{r['id']}")
                        novas_h = col2.number_input("Horas", value=int(r['horas']), key=f"hr_{r['id']}")
                        novos_e = col3.number_input("Estudos", value=int(r['estudos_biblicos']), key=f"es_{r['id']}")
                        
                        b_salvar, b_deletar = st.columns(2)
                        if b_salvar.button("Salvar Alterações", key=f"save_{r['id']}"):
                            inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({
                                "horas": novas_h, 
                                "estudos_biblicos": novos_e,
                                "cat_oficial": nova_cat
                            })
                            st.success("Atualizado!")
                            st.rerun()
                        
                        if b_deletar.button("Deletar este relatório", key=f"del_{r['id']}"):
                            deletar_relatorio(r['id'])

        # 2 - GESTÃO DE MEMBROS (LISTA COMPLETA ALFABÉTICA COM CHECKBOXES E DATAS)
        with sub_cfg[1]:
            st.write("### Cadastro e Atributos de Membros")
            
            if membros_db:
                membros_lista = sorted(membros_db.keys())
                for nome in membros_lista:
                    m_data = membros_db[nome]
                    with st.expander(f"👤 {nome}"):
                        with st.form(key=f"form_mem_{nome}"):
                            c_dt1, c_dt2 = st.columns(2)
                            
                            # Datas (Nascimento e Batismo)
                            dt_nasc = c_dt1.date_input("Nascimento", 
                                value=pd.to_datetime(m_data.get('nascimento', '1990-01-01')).date())
                            dt_bat = c_dt2.date_input("Batismo", 
                                value=pd.to_datetime(m_data.get('batismo', '1990-01-01')).date())
                            
                            # Checkboxes de Cargos/Designações
                            st.write("**Atributos:**")
                            col_ck1, col_ck2, col_ck3, col_ck4 = st.columns(4)
                            
                            is_anciao = col_ck1.checkbox("Ancião", value=m_data.get('is_anciao', False))
                            is_servo = col_ck2.checkbox("Servo Ministerial", value=m_data.get('is_servo', False))
                            is_pioneiro = col_ck3.checkbox("Pioneiro Regular", value=m_data.get('categoria') == "PIONEIRO REGULAR")
                            is_publicador = col_ck4.checkbox("Publicador", value=m_data.get('categoria') == "PUBLICADOR")
                            
                            if st.form_submit_button("Atualizar Cadastro"):
                                # Define categoria baseada no check
                                cat_atualizada = "PUBLICADOR"
                                if is_pioneiro: cat_atualizada = "PIONEIRO REGULAR"
                                
                                novos_dados = {
                                    "nascimento": str(dt_nasc),
                                    "batismo": str(dt_bat),
                                    "is_anciao": is_anciao,
                                    "is_servo": is_servo,
                                    "categoria": cat_atualizada
                                }
                                atualizar_membro_completo(nome, novos_dados)
                                st.success(f"Dados de {nome} salvos!")
                                st.rerun()
            else:
                st.warning("Nenhum membro cadastrado.")

    st.caption("v2.5.0 | Parque Aliança | Gestão Integrada")

if __name__ == "__main__":
    main()
