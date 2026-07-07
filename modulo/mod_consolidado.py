# =============================================================
# modulo/mod_consolidado.py
# Aba "CONSOLIDADO" — histórico individual (cartão S-21) e resumo
# por categoria.
#
# ATUALIZAÇÃO: aceita pode_editar=True/False.
#
# ATUALIZAÇÃO (v1.1) — CORREÇÃO DO SUMIÇO DOS CAMPOS DE ASSISTÊNCIA:
#  - A sub-aba "🏛️ Registro de Assistência" foi REMOVIDA daqui e
#    promovida para uma sub-aba direta de Relatórios (mod_relatorios.py),
#    no mesmo nível de Triagem/Consolidado. O motivo: com ela aqui
#    dentro, o formulário ficava 3 níveis de abas aninhadas abaixo
#    da tela principal (Relatórios > Consolidado > Assistência), e
#    nessa profundidade os campos number_input do formulário
#    deixavam de renderizar (limitação conhecida do Streamlit com
#    abas/colunas aninhadas demais). Um nível a menos resolve.
#  - O parâmetro registros_assistencia continua aceito por
#    compatibilidade com quem chama esta função, mas não é mais
#    usado aqui (a sub-aba que o usava foi movida).
# =============================================================
import io
import os
import sys
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from utilitarios import ordenar_df_por_mes
from constantes import categorias_lista
from pdf_s21 import gerar_pdf_padrao_s21


def aba_consolidado(df, membros_db, mes_vigente, registros_assistencia, pode_editar=True):
    c1_tab, c2_tab = st.tabs([
        "👤 INDIVIDUAL (HISTÓRICO)",
        "📊 POR CATEGORIA",
    ])

    # ---- Sub-aba 1: Individual ----
    with c1_tab:
        membros_ord = sorted(list(membros_db.keys()))
        publicador  = st.selectbox("Publicador", membros_ord)

        st.markdown("---")
        st.markdown("#### 📦 Exportar Todos os Cartões S-21")
        st.caption("Gera um ZIP com o cartão histórico completo de **todos** os membros.")

        if st.button("⚙️ Preparar ZIP — Todos os Cartões", use_container_width=True):
            if df.empty:
                st.warning("Nenhum relatório encontrado.")
                st.session_state.pop("zip_todos_cartoes", None)
            else:
                prog = st.progress(0, text="Iniciando...")
                membros_lista = sorted(membros_db.keys())
                buf_all = io.BytesIO()
                count_ok = 0
                total_m  = len(membros_lista)

                with zipfile.ZipFile(buf_all, "w", compression=zipfile.ZIP_DEFLATED) as zf_all:
                    for i, nome_m in enumerate(membros_lista):
                        prog.progress((i + 1) / total_m, text=f"{nome_m} ({i+1}/{total_m})")
                        df_hist_m = df[
                            (df['nome_oficial'] == nome_m) &
                            (df['status_validacao'] == "IDENTIFICADO")
                        ]
                        if df_hist_m.empty:
                            continue
                        df_hist_m = ordenar_df_por_mes(df_hist_m)
                        mi_m  = membros_db.get(nome_m, {})
                        pdf_m = gerar_pdf_padrao_s21(
                            nome_m, mi_m.get('categoria', 'PUBLICADOR'),
                            df_hist_m, membro_info=mi_m
                        )
                        if pdf_m:
                            nome_arq = "".join(
                                c for c in nome_m if c.isalnum() or c in (' ', '_', '-')
                            ).strip().replace(' ', '_')
                            zf_all.writestr(f"S21_{nome_arq}.pdf", pdf_m)
                            count_ok += 1

                prog.empty()
                if count_ok:
                    st.session_state["zip_todos_cartoes"] = buf_all.getvalue()
                    st.session_state["zip_todos_nome"]    = f"S21_Todos_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                    st.session_state["zip_todos_count"]   = count_ok
                    st.success(f"✅ {count_ok} cartões prontos!")
                else:
                    st.warning("Nenhum PDF gerado.")
                    st.session_state.pop("zip_todos_cartoes", None)

        if "zip_todos_cartoes" in st.session_state:
            st.download_button(
                f"📥 Baixar ZIP ({st.session_state.get('zip_todos_count','?')} cartões)",
                data=st.session_state["zip_todos_cartoes"],
                file_name=st.session_state.get("zip_todos_nome", "S21_Todos.zip"),
                mime="application/zip",
                use_container_width=True,
                type="primary",
            )

        st.markdown("---")
        st.markdown("#### 👤 Cartão Individual")

        if publicador:
            df_hist = df[
                (df['nome_oficial'] == publicador) &
                (df['status_validacao'] == "IDENTIFICADO")
            ] if not df.empty else pd.DataFrame()

            if not df_hist.empty:
                df_hist = ordenar_df_por_mes(df_hist)
                st.dataframe(
                    df_hist[['mes_referencia', 'horas', 'estudos_biblicos']].rename(columns={
                        'mes_referencia': 'Mês', 'horas': 'Horas', 'estudos_biblicos': 'Estudos'
                    }),
                    use_container_width=True, hide_index=True,
                )
                pdf = gerar_pdf_padrao_s21(
                    publicador, membros_db[publicador].get('categoria'),
                    df_hist, membro_info=membros_db[publicador]
                )
                if pdf:
                    st.download_button(
                        "📥 Baixar Cartão S-21", pdf, f"S21_{publicador}.pdf",
                        use_container_width=True,
                    )
            else:
                st.info("Nenhum relatório identificado para este publicador.")

    # ---- Sub-aba 2: Por Categoria ----
    with c2_tab:
        cat_sel = st.selectbox("Categoria", categorias_lista)
        df_cons = df[
            (df['status_validacao'] == "IDENTIFICADO") &
            (df['cat_oficial'] == cat_sel)
        ] if not df.empty else pd.DataFrame()

        if not df_cons.empty:
            resumo = df_cons.groupby('mes_referencia').agg(
                total_relatorios=('id',              'count'),
                total_horas     =('horas',           'sum'),
                total_estudos   =('estudos_biblicos', 'sum'),
            ).reset_index()

            resumo_ord = ordenar_df_por_mes(resumo)

            def obs_col(row):
                if row['mes_referencia'] == mes_vigente:
                    return f"📌 {int(row['total_relatorios'])} relatórios entregues"
                return ""
            resumo_ord['observacao'] = resumo_ord.apply(obs_col, axis=1)

            st.dataframe(
                resumo_ord.rename(columns={
                    'mes_referencia':  'Mês', 'total_relatorios': 'Relatórios',
                    'total_horas':     'Total Horas', 'total_estudos': 'Total Estudos',
                    'observacao':      'Observação',
                }),
                use_container_width=True, hide_index=True,
            )

            df_pdf_consolidado = resumo_ord[['mes_referencia','total_relatorios','total_horas','total_estudos']].copy()
            df_pdf_consolidado = df_pdf_consolidado.rename(columns={
                'total_horas': 'horas', 'total_estudos': 'estudos_biblicos',
            })
            df_pdf_consolidado['observacoes'] = df_pdf_consolidado['total_relatorios'].apply(
                lambda n: f"{int(n)} relat."
            )
            df_pdf_consolidado['cat_oficial'] = cat_sel

            pdf_c = gerar_pdf_padrao_s21(f"CONSOLIDADO {cat_sel}", cat_sel, df_pdf_consolidado)
            if pdf_c:
                st.download_button(
                    f"📥 Baixar Cartão Consolidado — {cat_sel}",
                    pdf_c, f"S21_Consolidado_{cat_sel}.pdf",
                    use_container_width=True,
                )
        else:
            st.info("Sem dados para esta categoria.")
