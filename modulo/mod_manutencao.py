# =============================================================
# modulo/mod_manutencao.py
# Aba "MANUTENÇÃO" — réplica funcional da planilha
# "Planejamento_para_consertos_no_Salao_do_Reino".
#
# ATUALIZAÇÃO:
#  - "Todos os Reparos" virou duas sub-abas: 🗂️ Pendentes (Planejado
#    + Em andamento) e ✅ Finalizados (Concluído + Cancelado).
#  - Pendentes agora tem EDIÇÃO COMPLETA (todos os campos), não só
#    status — sempre condicionada a pode_editar (perfil definido em
#    Configuração → Usuários e Permissões).
#  - Painel de Orçamento ganhou gráficos (Altair, já vem junto do
#    Streamlit, não precisa instalar nada): barras de custo mensal
#    com a linha do teto, barras de status e barras empilhadas de
#    prioridade por mês — no mesmo espírito do painel da planilha.
#
# CORREÇÃO (v1.1):
#  - O campo "Custo estimado (R$)" em Novo Reparo não aparecia na
#    tela (rótulo era exibido, mas a caixa de input, não). Era o
#    único widget desta tela sem "key" explícita — nos demais
#    (categoria, problema, mês, status, etc.) sempre foi usado
#    key=... Sem key, a identidade do widget fica presa à posição
#    dele na árvore de elementos; como esta tela vive dentro de
#    sub-abas cuja lista muda dinamicamente conforme a permissão
#    do usuário (pode_editar), essa posição varia entre execuções
#    e o Streamlit deixa de montar o widget, sem lançar erro.
# CORREÇÃO (v1.2):
#  - As sub-abas desta tela (Novo Reparo/Pendentes/Finalizados/Painel)
#    usavam st.tabs(), que perde a aba selecionada sempre que uma ação
#    chama st.rerun() — e aqui quase toda ação chama (salvar, excluir,
#    mudar status). O sintoma era: depois de salvar algo, a tela
#    "jogava" o conteúdo de todas as sub-abas na tela ao mesmo tempo.
#    Trocado por abas_persistentes() (tabs_persistentes.py), que guarda
#    a aba ativa em st.session_state — sobrevive a qualquer rerun.
# =============================================================
import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import (
    carregar_reparos_manutencao, salvar_reparo_manutencao, deletar_reparo_manutencao,
    obter_teto_mensal_manutencao, salvar_teto_mensal_manutencao,
)
from catalogo_manutencao import (
    CATEGORIAS_MANUTENCAO, TABELA_GRAVIDADE, MESES_MANUTENCAO, STATUS_MANUTENCAO,
    problemas_da_categoria, buscar_problema,
)
import permissoes
from tema import CORES
from tabs_persistentes import abas_persistentes

_COR_STATUS = {
    "Planejado":    "#64748B",
    "Em andamento": CORES["primaria"],
    "Concluído":    CORES["sucesso"],
    "Cancelado":    "#9AA5B1",
}
_COR_PRIORIDADE = {"Alta": CORES["erro"], "Média": "#e0b23c", "Baixa": CORES["sucesso"]}
_STATUS_PENDENTES    = ["Planejado", "Em andamento"]
_STATUS_FINALIZADOS  = ["Concluído", "Cancelado"]


def aba_manutencao(pode_editar=True):
    st.markdown("### 🔧 Manutenção do Salão do Reino")
    st.caption("Planejamento de consertos · categorias e soluções conforme o Manual de Manutenção")

    if not pode_editar:
        permissoes.aviso_somente_leitura()

    reparos = carregar_reparos_manutencao()
    df = pd.DataFrame(reparos) if reparos else pd.DataFrame()

    labels = (["➕ Novo Reparo"] if pode_editar else []) + [
        "🗂️ Pendentes", "✅ Finalizados", "📊 Painel de Orçamento",
    ]
    idx_ativa = abas_persistentes(labels, key="abas_manutencao")
    idx = 0

    if pode_editar:
        if idx_ativa == 0:
            _sub_novo_reparo()
        idx = 1

    df_pend = df[df["status"].isin(_STATUS_PENDENTES)] if not df.empty and "status" in df.columns else pd.DataFrame()
    df_fin  = df[df["status"].isin(_STATUS_FINALIZADOS)] if not df.empty and "status" in df.columns else pd.DataFrame()

    if idx_ativa == idx:
        _sub_lista_reparos(df_pend, pode_editar, prefixo="pend",
                            vazio_msg="Nenhum reparo pendente no momento. 🎉")

    elif idx_ativa == idx + 1:
        _sub_lista_reparos(df_fin, pode_editar, prefixo="fin",
                            vazio_msg="Nenhum reparo finalizado ainda.", permitir_editar_campos=False)

    elif idx_ativa == idx + 2:
        _sub_painel(df, pode_editar)


# ─────────────────────────────────────────────────────────────
def _sub_novo_reparo():
    st.markdown("#### ➕ Lançar novo problema")

    col1, col2 = st.columns(2)
    categoria = col1.selectbox("Categoria", CATEGORIAS_MANUTENCAO, key="man_cat")

    problemas_cat = problemas_da_categoria(categoria)
    opcoes_problema = [p["problema"] for p in problemas_cat]
    problema_sel = col2.selectbox("Problema", opcoes_problema, key="man_prob")

    info = buscar_problema(categoria, problema_sel)
    risco_padrao   = info["risco"] if info else 1
    solucao_padrao = info["solucao"] if info else ""
    eh_outro       = str(problema_sel).lower().startswith("outro problema")

    st.markdown(f"""
    <div class="pa-aviso-neutro">💡 <strong>Solução recomendada:</strong> {solucao_padrao}</div>
    """, unsafe_allow_html=True)

    observacoes = st.text_area(
        "Observações adicionais" + (" *" if eh_outro else ""),
        placeholder="Detalhe o problema específico encontrado no salão"
                     + (" (obrigatório para itens 'Outro Problema...')" if eh_outro else ""),
        key="man_obs",
    )

    col3, col4, col5 = st.columns(3)
    # CORREÇÃO: key + value explícitos — era o único campo desta tela
    # sem "key", e por isso deixava de ser renderizado (ver nota no
    # topo do arquivo). Esse valor é o que alimenta o Painel de
    # Orçamento (KPIs e gráfico de custo mensal x teto).
    custo = col3.number_input(
        "Custo estimado (R$)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        format="%.2f",
        key="man_custo",
        help="Valor estimado do reparo, em reais. Alimenta o Painel de Orçamento.",
    )
    risco_alto   = col4.radio("Trabalho de alto risco? (DC-82)", ["Não", "Sim"], horizontal=True, key="man_risco_alto")
    consultar_tm = col5.radio("Precisa consultar o TM?",         ["Não", "Sim"], horizontal=True, key="man_tm")

    st.markdown("---")
    col6, col7 = st.columns([1, 2])
    with col6:
        nota_gravidade = st.select_slider(
            "Nota de gravidade (1 a 5)", options=[1, 2, 3, 4, 5],
            value=risco_padrao if risco_padrao in (1, 2, 3, 4, 5) else 1,
            key="man_nota",
        )
    info_grav = TABELA_GRAVIDADE[nota_gravidade]
    cor_prio = _COR_PRIORIDADE.get(info_grav["prioridade"], CORES["primaria_escura"])
    with col7:
        st.markdown(f"""
        <div class="pa-card" style="margin-top:0;">
          <div class="pa-card-header">{info_grav['gravidade']}</div>
          <div class="pa-card-sub">⏱ {info_grav['urgencia']} &nbsp;·&nbsp; 📈 {info_grav['tendencia']}</div>
          <div style="margin-top:6px;">
            <span style="background:{cor_prio}22;color:{cor_prio};font-weight:800;
                font-size:0.72rem;padding:3px 10px;border-radius:999px;
                text-transform:uppercase;letter-spacing:0.05em;">
                Prioridade {info_grav['prioridade']}</span>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    col8, col9, col10 = st.columns(3)
    mes_exec = col8.selectbox("Mês de execução", MESES_MANUTENCAO, key="man_mes")
    executor = col9.text_input("Nome do executor", placeholder="Opcional", key="man_executor")
    status   = col10.selectbox("Status", STATUS_MANUTENCAO, key="man_status")

    if st.button("💾 Salvar Reparo", type="primary", use_container_width=True, key="man_salvar_btn"):
        if eh_outro and not observacoes.strip():
            st.error("Para 'Outro Problema', descreva nas observações adicionais.")
        else:
            dados = {
                "categoria":            categoria,
                "problema":             problema_sel,
                "solucao_recomendada":  solucao_padrao,
                "observacoes":          observacoes.strip(),
                "custo_estimado":       float(custo),
                "risco_alto":           (risco_alto == "Sim"),
                "consultar_tm":         (consultar_tm == "Sim"),
                "risco":                nota_gravidade,
                "gravidade":            info_grav["gravidade"],
                "urgencia":             info_grav["urgencia"],
                "tendencia":            info_grav["tendencia"],
                "prioridade":           info_grav["prioridade"],
                "mes_execucao":         mes_exec,
                "executor":             executor.strip(),
                "status":               status,
            }
            salvar_reparo_manutencao(dados)
            st.success("✅ Reparo lançado com sucesso!")
            st.rerun()


# ─────────────────────────────────────────────────────────────
def _sub_lista_reparos(df, pode_editar, prefixo, vazio_msg, permitir_editar_campos=True):
    """
    Lista de reparos com filtros. Quando pode_editar=True e
    permitir_editar_campos=True (aba de Pendentes), mostra o
    formulário de edição completo, além de trocar status e excluir.
    Na aba de Finalizados, mesmo com pode_editar=True, só se pode
    reabrir (mudar status) ou excluir — não faz sentido reeditar
    detalhes de um reparo já concluído.
    """
    if df.empty:
        st.info(vazio_msg)
        return

    col_f1, col_f2 = st.columns(2)
    filtro_mes = col_f1.selectbox("Filtrar por mês", ["Todos"] + MESES_MANUTENCAO, key=f"fmes_{prefixo}")
    filtro_cat = col_f2.selectbox("Filtrar por categoria", ["Todas"] + CATEGORIAS_MANUTENCAO, key=f"fcat_{prefixo}")

    df_f = df.copy()
    if filtro_mes != "Todos":
        df_f = df_f[df_f.get("mes_execucao") == filtro_mes]
    if filtro_cat != "Todas":
        df_f = df_f[df_f.get("categoria") == filtro_cat]

    if df_f.empty:
        st.info("Nenhum reparo encontrado com esses filtros.")
        return

    st.caption(f"{len(df_f)} reparo(s) encontrado(s)")

    for _, r in df_f.sort_values("mes_execucao").iterrows():
        cor_status = _COR_STATUS.get(r.get("status"), CORES["primaria_escura"])
        cor_prio   = _COR_PRIORIDADE.get(r.get("prioridade"), CORES["primaria_escura"])
        titulo = f"{r.get('categoria','')} — {str(r.get('problema',''))[:60]}"

        with st.expander(titulo):
            st.markdown(f"""
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
              <span style="background:{cor_status}22;color:{cor_status};font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">{r.get('status','')}</span>
              <span style="background:{cor_prio}22;color:{cor_prio};font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">Prioridade {r.get('prioridade','')}</span>
              <span style="background:{CORES['primaria_clara']};color:{CORES['texto_muted2']};font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">📅 {r.get('mes_execucao','')}</span>
              <span style="background:{CORES['primaria_clara']};color:{CORES['texto_muted2']};font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">
                  💰 R$ {float(r.get('custo_estimado', 0) or 0):,.2f}</span>
            </div>""", unsafe_allow_html=True)

            if not pode_editar:
                st.markdown(f"**Solução recomendada:** {r.get('solucao_recomendada','—')}")
                if r.get("observacoes"):
                    st.markdown(f"**Observações:** {r.get('observacoes')}")
                st.markdown(f"**Executor:** {r.get('executor') or '—'}")
                st.caption(f"Gravidade: {r.get('gravidade','—')} · Urgência: {r.get('urgencia','—')} · "
                           f"Tendência: {r.get('tendencia','—')}")
                continue

            # ---- MODO EDIÇÃO (só chega aqui se pode_editar=True) ----
            if permitir_editar_campos:
                _formulario_edicao_completo(r, prefixo)
            else:
                # Finalizados: só reabrir (status) ou excluir, sem reeditar detalhes.
                st.markdown(f"**Solução recomendada:** {r.get('solucao_recomendada','—')}")
                if r.get("observacoes"):
                    st.markdown(f"**Observações:** {r.get('observacoes')}")
                st.markdown(f"**Executor:** {r.get('executor') or '—'}")
                col_e1, col_e2, col_e3 = st.columns([2, 1, 1])
                novo_status = col_e1.selectbox(
                    "Status", STATUS_MANUTENCAO,
                    index=STATUS_MANUTENCAO.index(r.get("status")) if r.get("status") in STATUS_MANUTENCAO else 0,
                    key=f"st_{prefixo}_{r['id']}",
                )
                with col_e2:
                    if st.button("💾 Salvar", key=f"savest_{prefixo}_{r['id']}",
                                 use_container_width=True, type="primary"):
                        salvar_reparo_manutencao({"status": novo_status}, doc_id=r["id"])
                        st.toast("✅ Status atualizado!")
                        st.rerun()
                with col_e3:
                    if st.button("🗑️ Excluir", key=f"del_{prefixo}_{r['id']}", use_container_width=True):
                        deletar_reparo_manutencao(r["id"])
                        st.toast("🗑️ Reparo excluído.")
                        st.rerun()


def _formulario_edicao_completo(r, prefixo):
    """Formulário com TODOS os campos editáveis — usado na aba Pendentes."""
    rid = r["id"]

    col1, col2 = st.columns(2)
    cat_atual = r.get("categoria")
    categoria_edit = col1.selectbox(
        "Categoria", CATEGORIAS_MANUTENCAO,
        index=CATEGORIAS_MANUTENCAO.index(cat_atual) if cat_atual in CATEGORIAS_MANUTENCAO else 0,
        key=f"cat_edit_{prefixo}_{rid}",
    )
    opcoes_problema = [p["problema"] for p in problemas_da_categoria(categoria_edit)]
    prob_atual = r.get("problema")
    problema_edit = col2.selectbox(
        "Problema", opcoes_problema,
        index=opcoes_problema.index(prob_atual) if prob_atual in opcoes_problema else 0,
        key=f"prob_edit_{prefixo}_{rid}",
    )

    info_atual = buscar_problema(categoria_edit, problema_edit)
    solucao_atual = info_atual["solucao"] if info_atual else r.get("solucao_recomendada", "")
    st.markdown(f"""<div class="pa-aviso-neutro">💡 <strong>Solução recomendada:</strong> {solucao_atual}</div>""",
                unsafe_allow_html=True)

    observacoes_edit = st.text_area("Observações adicionais", value=r.get("observacoes", ""),
                                     key=f"obs_edit_{prefixo}_{rid}")

    col3, col4, col5 = st.columns(3)
    custo_edit = col3.number_input("Custo estimado (R$)", min_value=0.0, step=10.0, format="%.2f",
                                    value=float(r.get("custo_estimado", 0) or 0), key=f"custo_edit_{prefixo}_{rid}")
    risco_alto_edit = col4.radio("Trabalho de alto risco?", ["Não", "Sim"], horizontal=True,
                                  index=1 if r.get("risco_alto") else 0, key=f"ra_edit_{prefixo}_{rid}")
    consultar_tm_edit = col5.radio("Precisa consultar o TM?", ["Não", "Sim"], horizontal=True,
                                    index=1 if r.get("consultar_tm") else 0, key=f"tm_edit_{prefixo}_{rid}")

    nota_atual = r.get("risco", 1) if r.get("risco") in (1, 2, 3, 4, 5) else 1
    nota_edit = st.select_slider("Nota de gravidade (1 a 5)", options=[1, 2, 3, 4, 5],
                                  value=nota_atual, key=f"nota_edit_{prefixo}_{rid}")
    info_grav_edit = TABELA_GRAVIDADE[nota_edit]
    cor_prio_edit = _COR_PRIORIDADE.get(info_grav_edit["prioridade"], CORES["primaria_escura"])
    st.markdown(f"""
    <div style="font-size:0.82rem;color:#6B6B6B;margin:4px 0 10px;">
      {info_grav_edit['gravidade']} · {info_grav_edit['urgencia']} · {info_grav_edit['tendencia']} ·
      <span style="color:{cor_prio_edit};font-weight:700;">Prioridade {info_grav_edit['prioridade']}</span>
    </div>""", unsafe_allow_html=True)

    col6, col7, col8 = st.columns(3)
    mes_atual = r.get("mes_execucao")
    mes_edit = col6.selectbox("Mês de execução", MESES_MANUTENCAO,
                               index=MESES_MANUTENCAO.index(mes_atual) if mes_atual in MESES_MANUTENCAO else 0,
                               key=f"mes_edit_{prefixo}_{rid}")
    executor_edit = col7.text_input("Nome do executor", value=r.get("executor", ""), key=f"exec_edit_{prefixo}_{rid}")
    status_atual = r.get("status")
    status_edit = col8.selectbox("Status", STATUS_MANUTENCAO,
                                  index=STATUS_MANUTENCAO.index(status_atual) if status_atual in STATUS_MANUTENCAO else 0,
                                  key=f"status_edit_{prefixo}_{rid}")

    col_save, col_del = st.columns([3, 1])
    with col_save:
        if st.button("💾 Salvar alterações", key=f"savefull_{prefixo}_{rid}",
                     type="primary", use_container_width=True):
            dados = {
                "categoria":           categoria_edit,
                "problema":            problema_edit,
                "solucao_recomendada": solucao_atual,
                "observacoes":         observacoes_edit.strip(),
                "custo_estimado":      float(custo_edit),
                "risco_alto":          (risco_alto_edit == "Sim"),
                "consultar_tm":        (consultar_tm_edit == "Sim"),
                "risco":               nota_edit,
                "gravidade":           info_grav_edit["gravidade"],
                "urgencia":            info_grav_edit["urgencia"],
                "tendencia":           info_grav_edit["tendencia"],
                "prioridade":          info_grav_edit["prioridade"],
                "mes_execucao":        mes_edit,
                "executor":            executor_edit.strip(),
                "status":              status_edit,
            }
            salvar_reparo_manutencao(dados, doc_id=rid)
            st.toast("✅ Reparo atualizado!")
            st.rerun()
    with col_del:
        if st.button("🗑️ Excluir", key=f"delfull_{prefixo}_{rid}", use_container_width=True):
            deletar_reparo_manutencao(rid)
            st.toast("🗑️ Reparo excluído.")
            st.rerun()


# ─────────────────────────────────────────────────────────────
# Painel de orçamento — KPIs + gráficos
# ─────────────────────────────────────────────────────────────
def _grafico_custo_mensal(df, teto):
    df_mes = df.groupby("mes_execucao")["custo_estimado"].sum().reindex(MESES_MANUTENCAO).fillna(0).reset_index()
    df_mes.columns = ["mes", "custo"]

    barras = alt.Chart(df_mes).mark_bar(color=CORES["primaria"], cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("mes:N", sort=MESES_MANUTENCAO, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("custo:Q", title="Custo estimado (R$)"),
        tooltip=[alt.Tooltip("mes:N", title="Mês"), alt.Tooltip("custo:Q", title="Custo (R$)", format=",.2f")],
    )
    rotulos = barras.mark_text(dy=-8, color=CORES['texto_muted2'], fontSize=10).encode(
        text=alt.Text("custo:Q", format=",.0f")
    )
    linha_teto = alt.Chart(pd.DataFrame({"teto": [teto]})).mark_rule(
        color="#c14b4b", strokeDash=[5, 4], size=2
    ).encode(y="teto:Q")

    st.altair_chart((barras + rotulos + linha_teto).properties(height=280), use_container_width=True)
    st.caption("🔴 linha tracejada = teto mensal")


def _grafico_status(df):
    contagem = df["status"].value_counts().reindex(STATUS_MANUTENCAO).fillna(0).reset_index()
    contagem.columns = ["status", "quantidade"]
    chart = alt.Chart(contagem).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        x=alt.X("quantidade:Q", title=None),
        y=alt.Y("status:N", sort=STATUS_MANUTENCAO, title=None),
        color=alt.Color("status:N",
                         scale=alt.Scale(domain=STATUS_MANUTENCAO,
                                          range=[_COR_STATUS[s] for s in STATUS_MANUTENCAO]),
                         legend=None),
        tooltip=["status", "quantidade"],
    ).properties(height=180)
    st.altair_chart(chart, use_container_width=True)


def _grafico_prioridade_mes(df):
    base = (df[df["prioridade"].notna()]
            .groupby(["mes_execucao", "prioridade"]).size().reset_index(name="quantidade"))
    if base.empty:
        st.caption("Sem dados suficientes para este gráfico ainda.")
        return
    chart = alt.Chart(base).mark_bar().encode(
        x=alt.X("mes_execucao:N", sort=MESES_MANUTENCAO, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("quantidade:Q", title="Qtd. de reparos"),
        color=alt.Color("prioridade:N",
                         scale=alt.Scale(domain=["Alta", "Média", "Baixa"],
                                          range=[_COR_PRIORIDADE["Alta"], _COR_PRIORIDADE["Média"], _COR_PRIORIDADE["Baixa"]]),
                         title="Prioridade"),
        tooltip=["mes_execucao", "prioridade", "quantidade"],
    ).properties(height=280)
    st.altair_chart(chart, use_container_width=True)


def _sub_painel(df, pode_editar):
    st.markdown("#### 📊 Painel de orçamento")

    teto_atual = obter_teto_mensal_manutencao()
    if pode_editar:
        col_teto, col_btn = st.columns([2, 1])
        with col_teto:
            novo_teto = st.number_input("Teto mensal de orçamento (R$)", min_value=0.0,
                                         value=float(teto_atual), step=50.0, format="%.2f",
                                         key="man_teto_mensal")
        with col_btn:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 Salvar teto", use_container_width=True, key="man_salvar_teto_btn"):
                salvar_teto_mensal_manutencao(novo_teto)
                st.toast("✅ Teto mensal atualizado!")
                st.rerun()

    if df.empty:
        st.info("Ainda não há reparos lançados para calcular o orçamento.")
        return

    df = df.copy()
    df["custo_estimado"] = pd.to_numeric(df.get("custo_estimado", 0), errors="coerce").fillna(0)

    total_custos    = df["custo_estimado"].sum()
    consertos_total = len(df)
    comunicados_tm  = int(df.get("consultar_tm", pd.Series(dtype=bool)).sum()) if "consultar_tm" in df.columns else 0

    st.markdown("---")
    k1, k2, k3, k4, k5 = st.columns(5)
    for col, label, valor in [
        (k1, "Previsão mensal", f"R$ {teto_atual:,.0f}"),
        (k2, "Previsão anual",  f"R$ {teto_atual*12:,.0f}"),
        (k3, "Total dos custos", f"R$ {total_custos:,.0f}"),
        (k4, "Consertos lançados", str(consertos_total)),
        (k5, "Comunicados ao TM", str(comunicados_tm)),
    ]:
        col.markdown(f"""<div class="pa-metric">
            <div class="pa-metric-value" style="font-size:18px;">{valor}</div>
            <div class="pa-metric-label">{label}</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 💰 Custo mensal estimado x teto")
    _grafico_custo_mensal(df, teto_atual)

    st.markdown("---")
    col_a, col_b = st.columns([1, 1.6])
    with col_a:
        st.markdown("##### 📌 Status dos consertos")
        _grafico_status(df)
    with col_b:
        st.markdown("##### 🚦 Reparos por mês, por prioridade")
        _grafico_prioridade_mes(df)

    pendentes_alta = df[(df.get("prioridade") == "Alta") & (df.get("status").isin(_STATUS_PENDENTES))]
    if not pendentes_alta.empty:
        st.markdown("---")
        st.markdown("##### 🔴 Prioridade alta ainda pendente")
        for _, r in pendentes_alta.iterrows():
            st.markdown(f"""
            <div class="pa-aviso-erro" style="margin-bottom:6px;">
              <strong>{r.get('categoria','')}</strong> — {str(r.get('problema',''))[:80]}
              &nbsp;·&nbsp; {r.get('mes_execucao','')}
            </div>""", unsafe_allow_html=True)
