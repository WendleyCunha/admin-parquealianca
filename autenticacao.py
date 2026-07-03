# =============================================================
# autenticacao.py
# Credenciais e tela de login.
#
# Origem: Seção 4 ("AUTENTICAÇÃO") do antigo main.py monolítico.
# Único ajuste: agora usa o logo personalizado (estilo.get_logo_base64)
# quando existe um arquivo de logo na raiz do projeto — se não
# houver, cai de volta no badge "PA" original, sem quebrar nada.
# =============================================================
import streamlit as st

from estilo import get_logo_base64

_AUTH_USERS = {"wendley": "Qmerd@10"}


def tela_login():
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #FAF7EE 0%, #F2ECD6 100%) !important; }
    </style>
    """, unsafe_allow_html=True)

    logo_b64, logo_mime = get_logo_base64()
    if logo_b64:
        badge_html = (
            f'<img src="data:{logo_mime};base64,{logo_b64}" '
            f'style="width:54px;height:54px;border-radius:12px;object-fit:contain;'
            f'background:#fff;padding:4px;" />'
        )
    else:
        badge_html = (
            '<div style="background: #C9A227; border-radius: 12px; width: 54px; height: 54px;'
            'display: flex; align-items: center; justify-content: center;'
            'font-weight: 700; font-size: 20px; color: #111;">PA</div>'
        )

    col_left, col_center, col_right = st.columns([1, 1.2, 1])
    with col_center:
        st.markdown(f"""
        <div style="background: #FFFFFF; border: 1px solid #EEE3B8; border-radius: 16px;
            margin-top: 12vh; text-align: center; overflow: hidden;
            box-shadow: 0 14px 34px rgba(140,110,20,0.14);">
          <div style="background: #111111; padding: 9px 0; border-bottom: 3px solid #C9A227;">
            <span style="color: #E9CF6B; font-weight: 800; font-size: 0.7rem; letter-spacing: 0.14em;">
                PARQUE ALIANÇA · PORTAL</span>
          </div>
          <div style="padding: 2.2rem 2rem 2.4rem;">
            <div style="display: flex; justify-content: center; margin-bottom: 1.25rem;">
              {badge_html}
            </div>
            <h2 style="color: #1A1A1A !important; font-size: 22px; font-weight: 700; margin-bottom: 6px;">
                Portal de Relatórios</h2>
            <p style="color: #9C8A46 !important; font-size: 13px; margin-bottom: 0.5rem;">
                Congregação Parque Aliança – 72249</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            user  = st.text_input("Usuário", placeholder="Digite seu usuário",
                                   label_visibility="collapsed", key="login_user")
            senha = st.text_input("Senha",   placeholder="Digite sua senha",
                                   type="password", label_visibility="collapsed", key="login_pass")
            entrar = st.button("Acessar Portal", use_container_width=True, type="primary")

        if entrar:
            if _AUTH_USERS.get(user.lower().strip()) == senha:
                st.session_state["autenticado"]    = True
                st.session_state["usuario_logado"] = user.strip().title()
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
