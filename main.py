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

# --- ESTILIZAÇÃO VISUAL (CARDS TOTAIS) ---
st.markdown("""
    <style>
    .card {
        background-color: #ffffff;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-top: 1px solid #eee;
    }
    .card-pub { border-left: 8px solid #4e73df; }
    .card-aux { border-left: 8px solid #1cc88a; }
    .card-reg { border-left: 8px solid #f6c23e; }
    .card-pendente { border-left: 8px solid #e74a3b; background-color: #fffcfc; }
    
    .metric-label { color: #64748b; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { color: #1e293b; font-size: 1.05rem; font-weight: bold; margin-bottom: 10px; display: block; }
    .obs-box { font-size: 0.85rem; color: #475569; background: #f8fafc; padding: 8px; border-radius: 6px; margin-top: 8px; border: 1px dashed #cbd5e1; }
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
    if not db: return {}
    if acao == "listar":
        docs = db.collection("membros_congregacao").stream()
        return {doc.id: doc.to_dict() for doc in docs}
    elif acao == "salvar":
        db.collection("membros_congregacao").document(dados['nome']).set(dados)

# --- LÓGICA DE PDF ---
def gerar_pdf_s4t(dados):
    try:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        meses_y = {"SETEMBRO": 455, "OUTUBRO": 438, "NOVEMBRO": 421, "DEZEMBRO": 404, "JANEIRO": 387, "FEVEREIRO": 370, "MARÇO": 353, "ABRIL": 336, "MAIO": 319, "JUNHO": 302, "JULHO": 285, "AGOSTO": 268}
        mes_puro = str(dados.get('mes_referencia', '')).split()[0].upper()
        y = meses_y.get(mes_puro, 100)
        can.setFont("Helvetica-Bold", 10)
        if dados.get('participou_ministerio'): can.drawString(168, y, "X")
        can.drawString(220, y, str(dados.get('estudos_biblicos', 0)))
        can.drawString(340, y, str(dados.get('horas', 0)))
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
    st.title("📊 Administração Parque Aliança")
    
    # 1. CARREGAR DADOS
    membros_db = gerenciar_membros("listar")
    relatorios_brutos = carregar_relatorios()
    
    # 2. ABA DE GESTÃO (PREVENTIVA)
    aba_rel, aba_gestao = st.tabs(["📝 PAINEL DE RELATÓRIOS", "⚙️ GESTÃO DE PESSOAS"])

    with aba_gestao:
        st.subheader("Cadastrar Novo Publicador")
        with st.form("form_cadastro"):
            nome_c = st.text_input("Nome Completo")
            cat_c = st.selectbox("Categoria", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"])
            if st.form_submit_button("Confirmar Cadastro"):
                if nome_c:
                    gerenciar_membros("salvar", {"nome": nome_c, "categoria": cat_c})
                    st.success(f"{nome_c} cadastrado!")
                    st.rerun()

    # 3. PROCESSAMENTO DOS RELATÓRIOS
    if not relatorios_brutos:
        with aba_rel: st.info("Nenhum relatório enviado ainda.")
        return

    df = pd.DataFrame(relatorios_brutos)
    
    # Garantir que a coluna categoria existe baseada no cadastro de membros
    def vincular_categoria(nome_relatorio):
        membro = membros_db.get(nome_relatorio)
        if membro: return membro['categoria']
        return "PUBLICADOR" # Fallback

    df['categoria'] = df['nome'].apply(vincular_categoria)

    meses = sorted(df['mes_referencia'].unique())
    mes_sel = st.sidebar.selectbox("📅 Selecione o Mês", meses, index=len(meses)-1)
    df_mes = df[df['mes_referencia'] == mes_sel]

    with aba_rel:
        col1, col2, col3 = st.columns(3)
        cats = [("PUBLICADOR", "Publicadores", "card-pub"), 
                ("PIONEIRO AUXILIAR", "Auxiliares", "card-aux"), 
                ("PIONEIRO REGULAR", "Regulares", "card-reg")]

        for i, (cat_id, cat_label, cor) in enumerate(cats):
            with [col1, col2, col3][i]:
                df_cat = df_mes[df_mes['categoria'] == cat_id]
                
                # --- CARD CONSOLIDADO ---
                st.markdown(f"""<div class="card {cor}">
                    <div class="metric-label">TOTAL {cat_label}</div>
                    <div class="metric-value">⏱️ {int(df_cat['horas'].sum())}h | 📖 {int(df_cat['estudos_biblicos'].sum())} Est.</div>
                    <div class="metric-label">Relatórios: {len(df_cat)}</div>
                </div>""", unsafe_allow_html=True)

                # --- CARDS INDIVIDUAIS (DADOS ABERTOS) ---
                for _, row in df_cat.iterrows():
                    st.markdown(f"""<div class="card {cor}">
                        <div class="metric-label">Publicador</div>
                        <div class="metric-value">{row['nome']}</div>
                        <div class="metric-label">Relatório</div>
                        <div class="metric-value">Horas: {row['horas']} | Estudos: {row['estudos_biblicos']}</div>
                        <div class="metric-label">Participação</div>
                        <div class="metric-value">{'✅ SIM' if row['participou_ministerio'] else '❌ NÃO'}</div>
                        {f'<div class="obs-box"><b>Obs:</b> {row["observacoes"]}</div>' if row['observacoes'] else ''}
                    </div>""", unsafe_allow_html=True)
                    
                    # Botão de PDF
                    pdf = gerar_pdf_s4t(row)
                    if pdf:
                        st.download_button("📥 PDF S-4-T", pdf, f"S4T_{row['nome']}.pdf", "application/pdf", key=f"btn_{row['id']}")

        st.divider()
        st.subheader("Pendentes de Envio")
        entregaram = df_mes['nome'].tolist()
        pendentes = [n for n, d in membros_db.items() if n not in entregaram and d['categoria'] != "INATIVO"]
        
        if pendentes:
            cols_p = st.columns(4)
            for j, p_nome in enumerate(pendentes):
                with cols_p[j % 4]:
                    st.markdown(f"""<div class="card card-pendente">
                        <div class="metric-label">{membros_db[p_nome]['categoria']}</div>
                        <div class="metric-value">⚠️ {p_nome}</div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.success("Todos os relatórios foram entregues!")

if __name__ == "__main__":
    main()
