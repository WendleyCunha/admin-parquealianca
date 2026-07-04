# =============================================================
# autenticacao.py
# Tela de login.
#
# ATUALIZAÇÃO (v6.1): cores agora vêm de tema.py (CORES) em vez de
# hexadecimais escritos aqui dentro — trocar a paleta do app não
# exige mais tocar neste arquivo.
#
#  - Login consulta a coleção "usuarios_sistema" (Firestore), criada
#    em CONFIGURAÇÃO → "Usuários e Permissões". Cada usuário carrega
#    consigo suas permissões por aba.
#  - Existe um usuário administrador de fábrica (fallback) que
#    continua funcionando SEMPRE — mesmo depois de já existirem
#    outros usuários — para garantir que o dono do sistema nunca
#    fique trancado para fora. Ele tem acesso total (admin=True).
# =============================================================
import streamlit as st

from estilo import get_logo_base64
from database import autenticar_usuario
from tema import CORES

_ADMIN_FALLBACK_USER  = "wendley"
_ADMIN_FALLBACK_SENHA = "Qmerd@10"


def _tentar_login(usuario: str, senha: str):
    """Retorna o dict de dados do usuário autenticado, ou None."""
    uid_digitado = (usuario or "").lower().strip()

    # Admin de fábrica: sempre válido, independente do que estiver no banco.
    if uid_digitado == _ADMIN_FALLBACK_USER and senha == _ADMIN_FALLBACK_SENHA:
        return {
            "username": _ADMIN_FALLBACK_USER,
            "nome_exibicao": "Administrador",
            "admin": True,
            "permissoes": {},
        }

    return autenticar_usuario(usuario, senha)


def tela_login():
    st.markdown(f"""
    <style>
    .stApp {{ background: linear-gradient(180deg, {CORES['fundo_pagina_1']} 0%, {CORES['primaria_clara']} 100%) !important; }}
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
            f'<div style="background: {CORES["primaria"]}; border-radius: 12px; width: 54px; height: 54px;'
            f'display: flex; align-items: center; justify-content: center;'
            f'font-weight: 700; font-size: 20px; color: #fff;">PA</div>'
        )

    col_left, col_center, col_right = st.columns([1, 1.3, 1])
    with col_center:
        st.markdown(f"""
        <div style="background: {CORES['fundo_card_1']}; border: 1px solid {CORES['primaria_borda']}; border-radius: 16px;
            margin-top: 8vh; text-align: center; overflow: hidden;
            box-shadow: 0 14px 34px rgba(30,70,120,0.14);">
          <div style="background: {CORES['primaria_clara']}; padding: 9px 0; border-bottom: 2px solid {CORES['primaria']};">
            <span style="color: {CORES['primaria_escura']}; font-weight: 800; font-size: 0.7rem; letter-spacing: 0.14em;">
                ACESSO RESTRITO</span>
          </div>
          <div style="padding: 2.2rem 2rem 2rem;">
            <div style="display: flex; justify-content: center; margin-bottom: 1.25rem;">
              {badge_html}
            </div>
            <h2 style="color: {CORES['texto_principal']} !important; font-size: 21px; font-weight: 700; margin-bottom: 4px;">
                Congregação Parque Aliança – 72249</h2>
            <p style="color: {CORES['texto_muted']} !important; font-size: 12.5px; font-weight: 700;
                text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0;">
                Comissão de Funcionamento</p>
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
            dados_usuario = _tentar_login(user, senha)
            if dados_usuario:
                st.session_state["autenticado"]          = True
                st.session_state["usuario_logado"]       = dados_usuario.get("nome_exibicao") or user.strip().title()
                st.session_state["usuario_logado_dados"] = dados_usuario
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
