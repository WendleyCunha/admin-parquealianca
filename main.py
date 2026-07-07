# =============================================================
# main.py
# PONTO DE ENTRADA DO APP — e só isso.
#
# ATUALIZAÇÃO (v6.0):
#  - sidebar.py foi REMOVIDO do projeto. Tudo que estava na barra
#    lateral (seletor de mês, KPIs rápidos, usuário logado, botão
#    Sair) agora vive dentro da própria página, em um cabeçalho +
#    barra de filtros (mais fácil de usar no celular, sem precisar
#    abrir um menu escondido).
#  - As abas exibidas dependem da PERMISSÃO do usuário logado
#    (ver permissoes.py e a nova sub-aba "Usuários e Permissões"
#    em CONFIGURAÇÃO). Quem não tem acesso a uma aba simplesmente
#    não a vê.
#
# ATUALIZAÇÃO (v6.1):
#  - CORREÇÃO DE VAZAMENTO DE DADOS: a barra "📅 Mês de análise"
#    (com os KPIs de Identificados / Em Triagem, que pertencem ao
#    módulo de RELATÓRIOS) era renderizada para QUALQUER usuário
#    logado, ANTES de checar as permissões dele — inclusive para
#    quem só tinha acesso à aba Passagens. Agora essa barra (e o
#    carregamento de membros/relatórios/assistência que a alimenta)
#    só roda se o usuário tiver permissão em "relatorios" e/ou
#    "configuracao" — as únicas abas que de fato usam mes_sel/df.
#    Passagens, Anúncios e Manutenção nunca precisaram desses dados.
#
# ATUALIZAÇÃO (v6.3):
#  - CORREÇÃO DEFINITIVA DO VAZAMENTO ENTRE ABAS: chamada nova
#    aplicar_fix_abas() logo após aplicar_estilo(). Ela injeta um
#    JavaScript que garante que só o conteúdo da aba selecionada
#    apareça na tela — em qualquer nível de aninhamento (abas dentro
#    de abas). Ver comentários em estilo.py para o detalhe técnico.
# =============================================================
import pandas as pd
import streamlit as st

from estilo import aplicar_estilo, aplicar_fix_abas, get_logo_path, get_logo_base64
from tabs_persistentes import abas_persistentes
from autenticacao import tela_login
from database import carregar_membros, carregar_relatorios, carregar_assistencia
from utilitarios import obter_mes_vigente_str, processar_dataframe
from constantes import ABAS_SISTEMA
import permissoes

from modulo.mod_relatorios import aba_relatorios
from modulo.mod_anuncios import aba_anuncios
from modulo.mod_passagens import exibir_modulo_passagens
from modulo.mod_manutencao import aba_manutencao
from modulo.mod_configuracao import aba_configuracao


# =============================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================
st.set_page_config(
    page_title="Parque Aliança · Gestão",
    layout="wide",
    page_icon=get_logo_path() or "🏢",
    initial_sidebar_state="collapsed",
)

aplicar_estilo()
aplicar_fix_abas()  # CORREÇÃO (v6.3): garante que só a aba selecionada apareça na tela

# Abas que realmente usam o "Mês de Análise" (mes_sel / df / df_ok / df_mes /
# membros_db). Se o usuário não tiver acesso a nenhuma delas, a barra de
# filtro e os KPIs de Identificados/Em Triagem nem são carregados.
ABAS_QUE_USAM_FILTRO_MES = {"relatorios", "configuracao"}


def _renderizar_cabecalho():
    """Marca + identidade da congregação + usuário logado, tudo no topo da página."""
    logo_b64, logo_mime = get_logo_base64()
    if logo_b64:
        marca_html = (f'<img src="data:{logo_mime};base64,{logo_b64}" '
                      f'style="width:38px;height:38px;object-fit:contain;border-radius:8px;" />')
    else:
        marca_html = '<div style="font-size:1.7rem;">🕊️</div>'

    usuario = st.session_state.get("usuario_logado", "Usuário")
    inicial = usuario[0].upper() if usuario else "?"

    col_id, col_user = st.columns([4, 1.4])
    with col_id:
        st.markdown(f"""
        <div class="pa-header">
          <div class="pa-header-brand">
            {marca_html}
            <div>
              <div class="pa-header-title">Congregação Parque Aliança – 72249</div>
              <div class="pa-header-sub">Comissão de Funcionamento</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
    with col_user:
        st.markdown(f"""
        <div class="pa-header-user">
          <div class="pa-avatar">{inicial}</div>
          <div>
            <div class="pa-header-user-name">{usuario}</div>
            <div class="pa-header-user-role">Conectado</div>
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button("Sair", use_container_width=True, key="btn_sair_topo"):
            for k in ["autenticado", "usuario_logado", "usuario_logado_dados"]:
                st.session_state.pop(k, None)
            st.rerun()


def _renderizar_filtros(df, mes_vigente):
    """Barra de filtros dentro da página — substitui a antiga sidebar.
    Só deve ser chamada quando o usuário tem acesso a Relatórios e/ou
    Configuração (ver ABAS_QUE_USAM_FILTRO_MES)."""
    st.markdown('<div class="pa-filtros">', unsafe_allow_html=True)
    st.markdown('<div class="pa-filtros-label">📅 Mês de análise</div>', unsafe_allow_html=True)

    col_sel, col_badge, col_k1, col_k2 = st.columns([2, 1.3, 1, 1])

    meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else [mes_vigente]
    idx_default = len(meses_disponiveis) - 1
    if mes_vigente in meses_disponiveis:
        idx_default = meses_disponiveis.index(mes_vigente)

    with col_sel:
        mes_sel = st.selectbox("Mês", meses_disponiveis, index=idx_default,
                                label_visibility="collapsed")

    eh_vigente = (mes_sel == mes_vigente)
    with col_badge:
        if eh_vigente:
            st.markdown('<div class="mes-badge"><span class="mes-dot"></span>MÊS VIGENTE</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="mes-badge-historico">📜 HISTÓRICO</div>',
                        unsafe_allow_html=True)

    if not df.empty:
        df_mes_side = df[df['mes_referencia'] == mes_sel]
        df_id_side  = df_mes_side[df_mes_side['status_validacao'] == "IDENTIFICADO"]
        df_tri_side = df_mes_side[df_mes_side['status_validacao'] == "TRIAGEM"]
        with col_k1:
            st.markdown(f"""<div class="pa-metric" style="padding:0.6rem 0.8rem;margin-bottom:0;">
                <div class="pa-metric-value" style="font-size:18px;">{len(df_id_side)}</div>
                <div class="pa-metric-label">Identificados</div></div>""", unsafe_allow_html=True)
        with col_k2:
            st.markdown(f"""<div class="pa-metric" style="padding:0.6rem 0.8rem;margin-bottom:0;">
                <div class="pa-metric-value" style="font-size:18px;color:#c2410c;">{len(df_tri_side)}</div>
                <div class="pa-metric-label">Em triagem</div></div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    return mes_sel


# =============================================================
# PONTO DE ENTRADA PRINCIPAL
# =============================================================
def main():
    if not st.session_state.get("autenticado"):
        tela_login()
        st.stop()

    # ---- Permissões PRIMEIRO: define o que este usuário pode ver ----
    abas_permitidas = permissoes.abas_visiveis()

    _renderizar_cabecalho()

    if not abas_permitidas:
        st.markdown("""
        <div class="pa-aviso-atencao">
        ⚠️ Seu usuário não tem acesso a nenhuma aba. Contate um administrador
        para liberar as permissões em <strong>Configuração → Usuários e Permissões</strong>.
        </div>""", unsafe_allow_html=True)
        return

    ids_permitidos = {a["id"] for a in abas_permitidas}
    precisa_filtro_mes = bool(ids_permitidos & ABAS_QUE_USAM_FILTRO_MES)

    # ---- Só carrega dados de Relatórios e mostra a barra de Mês/KPIs ----
    # ---- se o usuário realmente tiver acesso a uma aba que usa isso. ----
    mes_vigente = obter_mes_vigente_str()
    if precisa_filtro_mes:
        membros_db        = carregar_membros()
        relatorios_brutos = carregar_relatorios()
        registros_assist  = carregar_assistencia()
        df                = processar_dataframe(relatorios_brutos, membros_db)

        mes_sel = _renderizar_filtros(df, mes_vigente)

        df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
        df_ok  = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()
    else:
        # Usuário sem acesso a Relatórios/Configuração: nenhum dado de
        # relatório é carregado nem exibido — nem a barra, nem os KPIs.
        membros_db       = {}
        registros_assist = None
        df     = pd.DataFrame()
        df_mes = pd.DataFrame()
        df_ok  = pd.DataFrame()
        mes_sel = mes_vigente

    labels_abas = [f"{a['icone']}  {a['label'].upper()}" for a in abas_permitidas]
    idx_aba_ativa = abas_persistentes(labels_abas, key="abas_principais")
    aba_ativa   = abas_permitidas[idx_aba_ativa]
    aba_id      = aba_ativa["id"]
    pode_editar = permissoes.pode_editar(aba_id)

    if aba_id == "relatorios":
        aba_relatorios(df_ok, df_mes, mes_sel, membros_db, df,
                       mes_vigente, registros_assist, pode_editar=pode_editar)

    elif aba_id == "anuncios":
        aba_anuncios(pode_editar=pode_editar)

    elif aba_id == "passagens":
        exibir_modulo_passagens(pode_editar=pode_editar)

    elif aba_id == "manutencao":
        aba_manutencao(pode_editar=pode_editar)

    elif aba_id == "configuracao":
        aba_configuracao(df, df_ok, df_mes, mes_sel, membros_db, pode_editar=pode_editar)

    # Rodapé
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 0.5rem;
        font-size:0.72rem;color:#5B7BA6;letter-spacing:0.05em;">
        v6.3 · Parque Aliança · Sistema de Gestão
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
