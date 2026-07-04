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
# =============================================================
import pandas as pd
import streamlit as st

from estilo import aplicar_estilo, get_logo_path, get_logo_base64
from autenticacao import tela_login
from database import carregar_membros, carregar_relatorios, carregar_assistencia
from utilitarios import obter_mes_vigente_str, processar_dataframe
from constantes import ABAS_SISTEMA
import permissoes

from modulo.mod_relatorios import aba_relatorios
from modulo.mod_triagem import aba_triagem
from modulo.mod_consolidado import aba_consolidado
from modulo.mod_anuncios import aba_anuncios
from modulo.mod_passagens import exibir_modulo_passagens
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
    """Barra de filtros dentro da página — substitui a antiga sidebar."""
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

    # Carregar dados
    membros_db        = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    registros_assist  = carregar_assistencia()
    df                = processar_dataframe(relatorios_brutos, membros_db)
    mes_vigente       = obter_mes_vigente_str()

    _renderizar_cabecalho()
    mes_sel = _renderizar_filtros(df, mes_vigente)

    # DataFrames derivados
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
    df_ok  = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()

    # Abas que o usuário logado pode ao menos visualizar
    abas_permitidas = permissoes.abas_visiveis()

    if not abas_permitidas:
        st.markdown("""
        <div class="pa-aviso-atencao">
        ⚠️ Seu usuário não tem acesso a nenhuma aba. Contate um administrador
        para liberar as permissões em <strong>Configuração → Usuários e Permissões</strong>.
        </div>""", unsafe_allow_html=True)
        return

    labels_abas = [f"{a['icone']}  {a['label'].upper()}" for a in abas_permitidas]
    tabs = st.tabs(labels_abas)

    for tab, aba in zip(tabs, abas_permitidas):
        aba_id      = aba["id"]
        pode_editar = permissoes.pode_editar(aba_id)

        with tab:
            if aba_id == "relatorios":
                aba_relatorios(df_ok, df_mes, mes_sel, membros_db, df, pode_editar=pode_editar)

            elif aba_id == "triagem":
                aba_triagem(df_mes, membros_db, pode_editar=pode_editar)

            elif aba_id == "consolidado":
                aba_consolidado(df, membros_db, mes_vigente, registros_assist, pode_editar=pode_editar)

            elif aba_id == "anuncios":
                aba_anuncios(pode_editar=pode_editar)

            elif aba_id == "passagens":
                exibir_modulo_passagens(pode_editar=pode_editar)

            elif aba_id == "configuracao":
                aba_configuracao(df, df_ok, df_mes, mes_sel, membros_db, pode_editar=pode_editar)

    # Rodapé
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 0.5rem;
        font-size:0.72rem;color:#9C8A46;letter-spacing:0.05em;">
        v6.0 · Parque Aliança · Sistema de Gestão
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
