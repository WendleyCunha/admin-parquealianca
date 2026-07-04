# =============================================================
# database.py
# TODA a comunicação com o Firestore vive aqui: conexão, cache
# de leitura e operações de escrita. Nenhum outro arquivo do
# projeto deve importar firestore/service_account diretamente —
# sempre passe por aqui, igual já fazíamos no projeto Kingstar.
#
# Origem: Seção 6 ("BANCO DE DADOS — CONEXÃO E CACHE") + Seção 7
# ("OPERAÇÕES DE ESCRITA NO BANCO") do antigo main.py monolítico.
#
# ATUALIZAÇÃO: acrescentada a coleção "usuarios_sistema", usada
# para criar usuários e definir permissão (sem_acesso / visualizar
# / editar) por aba — ver permissoes.py e a nova sub-aba "Usuários
# e Permissões" em modulo/mod_configuracao.py.
# =============================================================
import json

import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account

from utilitarios import obter_mes_vigente_str


def inicializar_db():
    if "db" not in st.session_state:
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            st.session_state.db = firestore.Client(
                credentials=creds, project="wendleydesenvolvimento")
        except Exception:
            return None
    return st.session_state.db


# ── Leitura (cacheada) ──────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def carregar_membros_cached():
    db = inicializar_db()
    if not db:
        return {}
    return {doc.id: doc.to_dict() for doc in db.collection("membros_v2").stream()}


@st.cache_data(ttl=60, show_spinner=False)
def carregar_relatorios_cached():
    db = inicializar_db()
    if not db:
        return []
    docs = db.collection("relatorios_parque_alianca").stream()
    return [
        {"id": doc.id, **doc.to_dict()}
        for doc in docs
        if doc.to_dict().get("status_validacao") != "EXCLUIDO"
    ]


@st.cache_data(ttl=120, show_spinner=False)
def carregar_anuncios_cached():
    db = inicializar_db()
    if not db:
        return []
    try:
        docs = (db.collection("anuncios")
                  .order_by("data_postagem", direction=firestore.Query.DESCENDING)
                  .stream())
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def carregar_assistencia_cached():
    """Carrega todos os registros de assistência às reuniões."""
    db = inicializar_db()
    if not db:
        return []
    try:
        docs = db.collection("assistencia_reunioes").stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def carregar_usuarios_cached():
    """Dict {username: {senha, nome_exibicao, admin, permissoes}}."""
    db = inicializar_db()
    if not db:
        return {}
    try:
        return {doc.id: doc.to_dict() for doc in db.collection("usuarios_sistema").stream()}
    except Exception:
        return {}


def carregar_membros():
    return carregar_membros_cached()


def carregar_relatorios():
    return carregar_relatorios_cached()


def carregar_anuncios():
    return carregar_anuncios_cached()


def carregar_assistencia():
    return carregar_assistencia_cached()


def carregar_usuarios():
    return carregar_usuarios_cached()


# ── Escrita ───────────────────────────────────────────────────
def atualizar_membro(nome, categoria, novo=False, extra=None):
    db = inicializar_db()
    if db:
        dados = {"categoria": categoria, "nome_oficial": nome}
        if novo:
            dados["mes_inicio"] = obter_mes_vigente_str()
        if extra:
            dados.update({k: v for k, v in extra.items() if v is not None})
        db.collection("membros_v2").document(nome).set(dados, merge=True)
        carregar_membros_cached.clear()


def deletar_relatorio(relatorio_id):
    db = inicializar_db()
    if not db:
        st.error("Sem conexão com o banco.")
        return
    try:
        db.collection("relatorios_parque_alianca").document(relatorio_id).delete()
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")
        return
    carregar_relatorios_cached.clear()
    carregar_membros_cached.clear()
    st.toast("🗑️ Relatório deletado permanentemente!")
    st.rerun()


def deletar_membro(nome):
    db = inicializar_db()
    if not db:
        st.error("Sem conexão com o banco.")
        return
    try:
        db.collection("membros_v2").document(nome).delete()
    except Exception as e:
        st.error(f"Erro ao deletar membro: {e}")
        return
    carregar_membros_cached.clear()
    carregar_relatorios_cached.clear()
    st.toast(f"🗑️ Membro '{nome}' deletado permanentemente!")
    st.rerun()


def salvar_baixa_manual(nome, mes, horas, estudos):
    db = inicializar_db()
    if db:
        novo_doc = {
            "nome": nome, "mes_referencia": mes, "horas": horas,
            "estudos_biblicos": estudos, "timestamp": firestore.SERVER_TIMESTAMP
        }
        db.collection("relatorios_parque_alianca").add(novo_doc)
        carregar_relatorios_cached.clear()
        st.success(f"✅ Relatório de {nome} adicionado!")
        st.rerun()


def salvar_anuncio(dados):
    db = inicializar_db()
    if not db:
        return False
    dados["data_postagem"] = firestore.SERVER_TIMESTAMP
    db.collection("anuncios").add(dados)
    carregar_anuncios_cached.clear()
    return True


def deletar_anuncio(anuncio_id):
    db = inicializar_db()
    if db:
        db.collection("anuncios").document(anuncio_id).delete()
        carregar_anuncios_cached.clear()
        st.toast("✅ Anúncio deletado!")
        st.rerun()


def salvar_assistencia(tipo_reuniao, ano_referencia, mes, qtd_reunioes, total_assistencia):
    """Salva ou atualiza um registro de assistência no Firestore."""
    db = inicializar_db()
    if not db:
        st.error("Sem conexão com o banco.")
        return False
    doc_id = f"{tipo_reuniao}_{ano_referencia}_{mes}".replace(" ", "_").upper()
    media = round(total_assistencia / qtd_reunioes, 1) if qtd_reunioes > 0 else 0
    dados = {
        "tipo_reuniao":      tipo_reuniao,
        "ano_referencia":    ano_referencia,
        "mes":               mes,
        "qtd_reunioes":      qtd_reunioes,
        "total_assistencia": total_assistencia,
        "media_semana":      media,
        "atualizado_em":     firestore.SERVER_TIMESTAMP,
    }
    db.collection("assistencia_reunioes").document(doc_id).set(dados)
    carregar_assistencia_cached.clear()
    return True


# ── Usuários e permissões ───────────────────────────────────────
def salvar_usuario(username, senha, nome_exibicao, permissoes, admin=False):
    """
    Cria ou atualiza um usuário do sistema.
    permissoes: dict {aba_id: "sem_acesso"|"visualizar"|"editar"}
    Se senha vier vazia em uma edição, mantém a senha já gravada.
    """
    db = inicializar_db()
    if not db:
        st.error("Sem conexão com o banco.")
        return False

    uid = (username or "").lower().strip()
    if not uid:
        st.error("Informe um nome de usuário.")
        return False

    dados = {
        "username":      uid,
        "nome_exibicao": (nome_exibicao or username).strip(),
        "permissoes":    permissoes or {},
        "admin":         bool(admin),
    }
    if senha:
        dados["senha"] = senha

    db.collection("usuarios_sistema").document(uid).set(dados, merge=True)
    carregar_usuarios_cached.clear()
    return True


def deletar_usuario(username):
    db = inicializar_db()
    if db:
        db.collection("usuarios_sistema").document((username or "").lower().strip()).delete()
        carregar_usuarios_cached.clear()


def autenticar_usuario(username, senha):
    """Retorna o dict do usuário se usuário+senha baterem, senão None."""
    usuarios = carregar_usuarios()
    uid = (username or "").lower().strip()
    user = usuarios.get(uid)
    if user and user.get("senha") == senha:
        return {"username": uid, **user}
    return None
