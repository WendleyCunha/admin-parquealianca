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

# --- ESTILIZAÇÃO CUSTOMIZADA ---
st.markdown("""
    <style>
    .card { background-color: #ffffff; padding: 15px; border-radius: 10px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #002366; }
    .card-header { font-weight: bold; font-size: 1rem; color: #1e293b; }
    .pendencia-row { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid #eee; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES UTILITÁRIAS ---
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

# AJUSTE 2: Validação automática inteligente (Fuzzy Match)
def validar_nome_automatico(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 3: return None
    
    melhor_match, maior_score = None, 0
    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        
        # Se for exatamente igual após normalizar, retorna na hora
        if entrada_norm == oficial_norm: return nome_oficial
        
        # Caso contrário, calcula similaridade (considera partes do nome)
        score = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score > maior_score: maior_score, melhor_match = score, nome_oficial
        
    # Tolerância de 75% para aceitar erro de digitação/sobrenome faltando
    return melhor_match if maior_score >= 0.75 else None

# --- MOTOR DE PDF (S-21 OFICIAL) ---
def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado.")
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
            if "AUXILIAR" in str(categoria_label).upper():
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
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()} if db else {}

def carregar_relatorios():
    db = inicializar_db()
    return [{"id": doc.id, **doc.to_dict()} for doc in db.collection("relatorios_parque_alianca").stream()] if db else []

def atualizar_membro(nome, categoria):
    db = inicializar_db()
    if db: db.collection("membros_v2").document(nome).set({"categoria": categoria, "nome_oficial": nome}, merge=True)

def salvar_relatorio_manual(nome, mes, horas, estudos):
    db = inicializar_db()
    if db:
        db.collection("relatorios_parque_alianca").add({
            "nome": nome, "mes_referencia": mes, "horas": int(horas),
            "estudos_biblicos": int(estudos), "observacoes": "Lançamento Manual"
        })
        st.toast(f"Relatório de {nome} salvo!")

# --- APP ---
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
            # AJUSTE 2: Aplicação da busca automática
            nome_oficial = validar_nome_automatico(row['nome'], membros_db.keys())
            if nome_oficial:
                cat = membros_db[nome_oficial].get('categoria', 'PUBLICADOR')
                return pd.Series([nome_oficial, cat, "IDENTIFICADO"])
            return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])
            
        df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
        df['mes_referencia'] = df['mes_referencia'].str.upper()

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else ["MAIO 2026"]
    mes_sel = st.sidebar.selectbox("📅 Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
    
    tabs = st.tabs(["📋 RELATÓRIOS", "⚠️ TRIAGEM", "📈 CONSOLIDADO", "⚙️ CONFIG"])

    # --- ABA 0: RELATÓRIOS & PENDÊNCIAS ---
    with tabs[0]:
        df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"]
        entregaram = df_ok['nome_oficial'].unique()
        
        sub_rel = st.tabs(["PUBLICADORES", "P. AUXILIARES", "P. REGULARES", "⏳ PENDÊNCIAS"])
        
        for i, cat in enumerate(categorias_lista):
            with sub_rel[i]:
                df_cat = df_ok[df_ok['cat_oficial'] == cat]
                # AJUSTE 3: Ordem (Horas, Estudos e depois Envios)
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Horas", f"{int(df_cat['horas'].sum())}h")
                m2.metric("Estudos Bíblicos", int(df_cat['estudos_biblicos'].sum()))
                m3.metric("Total de Relatórios", len(df_cat))
                
                cols = st.columns(4)
                for idx, (_, r) in enumerate(df_cat.sort_values('nome_oficial').iterrows()):
                    with cols[idx % 4]:
                        st.markdown(f'<div class="card"><div class="card-header">{r["nome_oficial"]}</div>⏱️ {int(r["horas"])}h | 📚 {int(r["estudos_biblicos"])}</div>', unsafe_allow_html=True)

        with sub_rel[3]:
            # AJUSTE 1: Botão de Entrega Manual nas pendências
            st.warning(f"Pendentes em {mes_sel}")
            for cat in categorias_lista:
                membros_cat = [n for n, d in membros_db.items() if d.get('categoria') == cat]
                pendentes = sorted([n for n in membros_cat if n not in entregaram])
                if pendentes:
                    with st.expander(f"{cat} ({len(pendentes)})"):
                        for p in pendentes:
                            c1, c2 = st.columns([3, 1])
                            c1.write(f"• {p}")
                            if c2.button("Entregar Manual", key=f"btn_p_{p}"):
                                st.session_state[f"show_form_{p}"] = True
                            
                            if st.session_state.get(f"show_form_{p}"):
                                with st.form(f"form_{p}"):
                                    h_man = st.number_input("Horas", min_value=0, key=f"h_{p}")
                                    e_man = st.number_input("Estudos", min_value=0, key=f"e_{p}")
                                    if st.form_submit_button("Salvar Relatório"):
                                        salvar_relatorio_manual(p, mes_sel, h_man, e_man)
                                        st.rerun()

    # --- ABA 1: TRIAGEM ---
    with tabs[1]:
        df_triagem = df_mes[df_mes['status_validacao'] == "TRIAGEM"] if not df_mes.empty else pd.DataFrame()
        if df_triagem.empty: st.success("A validação automática resolveu tudo! ✅")
        else:
            for _, row in df_triagem.iterrows():
                with st.container(border=True):
                    st.write(f"Digitado: **{row['nome']}** | Horas: {row['horas']}")
                    nomes_db = sorted(list(membros_db.keys()))
                    vincular = st.selectbox("Vincular a:", ["-- Novo Membro --"] + nomes_db, key=f"v_{row['id']}")
                    if st.button("Confirmar Vínculo", key=f"b_{row['id']}"):
                        nome_final = row['nome'] if vincular == "-- Novo Membro --" else vincular
                        inicializar_db().collection("relatorios_parque_alianca").document(row['id']).update({"nome": nome_final})
                        st.rerun()

    # --- ABA 2: CONSOLIDADO ---
    with tabs[2]:
        publicador = st.selectbox("Publicador para Histórico S-21", sorted(list(membros_db.keys())))
        if publicador:
            df_hist = df[(df['nome_oficial'] == publicador) & (df['status_validacao'] == "IDENTIFICADO")].sort_values('mes_referencia')
            if not df_hist.empty:
                st.table(df_hist[['mes_referencia', 'horas', 'estudos_biblicos']])
                pdf = gerar_pdf_padrao_s21(publicador, membros_db[publicador].get('categoria'), df_hist)
                st.download_button("📥 Baixar Cartão S-21", pdf, f"S21_{publicador}.pdf")

    # --- ABA 3: CONFIG ---
    with tabs[3]:
        with st.form("novo_membro"):
            nm = st.text_input("Nome do Novo Membro")
            ct = st.selectbox("Categoria", categorias_lista)
            if st.form_submit_button("Adicionar"):
                atualizar_membro(nm, ct); st.rerun()

    st.caption("v2.5.0 | Parque Aliança | Gestão S-21")

if __name__ == "__main__":
    main()
