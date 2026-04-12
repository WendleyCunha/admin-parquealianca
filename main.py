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

# --- SEGURANÇA: INICIALIZAÇÃO DE ESTADOS ---
def inicializar_estados():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    if "user_data" not in st.session_state:
        # Inicializa com estrutura vazia para evitar AttributeError
        st.session_state.user_data = {"username": "", "permissao": [], "role": "user"}

# --- SISTEMA DE LOGIN ---
def verificar_login():
    inicializar_estados()
    
    if not st.session_state.autenticado:
        c1, c2, c3 = st.columns([1, 1.2, 1])
        with c2:
            st.markdown("<br><br><h2 style='text-align:center;'>Acesso Administrativo</h2>", unsafe_allow_html=True)
            user_input = st.text_input("Usuário", key="login_user").lower().strip()
            senha_input = st.text_input("Senha", type="password", key="login_pass")
            
            if st.button("LOGAR", use_container_width=True, type="primary"):
                # Master Password
                if user_input == "wendley" and senha_input == "master77":
                    st.session_state.autenticado = True
                    st.session_state.user_data = {"username": "wendley", "role": "admin", "permissao": ["Relatórios", "Passagens"]}
                    st.rerun()
                
                # Busca no Firestore
                user_doc = db.collection("usuarios_app").document(user_input).get()
                if user_doc.exists:
                    dados = user_doc.to_dict()
                    if dados.get('senha') == senha_input:
                        st.session_state.autenticado = True
                        st.session_state.user_data = dados
                        st.rerun()
                    else: st.error("Senha incorreta.")
                else: st.error("Usuário não encontrado.")
        return False
    return True

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
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
    # 1. Garante inicialização antes de qualquer acesso
    inicializar_estados()
    
    # 2. Bloqueia se não logado
    if not verificar_login():
        st.stop()

    # 3. Acesso seguro ao user_data
    user_info = st.session_state.user_data
    permissoes_usuario = user_info.get('permissao', [])
    
    # MENU LATERAL DINÂMICO
    with st.sidebar:
        st.title(f"Olá, {user_info.get('username', 'Usuário').capitalize()}")
        opcoes_menu = []
        if "Relatórios" in permissoes_usuario: opcoes_menu.append("📊 Gestão Parque Aliança")
        if "Passagens" in permissoes_usuario: opcoes_menu.append("🎫 Sistema de Passagens")
        
        if not opcoes_menu:
            st.error("Sem permissões. Contate Wendley.")
            st.stop()
            
        app_mode = st.radio("Ir para:", opcoes_menu)
        st.divider()
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.session_state.user_data = None
            st.rerun()

    if app_mode == "🎫 Sistema de Passagens":
        st.title("🎫 Sistema de Passagens")
        st.info("Módulo de passagens ativo para este usuário.")
        return

    # --- LÓGICA GESTÃO PARQUE ALIANÇA ---
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

    with tabs_principal[0]:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        st.subheader(f"Resumo de {mes_sel}")
        sub_tabs_rel = st.tabs(["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "⏳ PENDÊNCIAS"])
        
        for i, cat in enumerate(categorias_lista):
            with sub_tabs_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()
                if df_cat.empty: st.info(f"Nenhum relatório de {cat} recebido.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{len(df_cat)}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-container"><div class="metric-label">Total Horas</div><div class="metric-value">{int(df_cat["horas"].sum())}h</div></div>', unsafe_allow_html=True)
                    m3.markdown(f'<div class="metric-container"><div class="metric-label">Total Estudos</div><div class="metric-value">{int(df_cat["estudos_biblicos"].sum())}</div></div>', unsafe_allow_html=True)
                    
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>', unsafe_allow_html=True)

    with tabs_principal[1]:
        st.subheader("Nomes para Identificar")
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Tudo certo nos nomes!")
        else:
            st.dataframe(df_triagem[['nome', 'horas', 'mes_referencia']], use_container_width=True)

    with tabs_principal[2]:
        st.subheader("Painel de Controle e Acessos")
        col_cfg1, col_cfg2 = st.columns(2)
        
        with col_cfg1:
            with st.expander("🔑 Alterar Minha Senha"):
                nova_senha = st.text_input("Nova Senha", type="password")
                if st.button("Atualizar Minha Senha"):
                    db.collection("usuarios_app").document(user_info['username']).update({"senha": nova_senha})
                    st.success("Senha alterada!")

        if user_info.get('role') == 'admin':
            with col_cfg2:
                with st.expander("👥 Gerenciar Usuários (Novo)"):
                    novo_user = st.text_input("Nome do Usuário").lower().strip()
                    nova_pass = st.text_input("Senha", type="password", key="reg_pass")
                    perms = st.multiselect("Acessos", ["Relatórios", "Passagens"])
                    if st.button("Salvar Novo Usuário"):
                        if novo_user and nova_pass:
                            db.collection("usuarios_app").document(novo_user).set({
                                "username": novo_user, "senha": nova_pass, "permissao": perms, "role": "user"
                            })
                            st.success(f"Usuário {novo_user} cadastrado!")
        
        st.divider()
        st.subheader("📦 Exportação S-21")
        if not df_mes.empty:
            df_export = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
            if not df_export.empty:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for _, r in df_export.iterrows():
                        zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_registro_s21(r, mes_sel))
                st.download_button("📥 BAIXAR TUDO ZIP", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", "application/zip", use_container_width=True)

    st.caption("S-4-T 11/23 | Parque Aliança | Gestão Administrativa")

if __name__ == "__main__":
    main()
