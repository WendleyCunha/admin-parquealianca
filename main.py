import streamlit as st
import pandas as pd
import json
import io
import zipfile
import unicodedata
import os
from datetime import datetime
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

# --- ESTILIZAÇÃO CUSTOMIZADA ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .status-tag { font-size: 0.7rem; padding: 2px 5px; border-radius: 4px; background: #e2e8f0; margin-right: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def obter_mes_referencia_atual():
    hoje = datetime.now()
    # Se passou do dia 20, o foco é o mês atual. Se não, ainda estamos fechando o anterior.
    meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    indice = hoje.month - 1
    return f"{meses[indice]} {hoje.year}"

# --- MOTOR DE PDF (S-21) ---
def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        return None

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica-Bold", 10)
    can.drawString(24*mm, 258*mm, str(nome_cabecalho).upper())
    
    y_map = {
        "SETEMBRO": 204.5, "OUTUBRO": 196.5, "NOVEMBRO": 188.5, "DEZEMBRO": 180.5,
        "JANEIRO": 172.5, "FEVEREIRO": 164.5, "MARÇO": 156.5, "ABRIL": 148.5,
        "MAIO": 140.5, "JUNHO": 132.5, "JULHO": 124.5, "AGOSTO": 116.5
    }
    
    for _, row in dados_rows.iterrows():
        mes_key = str(row['mes_referencia']).split()[0].upper()
        if mes_key in y_map:
            y_pos = y_map[mes_key] * mm
            if int(row.get('horas', 0)) > 0 or int(row.get('estudos_biblicos', 0)) > 0:
                can.drawCentredString(53.5*mm, y_pos, "X")
            can.drawCentredString(80.5*mm, y_pos, str(int(row.get('estudos_biblicos', 0))))
            if "PIONEIRO" in str(categoria_label).upper():
                can.drawCentredString(97.5*mm, y_pos, "X")
            can.drawCentredString(116.5*mm, y_pos, str(int(row.get('horas', 0))))

    can.save()
    packet.seek(0)
    reader_original = PdfReader(open(path_original, "rb"))
    writer = PdfWriter()
    pagina_base = reader_original.pages[0]
    pagina_base.merge_page(PdfReader(packet).pages[0])
    writer.add_page(pagina_base)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()

# --- BANCO DE DADOS ---
def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="wendleydesenvolvimento")
        except: return None
    return st.session_state.db

def carregar_membros():
    db = inicializar_db()
    if not db: return {}
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}

def carregar_relatorios():
    db = inicializar_db()
    if not db: return []
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()]

def salvar_membro(dados):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(dados['nome_oficial']).set(dados, merge=True)

def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if db: 
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
        st.toast("Relatório excluído com sucesso!")
        st.rerun()

def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
    return melhor_match if maior_score >= 0.85 else None

# --- APP ---
def main():
    st.title("📊 Gestão Parque Aliança")
    membros_db = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    
    categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR", "PIONEIRO ESPECIAL", "MISSIONÁRIO"]
    designacoes = ["Ancião", "Servo ministerial", "Outras ovelhas", "Ungido"]

    df = pd.DataFrame(relatorios_brutos) if relatorios_brutos else pd.DataFrame()
    if not df.empty:
        df['horas'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
        df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
        
        def validar_envio(row):
            nome_oficial = normalizar_nome_no_banco(row['nome'], membros_db.keys())
            if nome_oficial:
                m = membros_db[nome_oficial]
                return pd.Series([nome_oficial, m.get('categoria', 'PUBLICADOR'), "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    mes_default = obter_mes_referencia_atual()
    meses_lista = sorted(df['mes_referencia'].unique()) if not df.empty else [mes_default]
    if mes_default not in meses_lista: meses_lista.append(mes_default)
    
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_lista, index=len(meses_lista)-1)
    
    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "⚙️ CONFIGURAÇÃO"])

    # --- ABA 0: RELATÓRIOS ---
    with tabs[0]:
        df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        
        # Filtros de Categoria de Membro
        filtro_cat = st.multiselect("Filtrar por Categoria de Cadastro:", options=categorias_lista)
        
        df_display = df_ok.copy()
        if filtro_cat:
            df_display = df_display[df_display['cat_oficial'].isin(filtro_cat)]

        st.subheader(f"Envios de {mes_sel}")
        if df_display.empty: st.info("Nenhum relatório para os filtros selecionados.")
        else:
            cols = st.columns(4)
            for idx, (_, r) in enumerate(df_display.sort_values('nome_oficial').iterrows()):
                with cols[idx % 4]:
                    tags = f"<span class='status-tag'>{r['cat_oficial']}</span>"
                    st.markdown(f'''<div class="card">
                        <div class="card-header">{r["nome_oficial"]}</div>
                        {tags}<br>
                        ⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}
                    </div>''', unsafe_allow_html=True)

    # --- ABA 1: TRIAGEM ---
    with tabs[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("Tudo limpo na triagem!")
        else:
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3,2,1])
                    c1.write(f"**Digitado:** {row['nome']} ({row['horas']}h)")
                    vincular = c2.selectbox("Vincular a:", ["-- Novo --"] + sorted(list(membros_db.keys())), key=f"t_v_{row['id']}")
                    if c3.button("🗑️", key=f"del_t_{row['id']}"): deletar_relatorio(row['id'])
                    
                    if st.button("Confirmar Vinculação", key=f"conf_t_{row['id']}"):
                        nome_final = row['nome'] if vincular == "-- Novo --" else vincular
                        inicializar_db().collection("relatorios_parque_alianca").document(row['id']).update({"nome": nome_final})
                        st.rerun()

    # --- ABA 2: CONSOLIDADO ---
    with tabs[2]:
        publicador = st.selectbox("Histórico do Publicador", sorted(list(membros_db.keys())))
        if publicador:
            df_h = df[df['nome_oficial'] == publicador]
            st.dataframe(df_h[['mes_referencia', 'horas', 'estudos_biblicos']])
            pdf = gerar_pdf_padrao_s21(publicador, membros_db[publicador].get('categoria'), df_h)
            if pdf: st.download_button("📥 Baixar S-21", pdf, f"S21_{publicador}.pdf")

    # --- ABA 3: CONFIGURAÇÃO ---
    with tabs[3]:
        sub_cfg = st.tabs(["➕ LANÇAMENTO MANUAL", "👥 GESTÃO DE MEMBROS", "✏️ EDITAR/DELETAR"])
        
        with sub_cfg[0]:
            st.write("### Dar baixa manual (Pessoas que não usaram o link)")
            with st.form("baixa_manual"):
                m_nome = st.selectbox("Membro", sorted(list(membros_db.keys())))
                m_mes = st.selectbox("Mês", meses_lista, index=len(meses_lista)-1)
                col1, col2 = st.columns(2)
                m_h = col1.number_input("Horas", min_value=0)
                m_e = col2.number_input("Estudos", min_value=0)
                if st.form_submit_button("Registrar Relatório"):
                    db = inicializar_db()
                    db.collection("relatorios_parque_alianca").add({
                        "nome": m_nome, "mes_referencia": m_mes, "horas": m_h, "estudos_biblicos": m_e, "timestamp": datetime.now()
                    })
                    st.success("Lançado!")
                    st.rerun()

        with sub_cfg[1]:
            st.write("### Cadastro de Membros")
            with st.form("form_membro"):
                c1, c2 = st.columns(2)
                nome_m = c1.text_input("Nome Completo")
                cat_m = c2.selectbox("Categoria Principal", categorias_lista)
                
                c3, c4, c5 = st.columns(3)
                dt_nasc = c3.date_input("Data de Nascimento", value=None)
                dt_bat = c4.date_input("Data de Batismo", value=None)
                sexo = c5.radio("Gênero", ["Masculino", "Feminino"])
                
                designa = st.multiselect("Designações / Status", designacoes)
                
                if st.form_submit_button("Salvar Membro"):
                    dados = {
                        "nome_oficial": nome_m,
                        "categoria": cat_m,
                        "nascimento": str(dt_nasc),
                        "batismo": str(dt_bat),
                        "sexo": sexo,
                        "designacoes": designa
                    }
                    salvar_membro(dados)
                    st.rerun()

        with sub_cfg[2]:
            st.write(f"### Editar Envios de {mes_sel}")
            for _, r in df_ok.iterrows():
                with st.expander(f"{r['nome_oficial']}"):
                    ce1, ce2, ce3 = st.columns([2,1,1])
                    n_h = ce1.number_input("Horas", value=int(r['horas']), key=f"ed_h_{r['id']}")
                    if ce2.button("Atualizar", key=f"up_b_{r['id']}"):
                        inicializar_db().collection("relatorios_parque_alianca").document(r['id']).update({"horas": n_h})
                        st.rerun()
                    if ce3.button("Excluir Relatório", key=f"del_b_{r['id']}", type="primary"):
                        deletar_relatorio(r['id'])

    st.caption(f"v2.5.0 | Parque Aliança | Ciclo: Dia 20")

if __name__ == "__main__":
    main()
