# =============================================================
# modulo/mod_manutencao.py  (NOVO)
# Aba "MANUTENÇÃO" — réplica funcional da planilha
# "Planejamento_para_consertos_no_Salao_do_Reino", com o mesmo
# catálogo de problemas por categoria, o mesmo cálculo automático
# de Gravidade/Urgência/Tendência/Prioridade (nota 1-5) e o mesmo
# teto mensal de orçamento — só que dentro do sistema, sem depender
# de abrir o Excel.
#
# Segue o padrão dos outros módulos: aceita pode_editar=True/False.
# =============================================================
import os
import sys

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

_COR_STATUS = {
    "Planejado":    "#B4952E",
    "Em andamento": "#2f7fb8",
    "Concluído":    "#2f8f52",
    "Cancelado":    "#9C8A46",
}
_COR_PRIORIDADE = {"Alta": "#c14b4b", "Média": "#B4952E", "Baixa": "#2f8f52"}


def aba_manutencao(pode_editar=True):
    st.markdown("### 🔧 Manutenção do Salão do Reino")
    st.caption("Planejamento de consertos · categorias e soluções conforme o Manual de Manutenção")

    if not pode_editar:
        permissoes.aviso_somente_leitura()

    reparos = carregar_reparos_manutencao()
    df = pd.DataFrame(reparos) if reparos else pd.DataFrame()

    labels = (["➕ Novo Reparo"] if pode_editar else []) + ["🗂️ Todos os Reparos", "📊 Painel de Orçamento"]
    tabs = st.tabs(labels)
    idx = 0

    if pode_editar:
        with tabs[0]:
            _sub_novo_reparo()
        idx = 1

    with tabs[idx]:
        _sub_todos_reparos(df, pode_editar)

    with tabs[idx + 1]:
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
    )

    col3, col4, col5 = st.columns(3)
    custo        = col3.number_input("Custo estimado (R$)", min_value=0.0, step=10.0, format="%.2f")
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
    cor_prio = _COR_PRIORIDADE.get(info_grav["prioridade"], "#8A6D14")
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
    executor = col9.text_input("Nome do executor", placeholder="Opcional")
    status   = col10.selectbox("Status", STATUS_MANUTENCAO, key="man_status")

    if st.button("💾 Salvar Reparo", type="primary", use_container_width=True):
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
def _sub_todos_reparos(df, pode_editar):
    st.markdown("#### 🗂️ Todos os reparos lançados")

    if df.empty:
        st.info("Nenhum reparo lançado ainda.")
        return

    col_f1, col_f2, col_f3 = st.columns(3)
    filtro_mes    = col_f1.selectbox("Filtrar por mês",      ["Todos"] + MESES_MANUTENCAO)
    filtro_status = col_f2.selectbox("Filtrar por status",   ["Todos"] + STATUS_MANUTENCAO)
    filtro_cat    = col_f3.selectbox("Filtrar por categoria", ["Todas"] + CATEGORIAS_MANUTENCAO)

    df_f = df.copy()
    if filtro_mes != "Todos":
        df_f = df_f[df_f.get("mes_execucao") == filtro_mes]
    if filtro_status != "Todos":
        df_f = df_f[df_f.get("status") == filtro_status]
    if filtro_cat != "Todas":
        df_f = df_f[df_f.get("categoria") == filtro_cat]

    if df_f.empty:
        st.info("Nenhum reparo encontrado com esses filtros.")
        return

    st.caption(f"{len(df_f)} reparo(s) encontrado(s)")

    for _, r in df_f.sort_values("mes_execucao").iterrows():
        cor_status = _COR_STATUS.get(r.get("status"), "#8A6D14")
        cor_prio   = _COR_PRIORIDADE.get(r.get("prioridade"), "#8A6D14")
        titulo = f"{r.get('categoria','')} — {r.get('problema','')[:60]}"
        with st.expander(titulo):
            st.markdown(f"""
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
              <span style="background:{cor_status}22;color:{cor_status};font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">{r.get('status','')}</span>
              <span style="background:{cor_prio}22;color:{cor_prio};font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">Prioridade {r.get('prioridade','')}</span>
              <span style="background:#F1EAD2;color:#6B5E3C;font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">📅 {r.get('mes_execucao','')}</span>
              <span style="background:#F1EAD2;color:#6B5E3C;font-weight:700;
                  font-size:0.72rem;padding:3px 10px;border-radius:999px;">
                  💰 R$ {float(r.get('custo_estimado', 0) or 0):,.2f}</span>
            </div>""", unsafe_allow_html=True)

            st.markdown(f"**Solução recomendada:** {r.get('solucao_recomendada','—')}")
            if r.get("observacoes"):
                st.markdown(f"**Observações:** {r.get('observacoes')}")
            st.markdown(f"**Executor:** {r.get('executor') or '—'}")
            st.caption(f"Gravidade: {r.get('gravidade','—')} · Urgência: {r.get('urgencia','—')} · "
                       f"Tendência: {r.get('tendencia','—')}")

            if pode_editar:
                st.markdown("---")
                col_e1, col_e2, col_e3 = st.columns([2, 1, 1])
                novo_status = col_e1.selectbox(
                    "Alterar status", STATUS_MANUTENCAO,
                    index=STATUS_MANUTENCAO.index(r.get("status")) if r.get("status") in STATUS_MANUTENCAO else 0,
                    key=f"st_{r['id']}",
                )
                with col_e2:
                    if st.button("💾 Salvar", key=f"save_st_{r['id']}", use_container_width=True, type="primary"):
                        salvar_reparo_manutencao({"status": novo_status}, doc_id=r["id"])
                        st.toast("✅ Status atualizado!")
                        st.rerun()
                with col_e3:
                    if st.button("🗑️ Excluir", key=f"del_{r['id']}", use_container_width=True):
                        deletar_reparo_manutencao(r["id"])
                        st.toast("🗑️ Reparo excluído.")
                        st.rerun()


# ─────────────────────────────────────────────────────────────
def _sub_painel(df, pode_editar):
    st.markdown("#### 📊 Painel de orçamento")

    teto_atual = obter_teto_mensal_manutencao()
    if pode_editar:
        col_teto, col_btn = st.columns([2, 1])
        with col_teto:
            novo_teto = st.number_input("Teto mensal de orçamento (R$)", min_value=0.0,
                                         value=float(teto_atual), step=50.0, format="%.2f")
        with col_btn:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            if st.button("💾 Salvar teto", use_container_width=True):
                salvar_teto_mensal_manutencao(novo_teto)
                st.toast("✅ Teto mensal atualizado!")
                st.rerun()
    else:
        st.markdown(f"""<div class="pa-metric" style="max-width:260px;">
            <div class="pa-metric-value">R$ {teto_atual:,.2f}</div>
            <div class="pa-metric-label">Teto mensal</div></div>""", unsafe_allow_html=True)

    if df.empty:
        st.info("Ainda não há reparos lançados para calcular o orçamento.")
        return

    df["custo_estimado"] = pd.to_numeric(df.get("custo_estimado", 0), errors="coerce").fillna(0)

    st.markdown("---")
    st.markdown("##### 💰 Custo estimado por mês x teto")
    resumo_mes = df.groupby("mes_execucao")["custo_estimado"].sum().reindex(MESES_MANUTENCAO).fillna(0)

    cols = st.columns(4)
    for i, mes in enumerate(MESES_MANUTENCAO):
        valor = resumo_mes.get(mes, 0)
        estourou = valor > teto_atual
        cor = "#c14b4b" if estourou else "#2f8f52"
        pct = min(round((valor / teto_atual) * 100), 999) if teto_atual > 0 else 0
        with cols[i % 4]:
            st.markdown(f"""
            <div class="pa-metric">
              <div class="pa-metric-label">{mes}</div>
              <div class="pa-metric-value" style="font-size:16px;color:{cor};">R$ {valor:,.0f}</div>
              <div style="font-size:0.68rem;color:#9C8A46;margin-top:2px;">{pct}% do teto</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("##### 📌 Por status")
        contagem_status = df["status"].value_counts() if "status" in df.columns else pd.Series(dtype=int)
        for status in STATUS_MANUTENCAO:
            qtd = int(contagem_status.get(status, 0))
            cor = _COR_STATUS.get(status, "#8A6D14")
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                padding:6px 0;border-bottom:1px solid #EEE3C7;">
              <span style="font-size:0.85rem;color:#1A1A1A;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                    background:{cor};margin-right:8px;"></span>{status}</span>
              <span style="font-weight:700;color:{cor};">{qtd}</span>
            </div>""", unsafe_allow_html=True)

    with col_b:
        st.markdown("##### 🚦 Por prioridade")
        contagem_prio = df["prioridade"].value_counts() if "prioridade" in df.columns else pd.Series(dtype=int)
        for prio in ["Alta", "Média", "Baixa"]:
            qtd = int(contagem_prio.get(prio, 0))
            cor = _COR_PRIORIDADE.get(prio, "#8A6D14")
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                padding:6px 0;border-bottom:1px solid #EEE3C7;">
              <span style="font-size:0.85rem;color:#1A1A1A;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                    background:{cor};margin-right:8px;"></span>{prio}</span>
              <span style="font-weight:700;color:{cor};">{qtd}</span>
            </div>""", unsafe_allow_html=True)

    pendentes_alta = df[(df.get("prioridade") == "Alta") & (df.get("status").isin(["Planejado", "Em andamento"]))]
    if not pendentes_alta.empty:
        st.markdown("---")
        st.markdown("##### 🔴 Prioridade alta ainda pendente")
        for _, r in pendentes_alta.iterrows():
            st.markdown(f"""
            <div class="pa-aviso-erro" style="margin-bottom:6px;">
              <strong>{r.get('categoria','')}</strong> — {r.get('problema','')[:80]}
              &nbsp;·&nbsp; {r.get('mes_execucao','')}
            </div>""", unsafe_allow_html=True)
