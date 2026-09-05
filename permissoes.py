# =============================================================
# permissoes.py
# Camada fina de controle de acesso por aba, baseada no usuário
# que fez login (guardado em st.session_state["usuario_logado_dados"]
# por autenticacao.py).
#
# Nenhum outro módulo deve ler st.session_state["usuario_logado_dados"]
# diretamente — sempre passar por aqui, para manter uma única fonte
# da verdade sobre "quem pode ver o quê" e "quem pode editar o quê".
#
# ATUALIZAÇÃO (reorganização visual — menu por módulo + área de admin):
#   eh_admin() → [NOVO] "Usuários e Permissões" deixou de ser mais uma
#   sub-aba de Configuração (gated por nivel_acesso("configuracao"))
#   e virou um botão à parte no cabeçalho, visível só para quem é
#   administrador de verdade (flag admin=True do usuário, não mais
#   uma permissão de aba). Isso foi um pedido explícito do usuário
#   ("é um acesso ADM"), então é a ÚNICA mudança de regra desta
#   reorganização — todo o resto (abas_visiveis, pode_ver, pode_editar)
#   continua exatamente com a mesma lógica de antes.
# =============================================================
import streamlit as st
from constantes import ABAS_SISTEMA, PERMISSOES_PADRAO_ADMIN


def usuario_atual():
    """Dict completo do usuário logado (ou {} se, por algum motivo, vazio)."""
    return st.session_state.get("usuario_logado_dados") or {}


def eh_admin() -> bool:
    """
    True se o usuário logado for administrador (acesso total automático).

    [NOVO] Usada especificamente para liberar o botão/tela de "Usuários
    e Permissões" no cabeçalho — essa área agora é exclusiva de quem é
    admin de verdade, e não mais de quem tem nivel_acesso("configuracao")
    == "editar". As demais permissões (abas_visiveis, pode_ver, pode_editar)
    continuam usando permissoes_usuario_atual()/nivel_acesso() normalmente,
    sem nenhuma mudança de comportamento.
    """
    return bool(usuario_atual().get("admin"))


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
    <div style="background:#E7F0FA;border:1px solid #BBD3EC;border-radius:10px;
        padding:8px 14px;margin-bottom:14px;font-size:0.82rem;color:#1F4E86;
        display:flex;align-items:center;gap:8px;">
        👁️ <span>{texto or "Você tem permissão apenas de <strong>visualização</strong> nesta aba."}</span>
    </div>""", unsafe_allow_html=True)
