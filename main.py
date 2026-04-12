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
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão S-21 Parque Aliança", layout="wide", page_icon="📝")

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e2e8f0; border-radius: 4px 4px 0px 0px; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #002366 !important; color: white !important; }
    .metric-card {
        background: white; padding: 20px; border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid #002366;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE PDF (O CORAÇÃO DO FORMULÁRIO) ---
def gerar_pdf_s21(row, mes_sel):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título Principal
    title_style = ParagraphStyle('Title', fontSize=14, alignment=1, spaceAfter=10, fontName='Helvetica-Bold')
    elements.append(Paragraph("REGISTRO DE PUBLICADOR DE CONGREGAÇÃO", title_style))
    
    # Cabeçalho (Nome e Dados)
    nome = row['nome_oficial'].upper()
    cat = row['cat_oficial']
    
    # Simulação de Checkboxes do formulário original
    chk_anc = "[  ] Ancião"
    chk_serv = "[  ] Servo ministerial"
    chk_reg = "[X]" if cat == "PIONEIRO REGULAR" else "[  ]"
    chk_aux = "[X]" if cat == "PIONEIRO AUXILIAR" else "[  ]"
    
    data_cabecalho = [
        [Paragraph(f"<b>Nome:</b> {nome}", styles['Normal']), ""],
        [f"Mês: {mes_sel}", "Ano de serviço: 2026"],
        [f"{chk_reg} Pioneiro regular   {chk_aux} Pioneiro auxiliar", ""]
    ]
    t_cabecalho = Table(data_cabecalho, colWidths=[300, 200])
    elements.append(t_cabecalho)
    elements.append(Spacer(1, 10))
    
    # Tabela de Dados (Simulando o layout da imagem)
    header = ["Mês", "Participou no\nministério", "Estudos\nbíblicos", "Pioneiro\nauxiliar", "Horas", "Observações"]
    
    # Lógica de preenchimento baseada no relatório
    part = "X" if row['horas'] > 0 or row.get('participou', False) else ""
    estudos = str(int(row['estudos_biblicos'])) if row['estudos_biblicos'] > 0 else "0"
    pion_aux = "X" if cat == "PIONEIRO AUXILIAR" else ""
    horas = str(int(row['horas'])) if row['horas'] > 0 else ""
    obs = row.get('observacoes', "")

    corpo = [[mes_sel.split()[0], f"[{part}]", estudos, f"[{pion_aux}]", horas, obs]]
    
    # Estilo da Tabela para ficar parecida com o impresso
    t_dados = Table([header] + corpo, colWidths=[80, 80, 60, 60, 50, 180])
    t_dados.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    
    elements.append(t_dados)
    doc.build(elements)
    return buffer.getvalue()

def show_pdf(bytes_data):
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="400" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- LÓGICA DE DADOS (FIRESTORE) ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except: return None
    return st.session_state.db

# ... (Funções carregar_membros, carregar_relatorios, normalizar_nome_no_banco permanecem como no seu original)

def main():
    st.title("🏛️ Sistema de Gestão Parque Aliança")
    db = inicializar_db()
    
    # Carregamento Inicial
    membros_db = carregar_membros() # Pega do Firestore
    relatorios_brutos = carregar_relatorios()
    
    # Processamento de Dados
    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        # Lógica de validação de nomes (seu código original de triagem)
        # ...

    # Interface de Abas
    tab_dash, tab_impressao, tab_inativos, tab_config = st.tabs([
        "📊 Painel Geral", "🖨️ Impressão S-21", "👤 Inativos", "⚙️ Configurações"
    ])

    with tab_dash:
        st.subheader("Resumo do Mês")
        # Colunas de métricas para soma automática
        if not df.empty:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="metric-card"><b>Total Horas</b><br><span style="font-size:24px">{int(df["horas"].sum())}h</span></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="metric-card"><b>Estudos</b><br><span style="font-size:24px">{int(df["estudos_biblicos"].sum())}</span></div>', unsafe_allow_html=True)
            
            # Tabela de quem entregou vs quem não entregou
            entregaram = df['nome_oficial'].tolist()
            pendentes = [n for n in membros_db.keys() if n not in entregaram and membros_db[n].get('categoria') != "INATIVO"]
            
            st.write("---")
            col_ent, col_pend = st.columns(2)
            with col_ent:
                st.success(f"✅ Entregaram ({len(entregaram)})")
                st.dataframe(df[['nome_oficial', 'cat_oficial', 'horas']], use_container_width=True)
            with col_pend:
                st.error(f"⏳ Pendentes ({len(pendentes)})")
                for p in pendentes:
                    st.write(f"• {p}")

    with tab_impressao:
        st.subheader("Gerador de Formulários Mensais")
        if not df.empty:
            pessoa_sel = st.selectbox("Selecione o Publicador para visualizar", df['nome_oficial'].unique())
            dados_pessoa = df[df['nome_oficial'] == pessoa_sel].iloc[0]
            
            col_pre, col_btn = st.columns([2, 1])
            with col_pre:
                st.write("### Pré-visualização")
                pdf_preview = gerar_pdf_s21(dados_pessoa, "MARÇO 2026")
                show_pdf(pdf_preview)
            
            with col_btn:
                st.write("### Ações")
                st.download_button("📥 Baixar PDF Individual", pdf_preview, f"S21_{pessoa_sel}.pdf", "application/pdf")
                
                # Botão para ZIP completo
                if st.button("📦 Gerar ZIP de Todos"):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a") as zf:
                        for _, r in df.iterrows():
                            zf.writestr(f"S21_{r['nome_oficial']}.pdf", gerar_pdf_s21(r, "MARÇO 2026"))
                    st.download_button("📥 Baixar Todos (ZIP)", zip_buffer.getvalue(), "Relatorios_Mensais.zip")

    with tab_inativos:
        st.subheader("Lista de Inativos")
        inativos = [n for n, d in membros_db.items() if d.get('categoria') == "INATIVO"]
        if inativos:
            for n in inativos:
                c1, c2 = st.columns([3, 1])
                c1.write(f"🚫 {n}")
                if c2.button("Reativar", key=f"react_{n}"):
                    db.collection("membros_v2").document(n).update({"categoria": "PUBLICADOR"})
                    st.rerun()
        else:
            st.info("Nenhum membro inativo no momento.")

    # ... Resto do seu código de configuração e triagem

if __name__ == "__main__":
    main()
