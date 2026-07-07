# =============================================================
# tabs_persistentes.py
# Substituto para st.tabs() cuja aba selecionada SOBREVIVE a
# st.rerun() — o que o st.tabs() nativo não garante.
#
# POR QUE ISSO EXISTE:
#  O st.tabs() nativo guarda qual aba está selecionada apenas no
#  componente do navegador (React), sem ligação com o
#  st.session_state do Python. Isso funciona bem enquanto o
#  usuário só clica entre abas (não há rerun "de verdade", é só
#  o componente trocando de estado no navegador).
#
#  Só que toda vez que o código chama st.rerun() — o que acontece
#  depois de qualquer ação que salva algo no banco (salvar horas,
#  atualizar um cartão, dar baixa, excluir, etc.) — o Streamlit
#  reconstrói a árvore de componentes do zero. Nesse processo, o
#  componente de abas pode perder a referência de qual aba estava
#  ativa, e o resultado é o conteúdo de TODAS as abas aparecendo
#  ao mesmo tempo na tela.
#
#  abas_persistentes() resolve isso guardando a aba ativa
#  explicitamente em st.session_state, com uma chave própria —
#  então ela sobrevive a qualquer rerun, sem exceção. Como bônus,
#  só o código da aba ativa É EXECUTADO (o st.tabs() nativo roda o
#  código de TODAS as abas a cada rerun, mesmo as escondidas) —
#  ou seja, isso também deixa o app mais rápido.
#
# COMO USAR (substituindo st.tabs()):
#
#   ANTES:
#       tabs = st.tabs(["Aba A", "Aba B", "Aba C"])
#       with tabs[0]:
#           conteudo_a()
#       with tabs[1]:
#           conteudo_b()
#       with tabs[2]:
#           conteudo_c()
#
#   DEPOIS:
#       idx = abas_persistentes(["Aba A", "Aba B", "Aba C"], key="minhas_abas")
#       if idx == 0:
#           conteudo_a()
#       elif idx == 1:
#           conteudo_b()
#       elif idx == 2:
#           conteudo_c()
#
# IMPORTANTE: cada conjunto de abas na tela precisa de uma "key"
# ÚNICA (ex: "abas_principais", "abas_manutencao", "abas_relatorios").
# Isso é o que permite ter abas dentro de abas sem elas colidirem.
# =============================================================
import streamlit as st


def abas_persistentes(labels, key):
    """
    Renderiza uma barra de abas (visualmente igual às pílulas do
    st.tabs() customizado do app) cuja seleção sobrevive a
    st.rerun(). Retorna o índice (int) da aba atualmente ativa.

    labels: lista de textos das abas (pode incluir emojis)
    key:    string única para este conjunto de abas na tela
    """
    state_key = f"_abas_persistentes_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = 0

    # Se por algum motivo o número de abas mudou (ex: permissão
    # diferente) e o índice salvo não existe mais, volta pra primeira.
    if st.session_state[state_key] >= len(labels):
        st.session_state[state_key] = 0

    cols = st.columns(len(labels), gap="small")
    for i, (col, label) in enumerate(zip(cols, labels)):
        ativa = (st.session_state[state_key] == i)
        with col:
            if st.button(
                label,
                key=f"{state_key}_btn_{i}",
                use_container_width=True,
                type="primary" if ativa else "secondary",
            ):
                if not ativa:
                    st.session_state[state_key] = i
                    st.rerun()

    st.markdown("<div style='margin-bottom:0.6rem;'></div>", unsafe_allow_html=True)
    return st.session_state[state_key]
