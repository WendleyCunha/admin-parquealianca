import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd
from datetime import datetime
import io

# =========================================================
# 1. CONEXÃO E CONFIGURAÇÃO (ESTILO PREMIUM)
# =========================================================

st.set_page_config(page_title="King Star - Passagens Pro", layout="wide", page_icon="🚌")

# Custom CSS para visual moderno
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        height: 45px; background-color: #f0f2f6; border-radius: 10px 10px 0px 0px; padding: 0px 20px; 
    }
    .stTabs [aria-selected="true"] { background-color: #003399 !important; color: white !important; }
    div[data-testid="metric-container"] { 
        background-color: white; border: 1px solid #e6e9ef; padding: 15px; border-radius: 12px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); 
    }
    .main-title { color: #003399; font-weight: 800; letter-spacing: -1px; }
    </style>
    """, unsafe_allow_html=True)

def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(credentials=creds, project="bancowendley")
        except Exception as e:
            st.error(f"Erro no Firebase: {e}")
            return None
    return st.session_state.db

# =========================================================
# 2. LÓGICA DE DADOS (MANTIDA INTACTA)
# =========================================================

def atualizar_cadastro_central(dados_pax):
    db = inicializar_db()
    if db:
        pax_id = dados_pax['nome'].lower().replace(" ", "")
        db.collection("cadastro_geral").document(pax_id).set({
            "nome": dados_pax['nome'],
            "rg": dados_pax.get('rg', ""),
            "cpf": dados_pax.get('cpf', ""),
            "grupo": dados_pax.get('grupo', "Geral"),
            "ultima_atualizacao": datetime.now()
        }, merge=True)

def buscar_pessoa_central(nome_pesquisa):
    db = inicializar_db()
    if not db or not nome_pesquisa: return None
    docs = db.collection("cadastro_geral").stream()
    nome_busca = nome_pesquisa.lower().strip()
    for doc in docs:
        dados = doc.to_dict()
        if nome_busca in dados.get('nome', '').lower():
            return dados
    return None

def criar_evento(nome, datas, valor_passagem):
    db = inicializar_db()
    if db:
        id_evento = f"{nome.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
        db.collection("eventos").document(id_evento).set({
            "nome": nome, "datas": datas, "valor": valor_passagem,
            "status": "ativo", "criado_em": datetime.now(),
            "frotas": {dia: 1 for dia in datas}
        })
        return id_evento

def adicionar_novo_onibus(id_evento, dia):
    db = inicializar_db()
    if db:
        doc_ref = db.collection("eventos").document(id_evento)
        evento = doc_ref.get().to_dict()
        frotas = evento.get('frotas', {d: 1 for d in evento['datas']})
        frotas[dia] = frotas.get(dia, 1) + 1
        doc_ref.update({"frotas": frotas})

def salvar_passageiro(id_evento, dados_pax):
    db = inicializar_db()
    if db:
        sufixo = dados_pax['rg'] if dados_pax.get('rg') else "reserva"
        pax_id = f"{dados_pax['nome']}_{sufixo}".lower().replace(" ", "")
        if 'embarcou' not in dados_pax:
            dados_pax['embarcou'] = False
        db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).set(dados_pax)
        atualizar_cadastro_central(dados_pax)

def atualizar_embarque(id_evento, pax, status):
    db = inicializar_db()
    if db:
        sufixo = pax['rg'] if pax.get('rg') else "reserva"
        pax_id = f"{pax['nome']}_{sufixo}".lower().replace(" ", "")
        db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).update({"embarcou": status})

def deletar_passageiro(id_evento, nome, rg):
    db = inicializar_db()
    if db:
        sufixo = rg if rg else "reserva"
        pax_id = f"{nome}_{sufixo}".lower().replace(" ", "")
        db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).delete()

def carregar_passageiros(id_evento):
    db = inicializar_db()
    paxs = db.collection("eventos").document(id_evento).collection("passageiros").stream()
    return [p.to_dict() for p in paxs]

def carregar_eventos():
    db = inicializar_db()
    if not db: return {}
    docs = db.collection("eventos").where("status", "==", "ativo").stream()
    return {doc.id: doc.to_dict() for doc in docs}

# =========================================================
# 3. INTERFACE VISUAL (MELHORIA PREMIUM)
# =========================================================

@st.dialog("Gerenciar Passageiro")
def gerenciar_pax_dialog(pax, id_evento, evento_atual):
    st.subheader(f"👤 {pax['nome']}")
    
    # Cálculos Financeiros Dinâmicos
    total_devido = pax.get('valor_total', len(pax.get('dias_onibus', [])) * evento_atual['valor'])
    pago_atualmente = pax.get('valor_pago', 0.0)
    saldo_devedor = total_devido - pago_atualmente

    col_f1, col_f2 = st.columns(2)
    col_f1.metric("Total da Passagem", f"R$ {total_devido:.2f}")
    col_f2.metric("Saldo Pendente", f"R$ {saldo_devedor:.2f}", delta_color="inverse")

    with st.form("edit_pax_final"):
        nome = st.text_input("Nome", value=pax['nome'])
        c1, c2 = st.columns(2)
        rg = c1.text_input("RG", value=pax.get('rg', ""))
        cpf = c2.text_input("CPF", value=pax.get('cpf', ""))
        
        lista_grupos = ["Rosas", "Engenho", "Cohab", "Geral"]
        grupo_atual = pax.get('grupo', 'Geral')
        idx_grupo = lista_grupos.index(grupo_atual) if grupo_atual in lista_grupos else 3
        grupo = st.selectbox("Grupo", lista_grupos, index=idx_grupo)
        
        st.divider()
        st.markdown("### 💰 Recebimentos / Troco")
        c_rec1, c_rec2, c_rec3 = st.columns(3)
        valor_recebido = c_rec1.number_input("Valor Recebido Agora", min_value=0.0, value=0.0, step=5.0)
        valor_entregue = c_rec2.number_input("Dinheiro (Troco)", min_value=0.0, value=0.0)
        if valor_entregue > valor_recebido:
            c_rec3.success(f"Troco: R$ {valor_entregue - valor_recebido:.2f}")

        st.divider()
        novas_viagens = []
        viagens_atuais = {v['dia']: v['bus'] for v in pax.get('dias_onibus', [])}
        
        for dia in evento_atual['datas']:
            col_d1, col_d2 = st.columns([1, 2])
            ativo = col_d1.checkbox(f"Viaja {dia}", value=dia in viagens_atuais, key=f"edit_chk_{dia}")
            if ativo:
                frotas_dia = evento_atual.get('frotas', {}).get(dia, 1)
                bus_default = viagens_atuais.get(dia, 1)
                bus_sel = col_d2.selectbox(f"Bus {dia}", range(1, frotas_dia + 1), index=min(bus_default-1, frotas_dia-1), key=f"edit_sel_{dia}")
                novas_viagens.append({"dia": dia, "bus": bus_sel})
        
        st.divider()
        novo_total_pago = pago_atualmente + valor_recebido
        pago = st.toggle("💰 Pagamento Total Quitado", value=pax.get('pago', False) or (novo_total_pago >= total_devido))
        embarque = st.toggle("🚩 Embarcou", value=pax.get('embarcou', False))
        
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary"):
            if nome != pax['nome'] or rg != pax.get('rg', ""):
                deletar_passageiro(id_evento, pax['nome'], pax.get('rg', ""))
            
            pax.update({
                "nome": nome, "rg": rg, "cpf": cpf, "grupo": grupo, 
                "dias_onibus": novas_viagens, "pago": pago, "embarcou": embarque,
                "valor_total": evento_atual['valor'] * len(novas_viagens),
                "valor_pago": novo_total_pago
            })
            salvar_passageiro(id_evento, pax)
            st.rerun()
        
        if col_btn2.form_submit_button("🗑️ Excluir Reserva", use_container_width=True):
            deletar_passageiro(id_evento, pax['nome'], pax.get('rg', ""))
            st.rerun()

def exibir_modulo_passagens():
    st.markdown("<h1 class='main-title'>🚌 Passagens VGP</h1>", unsafe_allow_html=True)
    eventos_ativos = carregar_eventos()
    
    # 1. NOVA ORDEM DAS ABAS COM ESTILO
    tab_reserva, tab_dash, tab_gestao, tab_chamada, tab_config = st.tabs([
        "📝 Reserva", "📊 Dashboard", "👥 Passageiros", "🚩 Chamada", "⚙️ Ajustes"
    ])

    if not eventos_ativos:
        with tab_config:
            st.subheader("Configurar Primeiro Evento")
            with st.form("criar_evento_inicial"):
                n_ev = st.text_input("Nome do Evento (Ex: Excursão Março)")
                v_ev = st.number_input("Valor da Passagem", min_value=0.0, value=50.0)
                d_ev = st.multiselect("Dias de Operação", ["Sexta", "Sábado", "Domingo"])
                if st.form_submit_button("🚀 Iniciar Evento"):
                    criar_evento(n_ev, d_ev, v_ev); st.rerun()
        st.info("Nenhum evento ativo. Vá em 'Ajustes' para criar um.")
        return

    # Sidebar para trocar de evento
    id_sel = st.sidebar.selectbox("Selecione o Evento", list(eventos_ativos.keys()), format_func=lambda x: eventos_ativos[x]['nome'])
    evento = eventos_ativos[id_sel]
    pax_lista = carregar_passageiros(id_sel)
    df = pd.DataFrame(pax_lista)
    
    # Normalização de dados
    if not df.empty:
        if 'grupo' not in df.columns: df['grupo'] = "Geral"
        df['grupo'] = df['grupo'].fillna("Geral")
        df['pago'] = df['pago'].fillna(False)

    CAPACIDADE = 46

    # --- ABA 1: NOVA RESERVA ---
    with tab_reserva:
        st.subheader("Lançar Nova Reserva")
        busca_nome = st.text_input("🔍 Buscar no histórico central (Nome)")
        mestre = buscar_pessoa_central(busca_nome) if busca_nome else None
        
        if mestre: st.success(f"Cadastro encontrado: {mestre['nome']}")

        with st.form("reserva_form_v2", clear_on_submit=True):
            nome_f = st.text_input("Nome Completo", value=mestre['nome'] if mestre else busca_nome)
            c_id1, c_id2 = st.columns(2)
            rg_f = c_id1.text_input("RG", value=mestre['rg'] if mestre else "")
            cpf_f = c_id2.text_input("CPF", value=mestre['cpf'] if mestre else "")
            
            grupo_f = st.selectbox("Grupo / Localização", ["Rosas", "Engenho", "Cohab", "Geral"])
            
            st.markdown("**Selecione os dias e ônibus:**")
            viagens = []
            for dia in evento['datas']:
                c1, c2 = st.columns([1, 2])
                if c1.checkbox(f"Viagem {dia}", key=f"f_res_{dia}"):
                    f_dia = evento.get('frotas', {}).get(dia, 1)
                    b_sel = c2.selectbox(f"Selecione o Bus {dia}", range(1, f_dia+1), key=f"f_bus_{dia}")
                    viagens.append({"dia": dia, "bus": b_sel})
            
            pago_f = st.toggle("Pagamento Confirmado?")
            if st.form_submit_button("✅ Finalizar Reserva", type="primary", use_container_width=True):
                if nome_f and viagens:
                    valor_total_devido = evento['valor'] * len(viagens)
                    salvar_passageiro(id_sel, {
                        "nome": nome_f, "rg": rg_f, "cpf": cpf_f, "grupo": grupo_f, 
                        "dias_onibus": viagens, "pago": pago_f, "embarcou": False,
                        "valor_total": valor_total_devido,
                        "valor_pago": valor_total_devido if pago_f else 0.0
                    })
                    st.success("Reserva Gravada!")
                    st.rerun()
                else:
                    st.error("Preencha o nome e escolha ao menos um dia.")

    # --- ABA 2: DASHBOARD (VISUAL PREMIUM) ---
    with tab_dash:
        if not df.empty:
            st.subheader(f"📊 Indicadores: {evento['nome']}")
            
            m1, m2, m3, m4 = st.columns(4)
            total_reservas = len(df)
            pagos = len(df[df['pago'] == True])
            financeiro = df['valor_pago'].sum() if 'valor_pago' in df.columns else (pagos * evento['valor'])
            
            m1.metric("Total Reservas", total_reservas)
            m2.metric("Pagos", f"{pagos}", f"{round((pagos/total_reservas)*100)}%")
            m3.metric("Pendentes", total_reservas - pagos)
            m4.metric("Arrecadado", f"R$ {financeiro:,.2f}")
            
            st.divider()
            
            # Controle de Ocupação por Ônibus
            st.markdown("### 🚌 Ocupação por Dia e Frota")
            cols_dia = st.columns(len(evento['datas']))
            
            for idx, dia in enumerate(evento['datas']):
                with cols_dia[idx]:
                    st.info(f"📅 **{dia}**")
                    num_onibus = evento.get('frotas', {}).get(dia, 1)
                    
                    for b in range(1, num_onibus + 1):
                        # Filtra passageiros desse dia e desse bus
                        qtd = 0
                        for _, p in df.iterrows():
                            for v in p.get('dias_onibus', []):
                                if v['dia'] == dia and v['bus'] == b:
                                    qtd += 1
                        
                        perc = round((qtd / CAPACIDADE) * 100) if CAPACIDADE > 0 else 0
                        
                        with st.container(border=True):
                            st.write(f"**Ônibus {b}**")
                            st.progress(min(perc/100, 1.0))
                            st.markdown(f"**{qtd}/{CAPACIDADE}** PAX ({perc}%)")
                            
                            if qtd >= CAPACIDADE:
                                st.warning("Lotação Máxima!")
                                if b == num_onibus:
                                    if st.button(f"➕ Add Ônibus {b+1}", key=f"add_{dia}_{b}", use_container_width=True):
                                        adicionar_novo_onibus(id_sel, dia)
                                        st.rerun()
        else:
            st.info("Aguardando dados para gerar o dashboard.")

    # --- ABA 3: GESTÃO DE PASSAGEIROS ---
    with tab_gestao:
        st.subheader("Controle de Pagamento e Edição")
        if not df.empty:
            col_pg, col_pn = st.columns(2)
            with col_pg:
                st.markdown("<h4 style='color:green;'>✅ Pagos</h4>", unsafe_allow_html=True)
                for _, r in df[df['pago']==True].sort_values('nome').iterrows():
                    if st.button(f"✏️ {r['nome']}", key=f"ed_pg_{r['nome']}", use_container_width=True):
                        gerenciar_pax_dialog(r.to_dict(), id_sel, evento)
            with col_pn:
                st.markdown("<h4 style='color:red;'>⚠️ Pendentes</h4>", unsafe_allow_html=True)
                for _, r in df[df['pago']==False].sort_values('nome').iterrows():
                    v_total = r.get('valor_total', len(r.get('dias_onibus', [])) * evento['valor'])
                    v_pago = r.get('valor_pago', 0.0)
                    v_falta = v_total - v_pago
                    
                    # Rótulo simplificado: Nome + Valor que falta com 2 casas decimais
                    label = f"👤 {r['nome']} | Falta: R$ {v_falta:,.2f}"
                    
                    if st.button(label, key=f"ed_pe_{r['nome']}", use_container_width=True):
                        gerenciar_pax_dialog(r.to_dict(), id_sel, evento)

    # --- ABA 4: LISTA DE EMBARQUE ---
    with tab_chamada:
        st.subheader("🚩 Chamada em Tempo Real")
        if not df.empty:
            grupos = sorted(df['grupo'].unique())
            for grp in grupos:
                with st.expander(f"📍 GRUPO: {grp.upper()}", expanded=True):
                    df_grp = df[df['grupo'] == grp]
                    c_faltam, c_ok = st.columns(2)
                    
                    with c_faltam:
                        st.caption("❌ AGUARDANDO EMBARQUE")
                        faltam = df_grp[(df_grp['pago'] == True) & (df_grp['embarcou'] == False)].sort_values('nome')
                        for _, p in faltam.iterrows():
                            col_n, col_b = st.columns([4, 1])
                            col_n.write(p['nome'])
                            if col_b.button("✅", key=f"emb_{grp}_{p['nome']}"):
                                atualizar_embarque(id_sel, p.to_dict(), True); st.rerun()
                                
                    with c_ok:
                        st.caption("🟢 EMBARCADOS")
                        embarcados = df_grp[df_grp['embarcou'] == True].sort_values('nome')
                        for _, p in embarcados.iterrows():
                            col_n, col_b = st.columns([4, 1])
                            col_n.write(f":gray[~~{p['nome']}~~]")
                            if col_b.button("🔙", key=f"rem_{grp}_{p['nome']}"):
                                atualizar_embarque(id_sel, p.to_dict(), False); st.rerun()

    # --- ABA 5: CONFIGURAÇÕES (ADMIN) ---
    with tab_config:
        st.subheader("⚙️ Painel Administrativo")
        
        with st.container(border=True):
            st.write("**Relatórios**")
            if st.button("📥 Exportar Lista para Excel", use_container_width=True):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Passageiros')
                st.download_button("💾 Baixar Arquivo Excel", output.getvalue(), f"lista_{id_sel}.xlsx", use_container_width=True)
        
        st.divider()
        with st.expander("🚨 Zona de Perigo"):
            st.warning("Ao finalizar, o evento sairá da lista de ativos.")
            if st.button("🏁 Finalizar e Arquivar Evento", type="primary", use_container_width=True):
                inicializar_db().collection("eventos").document(id_sel).update({"status": "finalizado"})
                st.rerun()

# Execução
if __name__ == "__main__":
    exibir_modulo_passagens()
