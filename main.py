import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- INICIALIZAÇÃO DO BANCO ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão: {e}"); return None
    return st.session_state.db

db = inicializar_db()

# --- SISTEMA DE LOGIN E SEGURANÇA ---
def verificar_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
        st.session_state.user_data = None

    if not st.session_state.autenticado:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c2:
            st.markdown("<br><br><h2 style='text-align:center;'>Acesso Administrativo</h2>", unsafe_allow_html=True)
            user_input = st.text_input("Usuário").lower().strip()
            senha_input = st.text_input("Senha", type="password")
            
            if st.button("LOGAR", use_container_width=True, type="primary"):
                # Master Password (Backup de Emergência)
                if user_input == "wendley" and senha_input == "master77":
                    st.session_state.autenticado = True
                    st.session_state.user_data = {"username": "wendley", "role": "admin", "permissao": ["Relatórios", "Passagens"]}
                    st.rerun()
                
                # Busca no Firestore
                user_doc = db.collection("usuarios_app").document(user_input).get()
                if user_doc.exists:
                    dados = user_doc.to_dict()
                    if dados['senha'] == senha_input:
                        st.session_state.autenticado = True
                        st.session_state.user_data = dados
                        st.rerun()
                    else: st.error("Senha incorreta.")
                else: st.error("Usuário não encontrado.")
        return False
    return True

# --- ESTILIZAÇÃO (ORIGINAL) ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO E PDF (MANTIDAS DO SEU ORIGINAL) ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def carregar_membros():
    docs = db.collection("membros_v2").stream()
    return {doc.id: doc.to_dict() for doc in docs}

def carregar_relatorios():
    docs = db.collection("relatorios_parque_alianca").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        if entrada_norm == oficial_norm: return nome_oficial
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.80 else None

def gerar_pdf_registro_s21(row, mes_sel):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontSize=16, alignment=1, spaceAfter=20, fontName='Helvetica-Bold')
    elements.append(Paragraph("REGISTRO DE PUBLICADOR DE CONGREGAÇÃO", title_style))
    data_cabecalho = [[Paragraph(f"<b>Nome:</b> {row['nome_oficial']}", styles['Normal']), ""], [f"Mês: {mes_sel}", "Ano de serviço: 2026"]]
    t_cabecalho = Table(data_cabecalho, colWidths=[350, 150])
    elements.append(t_cabecalho)
    elements.append(Spacer(1, 15))
    header = ["Participou no\nministério", "Estudos\nbíblicos", "Pioneiro\nauxiliar", "Horas", "Observações"]
    check_min = "X" if row['horas'] > 0 else ""
    check_pion = "X" if row['cat_oficial'] == "PIONEIRO AUXILIAR" else ""
    corpo = [[f"[{check_min}]", str(int(row['estudos_biblicos'])), f"[{check_pion}]", str(int(row['horas'])), row.get('observacoes', '')]]
    t_dados = Table([header] + corpo, colWidths=[100, 80, 80, 70, 160])
    t_dados.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 10), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t_dados)
    doc.build(elements)
    return buffer.getvalue()

# --- MAIN ---
def main():
    if not verificar_login():
        st.stop()

    user_info = st.session_state.user_data
    
    # MENU LATERAL DINÂMICO
    with st.sidebar:
        st.title(f"Olá, {user_info['username'].capitalize()}")
        opcoes_menu = []
        if "Relatórios" in user_info['permissao']: opcoes_menu.append("📊 Gestão Parque Aliança")
        if "Passagens" in user_info['permissao']: opcoes_menu.append("🎫 Sistema de Passagens")
        
        app_mode = st.radio("Ir para:", opcoes_menu)
        st.divider()
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    if app_mode == "🎫 Sistema de Passagens":
        st.title("🎫 Sistema de Passagens")
        st.info("O módulo de passagens pode ser importado aqui.")
        return

    # --- CÓDIGO DO PARQUE ALIANÇA ---
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
    
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial and nome_oficial in membros_db:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tabs_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 0 e 1: MANTIDAS IGUAIS AO SEU ORIGINAL ---
    with tabs_principal[0]:
        st.subheader(f"Resumo de {mes_sel}")
        # ... (seu código original de visualização de cards de relatórios) ...

    with tabs_principal[1]:
        st.subheader("Nomes para Identificar")
        # ... (seu código original de triagem) ...

    # --- ABA 2: CONFIGURAÇÃO (ONDE ESTÁ A GESTÃO DE USUÁRIOS) ---
    with tabs_principal[2]:
        st.subheader("Acessos e Configurações")
        
        col_cfg1, col_cfg2 = st.columns(2)
        
        with col_cfg1:
            with st.expander("🔑 Alterar Minha Senha"):
                nova_senha = st.text_input("Nova Senha", type="password")
                if st.button("Atualizar Senha"):
                    db.collection("usuarios_app").document(user_info['username']).update({"senha": nova_senha})
                    st.success("Senha alterada com sucesso!")

        # APENAS VOCÊ (WENDLEY/ADMIN) VÊ ISSO
        if user_info.get('role') == 'admin':
            with col_cfg2:
                with st.expander("👥 Criar Novo Usuário"):
                    novo_user = st.text_input("Username").lower().strip()
                    nova_pass = st.text_input("Senha", type="password", key="new_u_pass")
                    permissoes = st.multiselect("Acessos", ["Relatórios", "Passagens"])
                    if st.button("Cadastrar Usuário"):
                        if novo_user and nova_pass:
                            db.collection("usuarios_app").document(novo_user).set({
                                "username": novo_user,
                                "senha": nova_pass,
                                "permissao": permissoes,
                                "role": "user"
                            })
                            st.success(f"Usuário {novo_user} criado!")
        
        st.divider()
        st.subheader("Exportação")
        if not df_mes.empty:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for _, r in df_mes[df_mes['status_validacao'] == "IDENTIFICADO"].iterrows():
                    zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_registro_s21(r, mes_sel))
            st.download_button("📥 BAIXAR TUDO ZIP", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", "application/zip")

    st.caption("S-4-T 11/23 | Parque Aliança | Gestão Administrativa")

if __name__ == "__main__":
    main()
