import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
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
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; position: relative; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; margin-right: 25px; }
    .metric-container { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: bold; color: #002366; }
    .metric-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÃO MESTRE: PREENCHIMENTO DE PDF ORIGINAL (S-21) ---
def preencher_s21_original(pdf_template, dados_row, mes_sel):
    """Preenche o PDF original S-21 e fixa o conteúdo para visualização imediata."""
    try:
        pdf_template.seek(0)
        reader = PdfReader(pdf_template)
        writer = PdfWriter()
        
        # Copia as páginas do original
        page = reader.pages[0]
        writer.add_page(page)
        
        # Coordenadas Y (Grid S-21-T 11/23)
        coords_y = {
            "SETEMBRO": 532, "OUTUBRO": 512, "NOVEMBRO": 492, "DEZEMBRO": 472,
            "JANEIRO": 452, "FEVEREIRO": 432, "MARÇO": 412, "ABRIL": 392,
            "MAIO": 372, "JUNHO": 352, "JULHO": 332, "AGOSTO": 312
        }
        
        mes_puro = str(mes_sel).split()[0].upper()
        y_base = coords_y.get(mes_puro, 412)

        # 1. Nome
        nome_txt = str(dados_row.get('nome_oficial', ''))
        # Note que usamos writer.pages[0] para adicionar a anotação
        writer.add_annotation(page_number=0, annotation=AnnotationBuilder.free_text(
            nome_txt, rect=(55, 718, 400, 735), font="Helvetica-Bold", font_size=11
        ))
        
        # 2. Participou (X)
        if dados_row['horas'] > 0 or dados_row.get('estudos_biblicos', 0) > 0:
            writer.add_annotation(page_number=0, annotation=AnnotationBuilder.free_text(
                "X", rect=(191, y_base, 205, y_base + 12), font_size=12
            ))

        # 3. Estudos Bíblicos
        if dados_row['estudos_biblicos'] > 0:
            writer.add_annotation(page_number=0, annotation=AnnotationBuilder.free_text(
                str(int(dados_row['estudos_biblicos'])),
                rect=(273, y_base, 305, y_base + 12), font_size=10
            ))

        # 4. Horas
        if dados_row['horas'] > 0:
            writer.add_annotation(page_number=0, annotation=AnnotationBuilder.free_text(
                str(int(dados_row['horas'])),
                rect=(518, y_base, 560, y_base + 12), font_size=10
            ))

        # --- O SEGREDO PARA NÃO FICAR EM BRANCO ---
        # Força o PDF a mostrar as anotações como conteúdo da página
        for page in writer.pages:
            writer.page_to_array(page) # Prepara a página
            
        # Esta função mescla as anotações ao "desenho" do PDF
        # Disponível nas versões recentes do pypdf
        # Se sua versão for antiga, remova o 'capabilities'
        # writer.flatten() 

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
        
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return None

# --- FUNÇÕES DE APOIO ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# --- FUNÇÕES DE BANCO (FIRESTORE) ---
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
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()} if db else {}

def carregar_relatorios():
    db = inicializar_db()
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()] if db else []

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria}, merge=True)

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db: 
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório removido!")

def editar_nome_membro(nome_antigo, nome_novo, categoria):
    db = inicializar_db()
    if db:
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

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()

    tabs_principal = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "⚙️ CONFIGURAÇÃO"])

    with tabs_principal[0]:
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        entregaram = df_ok['nome_oficial'].unique() if not df_ok.empty else []
        
        sub_tabs_rel = st.tabs(["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "⏳ PENDÊNCIAS"])
        categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
        
        for i, cat in enumerate(categorias_lista):
            with sub_tabs_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()
                if df_cat.empty: st.info(f"Sem relatórios de {cat}.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{len(df_cat)}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-container"><div class="metric-label">Horas</div><div class="metric-value">{int(df_cat["horas"].sum())}h</div></div>', unsafe_allow_html=True)
                    m3.markdown(f'<div class="metric-container"><div class="metric-label">Estudos</div><div class="metric-value">{int(df_cat["estudos_biblicos"].sum())}</div></div>', unsafe_allow_html=True)
                    
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
                        if c2.button("Inativo", key=f"inat_{p_nome}"): atualizar_membro(p_nome, "INATIVO"); st.rerun()
                        if c3.button("📥 Baixa", key=f"baix_{p_nome}"):
                            inicializar_db().collection("relatorios_parque_alianca").add({"nome": p_nome, "mes_referencia": mes_sel, "horas": 0, "estudos_biblicos": 0, "observacoes": "Baixa manual"})
                            st.rerun()

    with tabs_principal[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Triagem limpa!")
        else:
            nomes_ex = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.write(f"**Digitado:** {row['nome']} | **Horas:** {row['horas']}")
                    sug = normalizar_nome_no_banco(row['nome'], nomes_ex)
                    idx_s = nomes_ex.index(sug) + 1 if sug else 0
                    c1, c2 = st.columns(2)
                    n_f = c1.text_input("Novo Nome?", value=row['nome'], key=f"tr_n_{row['id']}")
                    n_s = c2.selectbox("Corresponder a:", ["-- Selecionar --"] + nomes_ex, index=idx_s, key=f"tr_s_{row['id']}")
                    if st.button("✅ CONFIRMAR", key=f"tr_v_{row['id']}", use_container_width=True):
                        validar_e_gravar_novo_membro(row['id'], n_s if n_s != "-- Selecionar --" else n_f, "PUBLICADOR")
                        st.rerun()

    with tabs_principal[2]:
        sub_cfg = st.tabs(["📂 REGISTROS TOTAIS (S-21)", "👤 GESTÃO DE MEMBROS"])
        
        with sub_cfg[0]:
            st.subheader("Gerador de Cartão S-21 Oficial")
            modelo_upload = st.file_uploader("1. Faça upload do modelo S21.pdf original", type=["pdf"])
            
            if modelo_upload and not df_ok.empty:
                st.success("Modelo pronto para preenchimento!")
                
                zip_off = io.BytesIO()
                with zipfile.ZipFile(zip_off, "a", zipfile.ZIP_DEFLATED, False) as zf:
                    for _, r in df_ok.iterrows():
                        pdf_data = preencher_s21_original(modelo_upload, r, mes_sel)
                        if pdf_data:
                            zf.writestr(f"S21_{r['nome_oficial']}.pdf", pdf_data)
                
                st.download_button("📥 BAIXAR TODOS EM ZIP", zip_off.getvalue(), f"S21_{mes_sel}.zip", "application/zip", use_container_width=True)
                
                st.write("---")
                for _, r in df_ok.sort_values('nome_oficial').iterrows():
                    ca, cb = st.columns([4, 1])
                    ca.write(f"📄 {r['nome_oficial']}")
                    pdf_ind = preencher_s21_original(modelo_upload, r, mes_sel)
                    if pdf_ind:
                        cb.download_button("Baixar S-21", pdf_ind, f"S21_{r['nome_oficial']}.pdf", key=f"pdf_ind_{r['id']}")
            else:
                st.info("Suba o arquivo S21.pdf para gerar os documentos automáticos.")

        with sub_cfg[1]:
            st.subheader("Novo Membro")
            c1, c2, c3 = st.columns([2, 1, 1])
            new_n = c1.text_input("Nome")
            new_c = c2.selectbox("Cat", categorias_lista)
            if c3.button("Cadastrar"): 
                if new_n: atualizar_membro(new_n, new_c); st.rerun()
            
            st.write("---")
            for m_nome in sorted(membros_db.keys()):
                with st.expander(f"👤 {m_nome}"):
                    e_n = st.text_input("Nome", value=m_nome, key=f"e_n_{m_nome}")
                    e_c = st.selectbox("Cat", categorias_lista + ["INATIVO"], 
                                      index=(categorias_lista + ["INATIVO"]).index(membros_db[m_nome].get('categoria', 'PUBLICADOR')), 
                                      key=f"e_c_{m_nome}")
                    if st.button("Salvar", key=f"s_{m_nome}"):
                        if e_n != m_nome: editar_nome_membro(m_nome, e_n, e_c)
                        else: atualizar_membro(e_n, e_c)
                        st.rerun()

    st.caption("Admin Parque Aliança 2026 | S-21-T 11/23")

if __name__ == "__main__":
    main()
