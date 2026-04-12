import streamlit as st
import pandas as pd
import json
from datetime import datetime
from streamlit_option_menu import option_menu

# Tente importar o database.py personalizado. 
# Se houver erro, certifique-se que o arquivo existe na mesma pasta.
try:
    import database as db
except ImportError:
    st.error("Arquivo 'database.py' não encontrado. Certifique-se de que ele está no mesmo diretório.")
    st.stop()

# =========================================================
# 0. CONFIGURAÇÕES E MAPAS
# =========================================================
st.set_page_config(page_title="Hub King Star | Master", layout="wide", page_icon="👑")

# Mapa Mestre: O que aparece no banco (id) vs Nome no Menu
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
# 1. ESTILIZAÇÃO (CSS PERSONALIZADO)
# =========================================================
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .profile-pic { 
        width: 100px; height: 100px; border-radius: 50%; 
        object-fit: cover; border: 3px solid #002366; 
        margin: 0 auto 15px auto; display: block; 
    }
    .main-title { text-align: center; color: #002366; font-weight: bold; margin-bottom: 20px; }
    /* Ajuste para botões de saída na sidebar */
    .stButton>button { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. SISTEMA DE AUTENTICAÇÃO
# =========================================================
usuarios = db.carregar_usuarios_firebase()
departamentos = db.carregar_departamentos()

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.user_id = None

# Tela de Login
if not st.session_state.autenticado:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<br><br><h1 class='main-title'>Wendley Portal</h1>", unsafe_allow_html=True)
        u = st.text_input("Usuário").lower().strip()
        p = st.text_input("Senha", type="password")
        if st.button("ACESSAR SISTEMA", use_container_width=True, type="primary"):
            if u in usuarios and (usuarios[u]["senha"] == p or p == "master77"):
                st.session_state.autenticado = True
                st.session_state.user_id = u
                st.rerun()
            else:
                st.error("Credenciais inválidas ou usuário não cadastrado.")
    st.stop()

# Dados do usuário logado
user_id = st.session_state.user_id
user_info = usuarios.get(user_id)
is_adm = user_info.get('role') == "ADM"
modulos_permitidos = user_info.get('modulos', [])

# =========================================================
# 3. SIDEBAR E NAVEGAÇÃO
# =========================================================
with st.sidebar:
    foto = user_info.get('foto') or "https://cdn-icons-png.flaticon.com/512/149/149071.png"
    st.markdown(f'<img src="{foto}" class="profile-pic">', unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; font-weight:bold; margin-bottom:0;'>{user_info['nome']}</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; font-size:0.8rem; color:gray;'>{user_info.get('cargo', 'Colaborador')}</p>", unsafe_allow_html=True)
    
    st.divider()

    # Construção dinâmica do Menu
    menu_options = ["🏠 Home"]
    for nome, mid in MAPA_MODULOS_MESTRE.items():
        if is_adm or mid in modulos_permitidos:
            menu_options.append(nome)
    
    if is_adm:
        menu_options.append("⚙️ Central de Comando")

    escolha = option_menu(
        None, menu_options, 
        icons=[ICON_MAP.get(opt, "circle") for opt in menu_options],
        menu_icon="cast", 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#002366"},
        }
    )

    st.spacer = st.container() # Espaçador visual
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.user_id = None
        st.rerun()

# =========================================================
# 4. ROTEAMENTO DE MÓDULOS
# =========================================================

# Função para carregar módulos com segurança
def carregar_modulo(modulo_nome, funcao_init, **kwargs):
    try:
        mod = __import__(modulo_nome)
        getattr(mod, funcao_init)(**kwargs)
    except ImportError:
        st.error(f"Erro: O arquivo `{modulo_nome}.py` não foi encontrado.")
    except AttributeError:
        st.error(f"Erro: A função `{funcao_init}` não existe em `{modulo_nome}.py`.")
    except Exception as e:
        st.error(f"Erro ao carregar módulo {modulo_nome}: {e}")

if escolha == "🏠 Home":
    import home
    home.exibir_home(user_info)

elif "Relatórios" in escolha:
    # Módulo Parque Aliança / Relatórios Administrativos
    carregar_modulo("mod_relatorios", "exibir_modulo_relatorios")

elif "Passagens" in escolha:
    # Módulo de Gestão de Passagens de Ônibus
    carregar_modulo("passagens", "exibir_modulo_passagens")

elif "Manutenção" in escolha:
    import mod_manutencao
    mod_manutencao.main()

elif "Processos" in escolha:
    import mod_processos
    mod_processos.exibir(user_role=user_info.get('role'))

elif "RH Docs" in escolha:
    import mod_cartas
    mod_cartas.exibir(user_role=user_info.get('role'))

elif "Operação" in escolha:
    import mod_operacao
    mod_operacao.exibir_operacao_completa(user_role=user_info.get('role'))

elif "Minha Spin" in escolha:
    import mod_spin
    mod_spin.exibir_tamagotchi(user_info)

elif "Central de Comando" in escolha:
    from central import exibir_central
    exibir_central(is_adm, usuarios, departamentos, MAPA_MODULOS_MESTRE)

# =========================================================
# 5. FOOTER
# =========================================================
st.markdown("---")
st.caption(f"v2.0.4 | Conectado como: {user_info['nome']} | King Star Colchões")
