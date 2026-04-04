import streamlit as st
import pandas as pd
import json
import datetime
from google.cloud import firestore
from google.oauth2 import service_account
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pdfrw import PdfReader, PdfWriter, PageMerge

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO VISUAL ---
st.markdown("""
    <style>
    .card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .card-pub { border-left: 6px solid #4e73df; }
    .card-aux { border-left: 6px solid #1cc88a; }
    .card-reg { border-left: 6px solid #f6c23e; }
    .card-pendente { border-left: 6px solid #e74a3b; background-color: #fff5f5; }
    
    .label { color: #5a5c69; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }
    .value { color: #2e2f37; font-size: 1rem; font-weight: bold; margin-bottom: 8px; }
    .obs { font-size: 0.85rem; color: #858796; font-style: italic; border-top: 1px solid #eee; pt: 5px; }
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

def carregar_relatorios():
    db = inicializar_db()
    if db:
        docs = db.collection("relatorios_parque_alianca").stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    return []

def gerenciar_membros(acao, dados=None):
    db = inicializar_db()
    if not db: return
    if acao == "listar":
        docs = db.collection("membros_congregacao").stream()
        return {doc.id: doc.to_dict() for doc in docs}
    elif acao == "salvar":
        db.collection("membros_congregacao").document(dados['nome']).set(dados)

# --- LOGICA DE PDF ---
def gerar_pdf_s4t(dados):
    try:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        meses_y = {"SETEMBRO": 455, "OUTUBRO": 438, "NOVEMBRO": 421, "DEZEMBRO": 404, "JANEIRO": 387, "FEVEREIRO": 370, "MARÇO": 353, "ABRIL": 336, "MAIO": 319, "JUNHO": 302, "JULHO": 285, "AGOSTO": 268}
        mes_puro = dados['mes_referencia'].split()[0].upper()
        y = meses_y.get(mes_puro, 100)
        can.setFont("Helvetica-Bold", 10)
        if dados['participou_ministerio']: can.drawString(168, y, "X")
        can.drawString(220, y, str(dados['estudos_biblicos']))
        can.drawString(340, y, str(dados['horas']))
        can.save()
        packet.seek(0)
        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader("S-4-T_Template.pdf")
        output = PdfWriter()
        page = existing_pdf.pages[0]
        PageMerge(page).add(new_pdf.pages[0]).render()
        output.addpage(page)
        result = BytesIO()
        output.write(result)
        return result.getvalue()
    except: return None

def main():
    st.title("📊 Gestão Parque Aliança")
    
    # Carregar Membros e Relatórios
    membros = gerenciar_membros("listar")
    dados_brutos = carregar_relatorios()
    
    if not membros:
        st.warning("Nenhum membro cadastrado. Vá na aba 'GESTÃO DE PESSOAS'.")
        membros = {}

    df = pd.DataFrame(dados_brutos) if dados_brutos else pd.DataFrame()
    
    # Filtro de Mês
    if not df.empty:
        meses = sorted(df['mes_referencia'].unique())
        mes_sel = st.sidebar.selectbox("📅 Mês de Referência", meses, index=len(meses)-1)
        df_mes = df[df['mes_referencia'] == mes_sel]
    else:
        mes_sel = "Nenhum dado"
        df_mes = pd.DataFrame()

    aba_rel, aba_gestao = st.tabs(["📝 RELATÓRIOS DO MÊS", "⚙️ GESTÃO DE PESSOAS"])

    with aba_rel:
        if df_mes.empty:
            st.info("Sem envios para este mês.")
        else:
            col1, col2, col3 = st.columns(3)
            # Categorias
            for i, (cat, nome_cat, cor) in enumerate([("PUBLICADOR", "Publicadores", "card-pub"), 
                                                     ("PIONEIRO AUXILIAR", "Auxiliares", "card-aux"), 
                                                     ("PIONEIRO REGULAR", "Regulares", "card-reg")]):
                with [col1, col2, col3][i]:
                    df_cat = df_mes[df_mes['categoria'] == cat]
                    # Card Consolidado
                    st.markdown(f"""<div class="card {cor}">
                        <div class="label">CONSOLIDADO {nome_cat}</div>
                        <div class="value">Horas: {df_cat['horas'].sum()} | Estudos: {df_cat['estudos_biblicos'].sum()}</div>
                        <div class="label">Total de Relatórios: {len(df_cat)}</div>
                    </div>""", unsafe_allow_html=True)
                    
                    # Cards Individuais (TUDO DENTRO)
                    for _, row in df_cat.iterrows():
                        with st.container():
                            st.markdown(f"""<div class="card {cor}">
                                <div class="label">Nome</div><div class="value">{row['nome']}</div>
                                <div class="label">Horas / Estudos</div><div class="value">⏱️ {row['horas']} / 📖 {row['estudos_biblicos']}</div>
                                <div class="label">Status</div><div class="value">{'✅ Ativo' if row['participou_ministerio'] else '🛑 Inativo'}</div>
                                {f'<div class="obs"><b>Obs:</b> {row["observacoes"]}</div>' if row['observacoes'] else ''}
                            </div>""", unsafe_allow_html=True)
                            
                            pdf = gerar_pdf_s4t(row)
                            if pdf:
                                st.download_button("📩 Baixar S-4-T", pdf, f"{row['nome']}.pdf", "application/pdf", key=row['id'])

    with aba_gestao:
        st.subheader("Cadastrar / Editar Membro")
        with st.form("novo_membro"):
            c_nome = st.text_input("Nome Completo")
            c_cat = st.selectbox("Classificação", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"])
            if st.form_submit_button("Salvar Membro"):
                gerenciar_membros("salvar", {"nome": c_nome, "categoria": c_cat, "ativo": True})
                st.success("Salvo com sucesso!")
                st.rerun()

        st.divider()
        st.subheader("Status de Envios - Pendentes")
        
        entregaram = df_mes['nome'].tolist() if not df_mes.empty else []
        for nome, info in membros.items():
            if nome not in entregaram and info['categoria'] != "INATIVO":
                st.markdown(f"""<div class="card card-pendente">
                    <div class="label">NÃO ENVIOU: {info['categoria']}</div>
                    <div class="value">{nome}</div>
                </div>""", unsafe_allow_html=True)
                if st.button(f"Marcar {nome} como Inativo", key=f"inativo_{nome}"):
                    info['categoria'] = "INATIVO"
                    gerenciar_membros("salvar", info)
                    st.rerun()

    st.caption("Sistema v2.0 | Parque Aliança")

if __name__ == "__main__":
    main()
