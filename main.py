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
from reportlab.pdfgen import canvas  # FALTAVA ESTE
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from pypdf import PdfReader, PdfWriter # FALTAVA ESTE (ou use PyPDF2 se preferir)
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
    .stButton>button.del-btn {
        padding: 0px 5px; height: 25px; width: 25px; min-width: 25px; font-size: 12px;
        border-radius: 5px; background-color: #fee2e2; color: #ef4444; border: 1px solid #fecaca; float: right;
    }
    </style>
""", unsafe_allow_html=True)
# --- FUNÇÃO DE NORMALIZAÇÃO ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()
# --- NOVA FUNÇÃO PARA GERAR PDF (VERSÃO OVERLAY COM FIDELIDADE 100%) ---
# Esta função requer o arquivo 'template_s21.pdf' (modelo em branco) na mesma pasta.
def gerar_pdf_registro_s21(row, mes_sel):
    # --- PASSO 1: CRIAR A CAMADA DE DADOS (TRANSPARENTE) ---
    packet = io.BytesIO()
    # Usamos o canvas para desenhar nas coordenadas exatas do papel
    can = canvas.Canvas(packet, pagesize=A4)
    
    # --- CONFIGURAÇÃO DE FONTES ---
    can.setFont("Helvetica", 10) # Fonte normal para os dados
    
    # --- CABEÇALHO (Ajuste X, Y conforme necessário para alinhar com o papel) ---
    # Nome (X=75, Y=755)
    can.drawString(75, 755, str(row['nome_oficial'])) 
    
    # Exemplo de como marcar Gênero (se você tiver esse dado no banco)
    # can.drawString(652, 715, "X") # Masculino (X aproximado)
    
    # --- TABELA DE RELATÓRIOS (Coordenadas para as linhas) ---
    # Y inicial para o mês de Setembro (primeira linha)
    y_pos_setembro = 635 
    espacamento_linhas = 18.5 # Distância exata entre uma linha e outra no S-21
    
    # Lista padrão de meses do ano de serviço
    meses_lista = ["SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO", "JANEIRO", 
                   "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO"]
    
    try:
        # Pega apenas o nome do mês (ex: "ABRIL" de "ABRIL 2026")
        nome_mes_puro = mes_sel.split(" ")[0].upper()
        
        if nome_mes_puro in meses_lista:
            # Descobre qual é a linha (índice)
            indice_mes = meses_lista.index(nome_mes_puro)
            # Calcula o Y exato para aquela linha
            y_atual = y_pos_setembro - (indice_mes * espacamento_linhas)
            
            # --- DESENHAR OS DADOS NA LINHA ---
            # X de participação (Coluna "Participou no ministério")
            if row['horas'] > 0 or row.get('estudos_biblicos', 0) > 0:
                can.drawString(205, y_atual, "X") # Centralizado na coluna
                
            # Estudos Bíblicos (Coluna "Estudos bíblicos")
            can.drawString(325, y_atual, str(int(row['estudos_biblicos'])))
            
            # Horas (Coluna "Horas")
            # Se for publicador, as horas vão na coluna de Pioneiro Auxiliar? 
            # O S-21 oficial tem regras. Vou colocar na coluna de horas geral:
            can.drawString(570, y_atual, str(int(row['horas'])))
            
            # Observações (Coluna "Observações")
            if row.get('observacoes'):
                can.setFont("Helvetica", 8) # Fonte menor para caber
                # Limita a 40 caracteres para não vazar a célula
                obs_texto = str(row['observacoes'])[:40]
                can.drawString(650, y_atual, obs_texto)
                
    except Exception as e:
        # Se der erro no processamento do mês, não desenha nada na tabela
        print(f"Erro ao processar linha do mês no PDF: {e}")
        pass

    can.save()
    packet.seek(0)

    # --- PASSO 2: FUNDIR COM O PDF BASE (O MODELO EM BRANCO) ---
    try:
        # Carrega o PDF original que você fez upload
        arquivo_base = PdfReader(open("template_s21.pdf", "rb"))
        camada_dados = PdfReader(packet)
        
        output = PdfWriter()
        
        # Pega a primeira página do original
        pagina_principal = arquivo_base.pages[0]
        # Sobrepõe a camada de dados transparente
        pagina_principal.merge_page(camada_dados.pages[0])
        
        output.add_page(pagina_principal)
        
        # Retorna o PDF final mesclado
        buffer_final = io.BytesIO()
        output.write(buffer_final)
        return buffer_final.getvalue()
        
    except FileNotFoundError:
        # Caso o arquivo original não seja encontrado no servidor
        st.error("Erro Crítico: O arquivo 'template_s21.pdf' (modelo em branco) não foi encontrado na raiz do projeto. O PDF gerado estará em branco.")
        # Retorna o PDF base vazio para não quebrar o download, mas avisa o usuário
        output_vazio = PdfWriter()
        output_vazio.add_blank_page(width=A4[0], height=A4[1])
        buffer_vazio = io.BytesIO()
        output_vazio.write(buffer_vazio)
        return buffer_vazio.getvalue()
# --- FUNÇÕES DE CONEXÃO E BANCO ---
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
    if maior_score >= 0.80: return melhor_match
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
        df['mes_referencia'] = df['mes_referencia'].str.upper()
    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["ABRIL 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
    tabs = st.tabs(["📋 RELATÓRIOS RECEBIDOS", "⚠️ TRIAGEM DE NOMES", "⏳ PENDÊNCIAS", "📂 REGISTROS TOTAIS", "⚙️ CONFIGURAÇÃO"])
    with tabs[0]:
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
                        m1.markdown(f'<div class="metric-container"><div class="metric-label">Envios</div><div class="metric-value">{len(df_cat)}</div></div>', unsafe_allow_html=True)
                        m2.markdown(f'<div class="metric-container"><div class="metric-label">Total Horas</div><div class="metric-value">{int(df_cat["horas"].sum())}h</div></div>', unsafe_allow_html=True)
                        m3.markdown(f'<div class="metric-container"><div class="metric-label">Total Estudos</div><div class="metric-value">{int(df_cat["estudos_biblicos"].sum())}</div></div>', unsafe_allow_html=True)
                        cols = st.columns(4)
                        for idx, (_, r) in enumerate(df_cat.iterrows()):
                            with cols[idx % 4]:
                                st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div><div style="font-size:0.8rem;">⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])} est.</div></div>', unsafe_allow_html=True)
                                if st.button(f"🗑️ Deletar", key=f"del_ok_{r['id']}", use_container_width=True):
                                    deletar_relatorio(r['id']); st.rerun()
    with tabs[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("✨ Triagem limpa!")
        else:
            nomes_existentes = sorted(list(membros_db.keys()))
            for _, row in df_triagem.iterrows():
                with st.container():
                    st.markdown(f'<div class="triagem-box"><b>Digitado:</b> {row["nome"]} | <b>Horas:</b> {row["horas"]}</div>', unsafe_allow_html=True)
                    sugestao = normalizar_nome_no_banco(row['nome'], nomes_existentes)
                    idx_pre_selecao = nomes_existentes.index(sugestao) + 1 if sugestao and sugestao in nomes_existentes else 0
                    c1, c2 = st.columns(2)
                    n_f = c1.text_input("Ajustar Nome:", value=row['nome'], key=f"tri_n_{row['id']}")
                    n_s = c2.selectbox("Fundir com:", ["-- Selecionar --"] + nomes_existentes, index=idx_pre_selecao, key=f"fundir_{row['id']}")
                    cat_n = st.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], key=f"tri_c_{row['id']}")
                    b1, b2 = st.columns(2)
                    if b1.button("✅ VALIDAR", key=f"btn_v_{row['id']}", use_container_width=True):
                        nome_final = n_s if n_s != "-- Selecionar --" else n_f
                        validar_e_gravar_novo_membro(row['id'], nome_final, cat_n)
                        st.rerun()
                    if b2.button("🗑️ RECUSAR", key=f"btn_r_{row['id']}", use_container_width=True):
                        deletar_relatorio(row['id']); st.rerun()
    with tabs[2]:
        entregaram = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]['nome_oficial'].unique() if not df_mes.empty else []
        cats_pend = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]
        p_tabs = st.tabs(cats_pend)
        for i, cat in enumerate(cats_pend):
            with p_tabs[i]:
                membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
                pendentes = sorted([n for n in membros_cat if n not in entregaram])
                for p_nome in pendentes:
                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    c1.write(f"⚠️ {p_nome}")
                    nova_cat = c2.selectbox("Mover", cats_pend + ["INATIVO"], index=cats_pend.index(cat), key=f"p_cat_{p_nome}")
                    if c3.button("Atualizar", key=f"btn_p_{p_nome}"):
                        atualizar_membro(p_nome, nova_cat); st.rerun()
                    if c4.button("📥 RECEBIDO", key=f"baixa_{p_nome}"):
                        db = inicializar_db()
                        db.collection("relatorios_parque_alianca").add({"nome": p_nome, "mes_referencia": mes_sel, "horas": 0, "estudos_biblicos": 0, "observacoes": "Baixa manual"})
                        st.rerun()
    with tabs[3]:
        st.subheader(f"Exportação - {mes_sel}")
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
        if df_ok.empty: st.info("Sem dados identificados.")
        else:
            df_ok = df_ok.sort_values('nome_oficial')
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for _, r in df_ok.iterrows():
                    zf.writestr(f"Registro_{r['nome_oficial']}.pdf", gerar_pdf_registro_s21(r, mes_sel))
            st.download_button("📥 Baixar Todos (ZIP)", zip_buffer.getvalue(), f"Registros_{mes_sel}.zip", "application/zip")
            st.write("---")
            for _, r in df_ok.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"👤 **{r['nome_oficial']}**")
                c2.download_button("PDF", gerar_pdf_registro_s21(r, mes_sel), f"S21_{r['nome_oficial']}.pdf", key=f"pdf_{r['id']}")
    with tabs[4]:
        st.subheader("👤 Novo Membro")
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            new_n = col1.text_input("Nome:", placeholder="Nome Completo")
            new_c = col2.selectbox("Cat:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"])
            if col3.button("Cadastrar", use_container_width=True):
                if new_n: atualizar_membro(new_n, new_c); st.rerun()
        st.write("---")
        for m_nome in sorted(membros_db.keys()):
            with st.expander(f"👤 {m_nome}"):
                ca, cb = st.columns(2)
                e_n = ca.text_input("Editar Nome:", value=m_nome, key=f"cfg_n_{m_nome}")
                idx_cat = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"].index(membros_db[m_nome].get('categoria', 'PUBLICADOR'))
                e_c = ca.selectbox("Categoria:", ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "INATIVO"], index=idx_cat, key=f"cfg_c_{m_nome}")
                if ca.button("Salvar", key=f"cfg_s_{m_nome}"):
                    if e_n != m_nome: editar_nome_membro(m_nome, e_n, e_c)
                    else: atualizar_membro(e_n, e_c)
                    st.rerun()
                if cb.button(f"Excluir", key=f"cfg_d_{m_nome}"):
                    inicializar_db().collection("membros_v2").document(m_nome).delete(); st.rerun()
if __name__ == "__main__":
    main()
