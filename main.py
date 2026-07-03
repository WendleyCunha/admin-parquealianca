# =============================================================
# main.py
# PONTO DE ENTRADA DO APP — e só isso.
#
# Este arquivo era, até pouco tempo atrás, um único arquivo com
# mais de 2000 linhas (conexão com o banco, geração de PDF, CSS,
# e os seis módulos de aba, tudo junto). Foi dividido em:
#
#   estilo.py              → CSS global + logo personalizado
#   autenticacao.py         → tela de login
#   sidebar.py               → barra lateral
#   database.py              → Firestore (conexão, cache, escrita)
#   utilitarios.py           → funções auxiliares + processamento de dados
#   constantes.py            → listas compartilhadas entre módulos
#   pdf_s21.py                → geração do cartão S-21
#   modulo/mod_relatorios.py    → aba Relatórios
#   modulo/mod_triagem.py        → aba Triagem
#   modulo/mod_consolidado.py    → aba Consolidado (+ assistência)
#   modulo/mod_anuncios.py        → aba Anúncios
#   modulo/mod_passagens.py        → aba Passagens (antigo passagens.py)
#   modulo/mod_configuracao.py      → aba Configuração
#
# main.py agora só faz autenticação → carregar dados → sidebar →
# roteamento de abas. Nenhuma lógica de negócio mudou — só o lugar
# onde cada pedaço mora.
# =============================================================
import pandas as pd
import streamlit as st

from estilo import aplicar_estilo, get_logo_path
from autenticacao import tela_login
from sidebar import renderizar_sidebar
from database import carregar_membros, carregar_relatorios, carregar_assistencia
from utilitarios import obter_mes_vigente_str, processar_dataframe

from modulo.mod_relatorios import aba_relatorios
from modulo.mod_triagem import aba_triagem
from modulo.mod_consolidado import aba_consolidado
from modulo.mod_anuncios import aba_anuncios
from modulo.mod_passagens import exibir_modulo_passagens
from modulo.mod_configuracao import aba_configuracao


# =============================================================
# CONFIGURAÇÃO DA PÁGINA
# (precisa ser o primeiro comando Streamlit executado — por isso
# fica aqui no topo do main.py, e não dentro de estilo.py)
# =============================================================
st.set_page_config(
    page_title="Parque Aliança · Gestão",
    layout="wide",
    page_icon=get_logo_path() or "🏢",
    initial_sidebar_state="expanded",
)

aplicar_estilo()


# =============================================================
# PONTO DE ENTRADA PRINCIPAL
# =============================================================
def main():
    # Verificar autenticação
    if not st.session_state.get("autenticado"):
        tela_login()
        st.stop()

    # Carregar dados
    membros_db        = carregar_membros()
    relatorios_brutos = carregar_relatorios()
    registros_assist  = carregar_assistencia()
    df                = processar_dataframe(relatorios_brutos, membros_db)
    mes_vigente       = obter_mes_vigente_str()

    # Sidebar → retorna o mês selecionado
    mes_sel = renderizar_sidebar(df, mes_vigente)

    # Cabeçalho da página
    col_title, col_mes = st.columns([3, 1])
    with col_title:
        st.markdown("# Parque Aliança")
        st.markdown(
            '<p style="color:#6b7280;font-size:0.85rem;margin-top:-8px;">'
            'Sistema de Gestão · Relatórios & Publicadores</p>',
            unsafe_allow_html=True
        )
    with col_mes:
        st.markdown(f"""
        <div style="text-align:right;margin-top:12px;">
            <div class="mes-badge">
                <span class="mes-dot"></span>{mes_vigente}
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # DataFrames derivados
    df_mes = df[df['mes_referencia'] == mes_sel] if not df.empty else pd.DataFrame()
    df_ok  = df_mes[df_mes['status_validacao'] == "IDENTIFICADO"] if not df_mes.empty else pd.DataFrame()

    # Abas principais
    tabs = st.tabs([
        "📋  RELATÓRIOS",
        "⚠️  TRIAGEM",
        "📈  CONSOLIDADO",
        "📢  ANÚNCIOS",
        "🚌  PASSAGENS",
        "⚙️  CONFIGURAÇÃO",
    ])

    with tabs[0]:
        aba_relatorios(df_ok, df_mes, mes_sel, membros_db, df)

    with tabs[1]:
        aba_triagem(df_mes, membros_db)

    with tabs[2]:
        aba_consolidado(df, membros_db, mes_vigente, registros_assist)

    with tabs[3]:
        aba_anuncios()

    with tabs[4]:
        exibir_modulo_passagens()

    with tabs[5]:
        aba_configuracao(df, df_ok, df_mes, mes_sel, membros_db)

    # Rodapé
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 0.5rem;
        font-size:0.72rem;color:#374151;letter-spacing:0.05em;">
        v5.2 · Parque Aliança · Sistema de Gestão
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
