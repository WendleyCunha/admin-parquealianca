import streamlit as st
import pandas as pd
import json
import io
import zipfile
from google.cloud import firestore
from google.oauth2 import service_account
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

# --- FUNÇÕES DE APOIO E PDF ---
def gerar_pdf_registro(membro_nome, dados_membro, mes_ref, ano="2025"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=20)
    elements.append(Paragraph("REGISTRO DE PUBLICADOR DE CONGREGAÇÃO", title_style))
    
    # Cabeçalho
    header_data = [
        [f"Nome: {membro_nome}", ""],
        [f"Mês de Referência: {mes_ref}", f"Ano de Serviço: {ano}"]
    ]
    t_header = Table(header_data, colWidths=[350, 150])
    t_header.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
    elements.append(t_header)
    elements.append(Spacer(1, 12))
    
    # Tabela de Dados (Simulando a imagem)
    # Como o sistema salva por mês, aqui mostramos o registro do mês selecionado
    table_data = [
        ["Participou no Ministério", "Estudos Bíblicos", "Pioneiro Auxiliar", "Horas", "Observações"],
        ["[X]" if dados_membro['horas'] > 0 else "[ ]", 
         str(int(dados_membro['estudos_biblicos'])), 
         "[X]" if dados_membro['cat_oficial'] == "PIONEIRO AUXILIAR" else "[ ]", 
         str(int(dados_membro['horas'])), 
         dados_membro.get('observacoes', '')]
    ]
    
    t_main = Table(table_data, colWidths=[120, 80, 80, 60, 150], rowHeights=30)
    t_main.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_main)
    
    doc.build(elements)
    return buffer.getvalue()

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

def validar_e_gravar_novo_membro(relatorio_id, nome_correto, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome_correto).set({"categoria": categoria}, merge=True)
        db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_correto})
        st.toast(f"✅ {nome_correto} validado!")

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada = str(nome_recebido).strip().lower()
    if not entrada: return None
    for nome_oficial in lista_membros:
        if entrada in nome_oficial.lower(): return nome_oficial
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

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tabs = st.tabs(["📋 RECEBIDOS", "⚠️ TRIAGEM", "⏳ PENDÊNCIAS", "📂 REGISTROS TOTAIS", "⚙️ CONFIGURAÇÃO"])

    # --- ABA RECEBIDOS (Mantida) ---
    with tabs[0]:
        st.subheader(f"Relatórios de {mes_sel}")
        # ... (seu código de exibição de cards aqui)

    # --- ABA TRIAGEM (Mantida) ---
    with tabs[1]:
        # ... (seu código de triagem aqui)
        pass

    # --- ABA PENDÊNCIAS (Mantida) ---
    with tabs[2]:
        # ... (seu código de pendências aqui)
        pass

    # --- NOVA ABA: REGISTROS TOTAIS ---
    with tabs[3]:
        st.subheader(f"Gerar Documentos - {mes_sel}")
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        
        if df_ok.empty:
            st.warning("Sem dados validados para gerar registros neste mês.")
        else:
            col_a, col_b = st.columns([3, 1])
            
            with col_b:
                # Botão ZIP
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    for _, row in df_ok.iterrows():
                        pdf_data = gerar_pdf_registro(row['nome_oficial'], row, mes_sel)
                        zip_file.writestr(f"Registro_{row['nome_oficial']}_{mes_sel}.pdf", pdf_data)
                
                st.download_button(
                    label="📥 Baixar Todos (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"Relatorios_{mes_sel}.zip",
                    mime="application/zip",
                    use_container_width=True
                )

            # Tabela de visualização e download individual
            for _, row in df_ok.iterrows():
                with st.expander(f"📄 {row['nome_oficial']}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    c1.write(f"**Horas:** {int(row['horas'])}")
                    c2.write(f"**Estudos:** {int(row['estudos_biblicos'])}")
                    pdf_ind = gerar_pdf_registro(row['nome_oficial'], row, mes_sel)
                    c3.download_button(
                        "Baixar PDF",
                        data=pdf_ind,
                        file_name=f"Registro_{row['nome_oficial']}.pdf",
                        key=f"pdf_{row['id']}"
                    )

    # --- ABA CONFIGURAÇÃO (Com Novo Registro) ---
    with tabs[4]:
        st.subheader("🆕 Cadastrar Novo Membro")
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            novo_n = c1.text_input("Nome Completo", placeholder="Ex: João Silva")
            novo_c = c2.selectbox("Categoria", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
            if c3.button("Cadastrar", use_container_width=True):
                if novo_n:
                    atualizar_membro(novo_n, novo_c)
                    st.success("Membro cadastrado!")
                    st.rerun()
        
        st.markdown("---")
        st.subheader("Membros Cadastrados")
        # ... (seu código de lista de membros para excluir/editar aqui)

if __name__ == "__main__":
    main()
