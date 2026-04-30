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
# --- Motores de PDF ---
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO (Preservada) ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .triagem-box { background-color: #fff4e5; padding: 15px; border-radius: 10px; border: 1px solid #ffa94d; margin-bottom: 10px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- NOVA FUNÇÃO S-21 (Usando seu modelo oficial s21.pdf) ---
def gerar_pdf_registro_s21(row, mes_sel):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica-Bold", 10)
    
    # Nome (Coordenada aproximada do campo Nome no S-21)
    can.drawString(24*mm, 258*mm, str(row['nome_oficial']).upper())
    
    # Mapeamento do Eixo Y por Mês (Baseado no layout padrão do S-21)
    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5
    }
    
    mes_nome = mes_sel.split()[0].upper()
    y_pos = y_map.get(mes_nome, 148.5) * mm
    
    # Participou (X)
    if int(row['horas']) > 0 or int(row['estudos_biblicos']) > 0:
        can.drawCentredString(53.5*mm, y_pos, "X")
    
    # Estudos Bíblicos
    can.drawCentredString(80.5*mm, y_pos, str(int(row['estudos_biblicos'])))
    
    # Pioneiro Auxiliar (X)
    if row['cat_oficial'] == "PIONEIRO AUXILIAR":
        can.drawCentredString(97.5*mm, y_pos, "X")
        
    # Horas
    can.drawCentredString(116.5*mm, y_pos, str(int(row['horas'])))
    
    # Observações
    obs = str(row.get('observacoes', ''))[:30]
    if obs:
        can.setFont("Helvetica", 8)
        can.drawString(133*mm, y_pos, obs)
    
    can.save()
    packet.seek(0)

    try:
        reader_original = PdfReader(open(path_original, "rb"))
        writer = PdfWriter()
        pagina_base = reader_original.pages[0]
        overlay_pdf = PdfReader(packet)
        pagina_base.merge_page(overlay_pdf.pages[0])
        writer.add_page(pagina_base)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
    except:
        return None

# --- FUNÇÃO CONSOLIDADA (Preservada como está) ---
def gerar_pdf_consolidado_geral(df_dados, titulo_principal, subtitulo, label_entidade, valor_entidade):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontSize=16, alignment=1, spaceAfter=20, fontName='Helvetica-Bold')
    elements.append(Paragraph(titulo_principal, title_style))
    data_cabecalho = [[Paragraph(f"<b>{label_entidade}:</b> {valor_entidade}", styles['Normal']), ""], [f"{subtitulo}", ""]]
    t_cabecalho = Table(data_cabecalho, colWidths=[350, 150])
    elements.append(t_cabecalho)
    elements.append(Spacer(1, 15))
    header = ["Mês", "Estudos", "Horas"]
    corpo = [[str(row['Mês']), str(int(row['Estudos'])), str(int(row['Horas']))] for _, row in df_dados.iterrows()]
    t_dados = Table([header] + corpo, colWidths=[200, 100, 100])
    t_dados.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t_dados)
    doc.build(elements)
    return buffer.getvalue()

# --- FUNÇÕES DE BANCO (Preservadas) ---
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
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria, "nome_oficial": nome}, merge=True)

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db: 
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório removido!")

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

def validar_e_gravar_novo_membro(relatorio_id, nome_final, categoria):
    db = inicializar_db()
    if not db: return
    db.collection("membros_v2").document(nome_final).set({"categoria": categoria, "nome_oficial": nome_final}, merge=True)
    db.collection("relatorios_parque_alianca").document(relatorio_id).update({"nome": nome_final})
    st.success(f"Membro {nome_final} validado!")

# --- MAIN (Logica Original Mantida) ---
def main():
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

    tabs_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "⚙️ CONFIGURAÇÃO"])

    with tabs_principal[0]:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
        sub_tabs_rel = st.tabs(["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "⏳ PENDÊNCIAS"])
        for i, cat in enumerate(categorias_lista):
            with sub_tabs_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()
                if df_cat.empty: st.info(f"Nenhum relatório de {cat} recebido.")
                else:
                    cols = st.columns(4)
                    for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                        with cols[idx % 4]:
                            st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>', unsafe_allow_html=True)
                            if st.button(f"🗑️ Deletar", key=f"del_rel_{r['id']}"):
                                deletar_relatorio(r['id']); st.rerun()

        with sub_tabs_rel[3]:
            for cat in categorias_lista:
                membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
                pendentes = sorted([n for n in membros_cat if n not in entregaram])
                if pendentes:
                    st.warning(f"**{cat}** ({len(pendentes)})")
                    for p_nome in pendentes:
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.write(f"• {p_nome}")
                        if c3.button("📥 Baixa Manual", key=f"pend_baixa_{p_nome}"):
                            inicializar_db().collection("relatorios_parque_alianca").add({"nome": p_nome, "mes_referencia": mes_sel, "horas": 0, "estudos_biblicos": 0, "observacoes": "Baixa manual"})
                            st.rerun()

    with tabs_principal[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if not df_triagem.empty:
            nomes_existentes = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.markdown(f'<b>Digitado:</b> {row["nome"]}', unsafe_allow_html=True)
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_existentes)
                    n_s = st.selectbox("Confirmar Membro:", ["-- Selecionar --"] + nomes_existentes, index=nomes_existentes.index(sugestao)+1 if sugestao else 0, key=f"tri_s_{row['id']}")
                    if st.button("✅ VALIDAR", key=f"tri_v_{row['id']}"):
                        validar_e_gravar_novo_membro(row['id'], n_s, "PUBLICADOR")
                        st.rerun()

    with tabs_principal[2]:
        sub_tabs_cons_master = st.tabs(["📊 POR CATEGORIA", "👤 POR PESSOA"])
        with sub_tabs_cons_master[0]:
            if not df.empty:
                df_cons = df[df['status_validacao'] == "IDENTIFICADO"]
                for i, cat in enumerate(categorias_lista):
                    df_cat_total = df_cons[df_cons['cat_oficial'] == cat]
                    if not df_cat_total.empty:
                        resumo = df_cat_total.groupby('mes_referencia').agg({'estudos_biblicos': 'sum', 'horas': 'sum', 'nome_oficial': 'count'}).reset_index()
                        resumo.columns = ['Mês', 'Estudos', 'Horas', 'Relatórios']
                        st.write(f"### {cat}")
                        st.dataframe(resumo, hide_index=True)
                        pdf_cat = gerar_pdf_consolidado_geral(resumo, "CONSOLIDADO DE CATEGORIA", "2026", "Categoria", cat)
                        st.download_button(f"📥 Baixar PDF {cat}", pdf_cat, f"Consol_{cat}.pdf")

        with sub_tabs_cons_master[1]:
            membro_sel = st.selectbox("Selecione o Publicador", sorted(list(membros_db.keys())))
            if membro_sel:
                df_pessoal = df[(df['nome_oficial'] == membro_sel) & (df['status_validacao'] == "IDENTIFICADO")]
                if not df_pessoal.empty:
                    resumo_pessoal = df_pessoal.sort_values('mes_referencia')[['mes_referencia', 'estudos_biblicos', 'horas']]
                    resumo_pessoal.columns = ['Mês', 'Estudos', 'Horas']
                    st.table(resumo_pessoal)
                    pdf_pessoal = gerar_pdf_consolidado_geral(resumo_pessoal, "HISTÓRICO INDIVIDUAL", "2026", "Publicador", membro_sel)
                    st.download_button("📥 Baixar Histórico (PDF)", pdf_pessoal, f"Hist_{membro_sel}.pdf")

    with tabs_principal[3]:
        st.subheader("Exportação Mensal S-21 (Modelo Oficial)")
        df_export = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        if not df_export.empty:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for _, r in df_export.iterrows():
                    pdf_bin = gerar_pdf_registro_s21(r, mes_sel)
                    if pdf_bin: zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf_bin)
            st.download_button("📥 BAIXAR TUDO ZIP (S-21 OFICIAL)", zip_buffer.getvalue(), f"S21_{mes_sel}.zip", "application/zip")

    st.caption("v2.3.0 | Parque Aliança | Modelo S-21 Integrado")

if __name__ == "__main__":
    main()
