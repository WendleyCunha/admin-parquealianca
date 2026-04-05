import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata 
from pypdf import PdfReader, PdfWriter
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account

# --- NOVOS IMPORTS PARA O PDF ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
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

# --- FUNÇÃO DE NORMALIZAÇÃO ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- FUNÇÃO PARA GERAR PDF (VERSÃO OVERLAY COM FUNDO ORIGINAL) ---
def gerar_pdf_registro_s21(row, mes_sel):
    # 1. CRIAR CAMADA DE DADOS (TRANSPARENTE)
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # --- POSICIONAMENTO ---
    # Nome
    can.setFont("Helvetica-Bold", 11)
    can.drawString(70, 755, str(row['nome_oficial'])) 
    
    # Configuração de meses (Y inicial e espaçamento entre linhas da tabela S-21)
    y_pos_setembro = 635 
    espacamento_linhas = 18.5
    meses_lista = ["SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO", "JANEIRO", 
                   "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO"]
    
    try:
        nome_mes_puro = mes_sel.split(" ")[0].upper()
        if nome_mes_puro in meses_lista:
            indice_mes = meses_lista.index(nome_mes_puro)
            y_atual = y_pos_setembro - (indice_mes * espacamento_linhas)
            
            # X de participação
            if row['horas'] > 0 or row.get('estudos_biblicos', 0) > 0:
                can.drawString(205, y_atual, "X")
            
            # Estudos Bíblicos
            can.drawString(265, y_atual, str(int(row['estudos_biblicos'])))
            
            # Horas
            can.drawString(340, y_atual, str(int(row['horas'])))
            
            # Observações (limitado a 40 caracteres para não vazar a célula)
            if row.get('observacoes'):
                can.setFont("Helvetica", 8)
                can.drawString(410, y_atual, str(row['observacoes'])[:40])
    except:
        pass

    can.save()
    packet.seek(0)

    # 2. MESCLAR COM O PDF ORIGINAL
    try:
        # Tenta ler o arquivo template_s21.pdf que deve estar na sua pasta principal
        arquivo_base = PdfReader(open("template_s21.pdf", "rb"))
        camada_dados = PdfReader(packet)
        
        output = PdfWriter()
        pagina_principal = arquivo_base.pages[0]
        pagina_principal.merge_page(camada_dados.pages[0])
        output.add_page(pagina_principal)
        
        buffer_final = io.BytesIO()
        output.write(buffer_final)
        return buffer_final.getvalue()
        
    except FileNotFoundError:
        return "Erro: Arquivo template_s21.pdf não encontrado na raiz do projeto.".encode()
    except Exception as e:
        return f"Erro ao processar PDF: {str(e)}".encode()

# --- FUNÇÕES DE BANCO (Mantidas originais) ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except Exception as e:
            st.error(f"Erro de conexão: {e}"); return None
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
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório removido com sucesso!")

def editar_nome_membro(nome_antigo, nome_novo, categoria):
    db = inicializar_db()
    if db and nome_antigo != nome_novo:
        db.collection("membros_v2").document(nome_novo).set({"categoria": categoria})
        db.collection("membros_v2").document(nome_antigo).delete()

def validar_e_gravar_novo_membro(relatorio_id, nome_correto, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome_correto).set({"categoria": categoria}, merge=True)
        db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_correto})
        st.toast(f"✅ {nome_correto} validado!")

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match = None
    maior_score = 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        if entrada_norm == oficial_norm: return nome_oficial
        if entrada_norm in oficial_norm or oficial_norm in entrada_norm:
            score = 0.90
        else:
            score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score:
            maior_score = score
            melhor_match = nome_oficial
    return melhor_match if maior_score >= 0.80 else None

# --- MAIN ---
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

    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⏳ PENDÊNCIAS", "📂 REGISTROS", "⚙️ CONFIG"])

    with tabs[0]: # RELATÓRIOS RECEBIDOS
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        if df_ok.empty: st.info("Nenhum relatório identificado.")
        else:
            df_ok = df_ok.sort_values('nome_oficial')
            cats = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
            sub_tabs = st.tabs(cats)
            for i, cat in enumerate(cats):
                with sub_tabs[i]:
                    df_cat = df_ok[df_ok['cat_oficial'] == cat]
                    if not df_cat.empty:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Envios", len(df_cat))
                        m2.metric("Total Horas", int(df_cat["horas"].sum()))
                        m3.metric("Total Estudos", int(df_cat["estudos_biblicos"].sum()))
                        cols = st.columns(4)
                        for idx, (_, r) in enumerate(df_cat.iterrows()):
                            with cols[idx % 4]:
                                st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>', unsafe_allow_html=True)

    with tabs[1]: # TRIAGEM
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Triagem limpa!")
        else:
            for _, row in df_triagem.iterrows():
                with st.container():
                    st.markdown(f'<div class="triagem-box"><b>Digitado:</b> {row["nome"]}</div>', unsafe_allow_html=True)
                    if st.button(f"Validar {row['nome']}", key=f"btn_v_{row['id']}"):
                        validar_e_gravar_novo_membro(row['id'], row['nome'], "PUBLICADOR")
                        st.rerun()

    with tabs[2]: # PENDÊNCIAS
        st.write("Membros que ainda não enviaram relatório.")

    with tabs[3]: # EXPORTAÇÃO
        st.subheader(f"Exportação - {mes_sel}")
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        if df_ok.empty: st.info("Sem dados para exportar.")
        else:
            df_ok = df_ok.sort_values('nome_oficial')
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for _, r in df_ok.iterrows():
                    pdf_data = gerar_pdf_registro_s21(r, mes_sel)
                    zf.writestr(f"Registro_{r['nome_oficial']}.pdf", pdf_data)
            
            st.download_button("📥 Baixar Todos (ZIP)", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", "application/zip")
            for _, r in df_ok.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"👤 {r['nome_oficial']}")
                c2.download_button("PDF", gerar_pdf_registro_s21(r, mes_sel), f"S21_{r['nome_oficial']}.pdf", key=f"pdf_{r['id']}")

    with tabs[4]: # CONFIG
        st.write("Configurações de membros.")

if __name__ == "__main__":
    main()
