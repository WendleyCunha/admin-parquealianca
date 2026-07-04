# =============================================================
# permissoes.py  (NOVO)
# Camada fina de controle de acesso por aba, baseada no usuário
# que fez login (guardado em st.session_state["usuario_logado_dados"]
# por autenticacao.py).
#
# Nenhum outro módulo deve ler st.session_state["usuario_logado_dados"]
# diretamente — sempre passar por aqui, para manter uma única fonte
# da verdade sobre "quem pode ver o quê" e "quem pode editar o quê".
# =============================================================
import streamlit as st

from constantes import ABAS_SISTEMA, PERMISSOES_PADRAO_ADMIN


def usuario_atual():
    """Dict completo do usuário logado (ou {} se, por algum motivo, vazio)."""
    return st.session_state.get("usuario_logado_dados") or {}


def permissoes_usuario_atual():
    """
    Dict {aba_id: nivel}. Administradores recebem 'editar' em tudo
    automaticamente, sem precisar ter isso gravado no Firestore.
    """
    dados = usuario_atual()
    if dados.get("admin"):
        return PERMISSOES_PADRAO_ADMIN
    return dados.get("permissoes", {}) or {}


def nivel_acesso(aba_id: str) -> str:
    """'sem_acesso' | 'visualizar' | 'editar' para a aba informada."""
    return permissoes_usuario_atual().get(aba_id, "sem_acesso")


def pode_ver(aba_id: str) -> bool:
    return nivel_acesso(aba_id) in ("visualizar", "editar")


def pode_editar(aba_id: str) -> bool:
    return nivel_acesso(aba_id) == "editar"


def abas_visiveis():
    """Subconjunto de ABAS_SISTEMA que o usuário atual pode ao menos visualizar."""
    return [aba for aba in ABAS_SISTEMA if pode_ver(aba["id"])]


def aviso_somente_leitura(texto: str = None):
    """Mostra um aviso discreto (não bloqueante) de modo somente-leitura."""
    st.markdown(f"""
    <div style="background:#FBF1D4;border:1px solid #E9D48E;border-radius:10px;
        padding:8px 14px;margin-bottom:14px;font-size:0.82rem;color:#8A6D14;
        display:flex;align-items:center;gap:8px;">
        👁️ <span>{texto or "Você tem permissão apenas de <strong>visualização</strong> nesta aba."}</span>
    </div>""", unsafe_allow_html=True)
