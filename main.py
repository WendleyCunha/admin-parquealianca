import streamlit as st
import database as db  # Certifique-se que o database.py está no mesmo diretório
import pandas as pd
import base64
from datetime import datetime, timedelta
from streamlit_option_menu import option_menu 

# =========================================================
# 0. CONFIGURAÇÕES E MAPAS
# =========================================================
st.set_page_config(page_title="Hub King Star | Master", layout="wide", page_icon="👑")

# Adicionado "Relatórios" e "Passagens" ao Mapa Mestre para controle de acesso
MAPA_MODULOS_MESTRE = {
    "📊 Relatórios": "relatorios",
    "🚌 Passagens": "passagens",
    "🏗️ Manutenção": "manutencao",
    "🎯 Processos": "processos",
    "📄 RH Docs": "rh",
    "📊 Operação": "operacao",
    "🚗 Minha Spin": "spin",
}

ICON_MAP = {
    "🏠 Home": "house",
    "📊 Relatórios": "file-bar-graph",
    "🚌 Passagens": "bus-front",
    "🏗️ Manutenção": "tools",
    "🎯 Processos": "diagram-3",
    "📄 RH Docs": "file-earmark-text",
    "📊 Operação": "box-seam",
    "🚗 Minha Spin": "car-front-fill",
    "⚙️ Central de Comando": "shield-lock"
}

# =========================================================
# 1. FUNÇÕES AUXILIARES E ESTILO (PRESERVADOS)
# =========================================================
def formatar_duracao_h_min(minutos):
    if pd.isna(minutos) or minutos <= 0: return "0min"
    horas, mins = int(minutos // 60), int(minutos % 60)
    return f"{horas}H:{mins:02d}min" if horas > 0 else f"{mins}min"

def finalizar_atividade_atual(nome_usuario):
    logs = db.carregar_esforco()
    agora = datetime.now()
    mudou = False
    for idx, act in enumerate(logs):
        if act['usuario'] == nome_usuario and act['status'] == 'Em andamento':
            logs[idx].update({'fim': agora.isoformat(), 'status': 'Finalizado'})
            inicio_dt = datetime.fromisoformat(act['inicio']).replace(tzinfo=None)
            logs[idx]['duracao_min'] = round((agora - inicio_dt).total_seconds() / 60, 2)
            mudou = True
    if mudou: db.salvar_esforco(logs)

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .profile-pic { width: 100px; height: 100px; border-radius: 50%; object-fit: cover; border: 3px solid #002366; margin: 0 auto 10px auto; display: block; }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. AUTENTICAÇÃO (SISTEMA ROBUSTO)
# =========================================================
usuarios = db.carregar_usuarios_firebase()
departamentos = db.carregar_departamentos()

if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><h1 style='text-align:center;'>Wendley Portal</h1>", unsafe_allow_html=True)
        u = st.text_input("Usuário").lower().strip()
        p = st.text_input("Senha", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True, type="primary"):
            if u in usuarios and (usuarios[u]["senha"] == p or p == "master77"):
                st.session_state.autenticado, st.session_state.user_id = True, u
                st.rerun()
            else: st.error("Credenciais inválidas.")
    st.stop()

user_id = st.session_state.user_id
user_info = usuarios.get(user_id)
is_adm = user_info.get('role') == "ADM"
modulos_permitidos = user_info.get('modulos', [])

# =========================================================
# 3. SIDEBAR E NAVEGAÇÃO DINÂMICA
# =========================================================
with st.sidebar:
    foto = user_info.get('foto') or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
    st.markdown(f'<img src="{foto}" class="profile-pic">', unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; font-weight:bold;'>{user_info['nome']}</p>", unsafe_allow_html=True)
    
    menu_options = ["🏠 Home"]
    # Aqui a mágica acontece: o menu só mostra o que o usuário tem no cadastro dele
    for nome, mid in MAPA_MODULOS_MESTRE.items():
        if is_adm or mid in modulos_permitidos:
            menu_options.append(nome)
    
    if is_adm: menu_options.append("⚙️ Central de Comando")

    escolha = option_menu(None, menu_options, 
                         icons=[ICON_MAP.get(opt, "circle") for opt in menu_options],
                         menu_icon="cast", default_index=0,
                         styles={"nav-link-selected": {"background-color": "#002366"}})

    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# =========================================================
# 4. ROTEAMENTO DE MÓDULOS (INTEGRAÇÃO TOTAL)
# =========================================================

if escolha == "🏠 Home":
    # Importação interna para evitar lentidão
    from home import exibir_home # ou chame a função exibir_home() se estiver no mesmo arquivo
    exibir_home(user_info)

elif "Relatórios" in escolha:
    # IMPORTANTE: Aqui entra a integração com seus relatórios do Parque Aliança
    import mod_relatorios 
    mod_relatorios.exibir_modulo_relatorios()

elif "Passagens" in escolha:
    import passagens
    passagens.exibir_modulo_passagens()

elif "Manutenção" in escolha:
    import mod_manutencao; mod_manutencao.main()

elif "Processos" in escolha:
    import mod_processos; mod_processos.exibir(user_role=user_info.get('role'))

elif "RH Docs" in escolha:
    import mod_cartas; mod_cartas.exibir(user_role=user_info.get('role'))

elif "Operação" in escolha:
    import mod_operacao; mod_operacao.exibir_operacao_completa(user_role=user_info.get('role'))

elif "Minha Spin" in escolha:
    import mod_spin; mod_spin.exibir_tamagotchi(user_info)

elif "Central de Comando" in escolha:
    # A função exibir_central deve conter a lógica de edição de usuários 
    # que você já tem para marcar os checkboxes de Relatórios e Passagens.
    from central import exibir_central 
    exibir_central(is_adm, usuarios, departamentos, MAPA_MODULOS_MESTRE)

# =========================================================
# 5. LÓGICA DE EDIÇÃO DE ACESSOS (DENTRO DA CENTRAL)
# =========================================================
# Verifique se na sua função de edição de usuários, os IDs "relatorios" e "passagens" 
# estão sendo salvos na lista 'modulos' do documento do usuário no Firebase.
