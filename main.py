import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import base64
from difflib import SequenceMatcher
from google.cloud import firestore
from google.oauth2 import service_account
from pypdf import PdfReader, PdfWriter
from pypdf.generic import AnnotationBuilder

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def exibir_pdf(byte_data):
    """Renderiza o PDF em um iframe para visualização direta."""
    base64_pdf = base64.b64encode(byte_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def gerar_pdf_registro_s21(row, mes_sel):
    """Preenche o modelo oficial S-21-T carimbando os dados por cima."""
    try:
        reader = PdfReader("S21.pdf")
        page = reader.pages[0]
        writer = PdfWriter()
        writer.add_page(page)

        # Mapeamento de Y para cada mês no modelo S-21-T (11/23)
        coords_y = {
            "SETEMBRO": 532, "OUTUBRO": 512, "NOVEMBRO": 492, "DEZEMBRO": 472,
            "JANEIRO": 452, "FEVEREIRO": 432, "MARCO": 412, "ABRIL": 392,
            "MAIO": 372, "JUNHO": 352, "JULHO": 332, "AGOSTO": 312
        }
        
        mes_puro = normalizar_texto(mes_sel).split()[0].upper()
        y_pos = coords_y.get(mes_puro, 412)

        # 1. Nome do Publicador
        nome_anno = AnnotationBuilder.free_text(
            row['nome_oficial'].upper(),
            rect=(55, 718, 450, 735),
            font="Helvetica-Bold",
            font_size=11,
        )
        writer.add_annotation(page_number=0, annotation=nome_anno)

        # 2. Participou no Ministério (Checkmark)
        if row['horas'] > 0 or row['estudos_biblicos'] > 0:
            check_anno = AnnotationBuilder.free_text("X", rect=(191, y_pos, 205, y_pos+12), font_size=12)
            writer.add_annotation(page_number=0, annotation=check_anno)

        # 3. Estudos Bíblicos
        if row['estudos_biblicos'] > 0:
            estudos_anno = AnnotationBuilder.free_text(str(int(row['estudos_biblicos'])), rect=(273, y_pos, 305, y_pos+12), font_size=10)
            writer.add_annotation(page_number=0, annotation=estudos_anno)

        # 4. Horas
        if row['horas'] > 0:
            horas_anno = AnnotationBuilder.free_text(str(int(row['horas'])), rect=(518, y_pos, 560, y_pos+12), font_size=10)
            writer.add_annotation(page_number=0, annotation=horas_anno)

        # 5. Observações
        if row.get('observacoes'):
            obs_anno = AnnotationBuilder.free_text(row['observacoes'], rect=(610, y_pos, 800, y_pos+12), font_size=8)
            writer.add_annotation(page_number=0, annotation=obs_anno)

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")
        return b""

# --- FUNÇÕES DE BANCO ---
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
        st.toast("Relatório removido!")

def validar_e_gravar_novo_membro(relatorio_id, nome_correto, categoria):
    db = inicializar_db()
    if db:
        db.collection("membros_v2").document(nome_correto).set({"categoria": categoria}, merge=True)
        db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_correto})
        st.toast(f"✅ {nome_correto} validado!")

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

# --- MAIN ---
def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    
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

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["MARÇO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tabs_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⚙️ CONFIGURAÇÃO"])

    with tabs_principal[0]:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
        st.subheader(f"Resumo de {mes_sel}")
        sub_tabs_rel = st.tabs(["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "⏳ PENDÊNCIAS"])
        categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
        
        for i, cat in enumerate(categorias_lista):
            with sub_tabs_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()
                if df_cat.empty: st.info(f"Nenhum relatório de {cat} recebido.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{len(df_cat)}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-container"><div class="metric-label">Horas</div><div class="metric-value">{int(df_cat["horas"].sum())}h</div></div>', unsafe_allow_html=True)
                    m3.markdown(f'<div class="metric-container"><div class="metric-label">Estudos</div><div class="metric-value">{int(df_cat["estudos_biblicos"].sum())}</div></div>', unsafe_allow_html=True)
                    
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div>⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}</div>', unsafe_allow_html=True)
                            if st.button(f"🗑️ Deletar", key=f"del_rel_{r['id']}"):
                                deletar_relatorio(r['id']); st.rerun()

    with tabs_principal[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Tudo certo nos nomes!")
        else:
            nomes_existentes = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.write(f"**Digitado:** {row['nome']} | **Horas:** {row['horas']}")
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_existentes)
                    c1, c2 = st.columns(2)
                    n_s = c1.selectbox("Selecionar Oficial:", ["-- Novo Membro --"] + nomes_existentes, index=nomes_existentes.index(sugestao)+1 if sugestao else 0, key=f"tri_s_{row['id']}")
                    cat_n = c2.selectbox("Categoria:", categorias_lista, key=f"tri_c_{row['id']}")
                    if st.button("✅ VALIDAR", key=f"tri_v_{row['id']}", use_container_width=True):
                        validar_e_gravar_novo_membro(row['id'], n_s if n_s != "-- Novo Membro --" else row['nome'], cat_n)
                        st.rerun()

    with tabs_principal[2]:
        sub_tabs_cfg = st.tabs(["👤 MEMBROS", "📂 REGISTROS TOTAIS (PDF/PREVIEW)"])
        
        with sub_tabs_cfg[1]:
            st.subheader(f"Geração de Cartões S-21 - {mes_sel}")
            df_export = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"].sort_values('nome_oficial') if not df_mes.empty else pd.DataFrame()
            
            if df_export.empty: st.info("Sem dados para exportar.")
            else:
                col_ctrl, col_view = st.columns([1, 2])
                
                with col_ctrl:
                    st.write("#### 1. Conferência")
                    selecionado = st.selectbox("Visualizar rascunho de:", df_export['nome_oficial'].tolist())
                    
                    st.write("#### 2. Download em Massa")
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                        for _, r in df_export.iterrows():
                            pdf_data = gerar_pdf_registro_s21(r, mes_sel)
                            if pdf_data: zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf_data)
                    
                    st.download_button("📥 BAIXAR TUDO (ZIP)", zip_buffer.getvalue(), f"S21_{mes_sel}.zip", "application/zip", use_container_width=True)
                
                with col_view:
                    st.write(f"#### Preview Real: {selecionado}")
                    dados_view = df_export[df_export['nome_oficial'] == selecionado].iloc[0]
                    pdf_preview = gerar_pdf_registro_s21(dados_view, mes_sel)
                    if pdf_preview: exibir_pdf(pdf_preview)

    st.caption("S-4-T 11/23 | Parque Aliança | Gestão Administrativa")

if __name__ == "__main__":
    main()
