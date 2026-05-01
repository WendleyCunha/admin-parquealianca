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

# Bibliotecas para preenchimento do PDF OFICIAL (Overlay)
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Admin Parque Aliança", layout="wide", page_icon="📊")

# --- ESTILIZAÇÃO ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 15px; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- MOTOR DE PREENCHIMENTO UNIFICADO (S-21 OFICIAL) ---
def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado no servidor.")
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    
    # 1. Cabeçalho - Ajustado para cima (260.5mm)
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24*mm, 260.5*mm, str(nome_cabecalho).upper())
    
    # 2. Mapeamento de Coordenadas Y (Ajustado para as linhas do formulário)
    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 197.0, "NOVEMBRO": 189.5, "DEZEMBRO": 182.0,
        "JANEIRO": 174.5, "FEVEREIRO": 167.0, "MARÇO": 159.5, "ABRIL": 152.0,
        "MAIO": 144.5, "JUNHO": 137.0, "JULHO": 129.5, "AGOSTO": 122.0
    }
    
    total_estudos = 0
    total_horas = 0

    # 3. Preenchimento Iterativo das Linhas
    for _, row in dados_rows.iterrows():
        mes_key = str(row['mes_referencia']).split()[0].upper()
        
        if mes_key in y_map:
            y_pos = y_map[mes_key] * mm
            
            # Conversão e Acúmulo
            estudos = int(row.get('estudos_biblicos', 0))
            horas = int(row.get('horas', 0))
            total_estudos += estudos
            total_horas += horas

            # Coluna: Participou (X)
            if horas > 0 or estudos > 0:
                can.drawCentredString(53.5*mm, y_pos, "X")
            
            # Coluna: Estudos Bíblicos
            can.drawCentredString(80.5*mm, y_pos, str(estudos))
            
            # Coluna: Pioneiro Auxiliar (X)
            if str(row.get('cat_oficial')).upper() == "PIONEIRO AUXILIAR" or "AUXILIAR" in str(categoria_label).upper():
                can.drawCentredString(97.5*mm, y_pos, "X")
                
            # Coluna: Horas
            can.drawCentredString(116.5*mm, y_pos, str(horas))
            
            # Coluna: Observações
            obs = str(row.get('observacoes', ''))[:30]
            if obs and obs.lower() != 'nan':
                can.setFont("Helvetica", 7)
                can.drawString(133*mm, y_pos, obs)
                can.setFont("Helvetica-Bold", 10)

    # 4. Preenchimento da Soma Total (Linha de baixo)
    y_total = 111.5 * mm
    can.setFont("Helvetica-Bold", 10)
    can.drawCentredString(80.5*mm, y_total, str(total_estudos))
    can.drawCentredString(116.5*mm, y_total, str(total_horas))

    can.save()
    packet.seek(0)

    # Mesclagem Final
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
    except Exception as e:
        st.error(f"Erro na mesclagem do PDF: {e}")
        return None

# --- FUNÇÕES DE BANCO E INTERFACE (Mantidas conforme sua lógica) ---

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
        st.subheader(f"Resumo de {mes_sel}")
        sub_tabs_rel = st.tabs(categorias_lista + ["⏳ PENDÊNCIAS"])
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
                            if st.button(f"🗑️ Deletar", key=f"del_rel_{r['id']}"):
                                deletar_relatorio(r['id']); st.rerun()

    with tabs_principal[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Tudo certo!")
        else:
            nomes_existentes = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.markdown(f"**Digitado:** {row['nome']}")
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_existentes)
                    idx_sug = nomes_existentes.index(sugestao) + 1 if sugestao else 0
                    c1, c2 = st.columns(2)
                    n_s = c1.selectbox("Vincular a:", ["-- Selecionar --"] + nomes_existentes, index=idx_sug, key=f"tri_s_{row['id']}")
                    cat_n = c2.selectbox("Categoria:", categorias_lista, key=f"tri_c_{row['id']}")
                    if st.button("✅ VALIDAR", key=f"tri_v_{row['id']}", use_container_width=True):
                        validar_e_gravar_novo_membro(row['id'], n_s, cat_n); st.rerun()

    with tabs_principal[2]:
        c_sub1, c_sub2 = st.tabs(["📊 POR CATEGORIA", "👤 POR PESSOA"])
        with c_sub1:
            cat_sel = st.selectbox("Selecione a Categoria para Consolidado", categorias_lista)
            df_cons = df[df['status_validacao'] == "IDENTIFICADO"]
            df_cat_total = df_cons[df_cons['cat_oficial'] == cat_sel]
            if not df_cat_total.empty:
                resumo_cat = df_cat_total.groupby('mes_referencia').agg({'horas': 'sum', 'estudos_biblicos': 'sum'}).reset_index()
                st.dataframe(resumo_cat, use_container_width=True)
                pdf_cat = gerar_pdf_padrao_s21(f"CONSOLIDADO: {cat_sel}S", cat_sel, resumo_cat)
                st.download_button(f"📥 Baixar Cartão S-21 ({cat_sel})", pdf_cat, f"S21_Consolidado_{cat_sel}.pdf")
        with c_sub2:
            pessoa_sel = st.selectbox("Selecione o Publicador para Histórico", sorted(list(membros_db.keys())))
            if pessoa_sel:
                df_pessoal = df[(df['nome_oficial'] == pessoa_sel) & (df['status_validacao'] == "IDENTIFICADO")].sort_values('mes_referencia')
                if not df_pessoal.empty:
                    pdf_h = gerar_pdf_padrao_s21(pessoa_sel, membros_db[pessoa_sel].get('categoria'), df_pessoal)
                    st.download_button(f"📥 Baixar Cartão S-21 Completo: {pessoa_sel}", pdf_h, f"S21_Historico_{pessoa_sel}.pdf")

    with tabs_principal[3]:
        sub_tabs_cfg = st.tabs(["👤 MEMBROS", "📂 REGISTROS OFICIAIS (ZIP)"])
        with sub_tabs_cfg[1]:
            df_export = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
            if not df_export.empty:
                if st.button("🚀 GERAR ZIP COM TODOS S-21 DO MÊS"):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "a") as zf:
                        for _, r in df_export.iterrows():
                            pdf_data = gerar_pdf_padrao_s21(r['nome_oficial'], r['cat_oficial'], pd.DataFrame([r]))
                            if pdf_data: zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf_data)
                    st.download_button("📥 BAIXAR ZIP", zip_buffer.getvalue(), f"S21_{mes_sel}.zip")

    st.caption("v2.3.2 | Parque Aliança | Gestão Administrativa Unificada")

if __name__ == "__main__":
    main()
