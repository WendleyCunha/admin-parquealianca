# =============================================================
# modulo/mod_relatorios.py
# Aba "RELATÓRIOS" — publicadores por categoria + pendências do mês.
#
# ATUALIZAÇÃO: Triagem e Consolidado agora vivem AQUI DENTRO, como
# sub-abas logo depois de "Pendências" — é o mesmo sistema/dados,
# só fazia sentido juntar. A permissão de "relatorios" (Configuração
# → Usuários e Permissões) passa a valer para as três sub-abas.
#
# Aceita pode_editar=True/False. Quando False (usuário só com
# permissão de visualização), os botões de edição ficam ocultos e
# um aviso de somente-leitura é exibido.
# =============================================================
import os
import sys

import pandas as pd
import streamlit as st
from google.cloud import firestore

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import inicializar_db, carregar_relatorios_cached, salvar_baixa_manual
from constantes import categorias_lista, meses_referencia_ordem
import permissoes
from modulo.mod_triagem import aba_triagem
from modulo.mod_consolidado import aba_consolidado


def aba_relatorios(df_ok, df_mes, mes_sel, membros_db, df, mes_vigente, registros_assistencia, pode_editar=True):
    st.markdown(f"### 📋 Relatórios de {mes_sel}")
    if not pode_editar:
        permissoes.aviso_somente_leitura()

    sub_rel = st.tabs([
        "👤 PUBLICADOR", "🌟 P. AUXILIAR", "💎 P. REGULAR", "⏳ PENDÊNCIAS",
        "⚠️ TRIAGEM", "📈 CONSOLIDADO",
    ])

    entregaram = set(df_ok['nome_oficial'].unique()) if not df_ok.empty else set()

    for i, cat in enumerate(categorias_lista):
        with sub_rel[i]:
            df_cat = df_ok[df_ok['cat_oficial'] == cat] if not df_ok.empty else pd.DataFrame()

            if df_cat.empty:
                st.info(f"Nenhum envio de {cat} em {mes_sel}.")
            else:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"""
                    <div class="pa-metric">
                      <div class="pa-metric-value">{len(df_cat)}</div>
                      <div class="pa-metric-label">Relatórios</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div class="pa-metric">
                      <div class="pa-metric-value">{int(df_cat['horas'].sum())}h</div>
                      <div class="pa-metric-label">Total de Horas</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                    <div class="pa-metric">
                      <div class="pa-metric-value">{int(df_cat['estudos_biblicos'].sum())}</div>
                      <div class="pa-metric-label">Estudos Bíblicos</div>
                    </div>""", unsafe_allow_html=True)

                st.markdown("")
                df_cat_sorted = df_cat.sort_values('nome_oficial')
                cols = st.columns(4)
                for idx, (_, r) in enumerate(df_cat_sorted.iterrows()):
                    with cols[idx % 4]:
                        st.markdown(
                            f'<div class="pa-card">'
                            f'<div class="pa-card-header">{r["nome_oficial"]}</div>'
                            f'<div class="pa-card-sub">⏱ {int(r["horas"])}h &nbsp;·&nbsp; 📚 {int(r["estudos_biblicos"])}</div>'
                            f'</div>',
                            unsafe_allow_html=True)

    with sub_rel[3]:
        idx_mes_sel = (meses_referencia_ordem.index(mes_sel)
                       if mes_sel in meses_referencia_ordem else 99)

        for cat in categorias_lista:
            pendentes = []
            for n, d_m in membros_db.items():
                inicio  = d_m.get('mes_inicio', 'SETEMBRO 2025')
                idx_ini = (meses_referencia_ordem.index(inicio)
                           if inicio in meses_referencia_ordem else 0)
                if (d_m.get('categoria') == cat
                        and n not in entregaram
                        and idx_mes_sel >= idx_ini
                        and d_m.get('status', 'Ativo') == 'Ativo'):
                    pendentes.append(n)

            pendentes = sorted(pendentes)
            if not pendentes:
                continue

            icone = '👤' if cat == 'PUBLICADOR' else ('💎' if 'AUXILIAR' in cat else '⭐')
            with st.expander(f"{icone} {cat} — {len(pendentes)} pendente(s)", expanded=False):
                if pode_editar:
                    col_btn_baixa, _ = st.columns([2, 3])
                    with col_btn_baixa:
                        if st.button(f"✔ Dar Baixa em Todos ({len(pendentes)})",
                                     key=f"baixa_all_{cat}_{mes_sel}", type="primary"):
                            db = inicializar_db()
                            if db:
                                batch = db.batch()
                                for p in pendentes:
                                    doc_ref = db.collection("relatorios_parque_alianca").document()
                                    batch.set(doc_ref, {
                                        "nome": p, "mes_referencia": mes_sel,
                                        "horas": 0, "estudos_biblicos": 0,
                                        "timestamp": firestore.SERVER_TIMESTAMP
                                    })
                                batch.commit()
                                carregar_relatorios_cached.clear()
                                st.success(f"✅ Baixa realizada para {len(pendentes)} publicadores(as)!")
                                st.rerun()

                st.markdown("---")
                for p in pendentes:
                    if pode_editar:
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
                        c1.markdown(f"**{p}**")
                        h_manual = c2.number_input("H", min_value=0, step=1,
                                                   key=f"h_man_{p}_{mes_sel}")
                        e_manual = c3.number_input("E", min_value=0, step=1,
                                                   key=f"e_man_{p}_{mes_sel}")
                        if c4.button("✔ Dar Baixa", key=f"btn_man_{p}_{mes_sel}"):
                            salvar_baixa_manual(p, mes_sel, h_manual, e_manual)
                    else:
                        st.markdown(f"- {p}")

    # ---- Sub-aba: Triagem (movida para dentro de Relatórios) ----
    with sub_rel[4]:
        aba_triagem(df_mes, membros_db, pode_editar=pode_editar)

    # ---- Sub-aba: Consolidado (movida para dentro de Relatórios) ----
    with sub_rel[5]:
        aba_consolidado(df, membros_db, mes_vigente, registros_assistencia, pode_editar=pode_editar)
