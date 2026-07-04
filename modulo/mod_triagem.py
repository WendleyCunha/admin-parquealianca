# =============================================================
# modulo/mod_triagem.py
# Aba "TRIAGEM" — relatórios que o sistema não conseguiu vincular
# automaticamente a um membro cadastrado.
#
# ATUALIZAÇÃO: removidas as cores escuras (fundo preto do card de
# sugestão, texto claro sobre fundo escuro etc.) — agora tudo usa
# a paleta clara do resto do app. Aceita pode_editar=True/False.
# =============================================================
import os
import sys

import pandas as pd
import streamlit as st

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import inicializar_db, atualizar_membro, deletar_relatorio, carregar_relatorios_cached
from utilitarios import normalizar_nome_no_banco
from constantes import categorias_lista
import permissoes
from tema import CORES


def aba_triagem(df_mes, membros_db, pode_editar=True):
    df_triagem = (df_mes[df_mes['status_validacao'] == "TRIAGEM"]
                  if not df_mes.empty else pd.DataFrame())

    if not pode_editar:
        permissoes.aviso_somente_leitura()

    if df_triagem.empty:
        st.markdown(f"""
        <div style="text-align:center;padding:3rem 1rem;">
          <div style="font-size:3rem;margin-bottom:0.5rem;">✅</div>
          <div style="font-size:1.1rem;font-weight:700;color:{CORES['sucesso']};">Tudo limpo!</div>
          <div style="color:{CORES['texto_muted']};font-size:0.85rem;margin-top:4px;">
              Nenhum relatório em triagem para este mês.</div>
        </div>""", unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div style="margin-bottom:1.5rem;">
      <div style="font-size:0.75rem;font-weight:700;color:{CORES['texto_muted2']};
          text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;">
          ⚠️ Triagem — {len(df_triagem)} item(s)
      </div>
      <div style="color:{CORES['texto_muted']};font-size:0.82rem;">
          Estes relatórios precisam de validação manual.
      </div>
    </div>""", unsafe_allow_html=True)

    nomes_db = sorted(list(membros_db.keys()))

    for _, row in df_triagem.iterrows():
        sugestao = normalizar_nome_no_banco(row['nome'], nomes_db)
        idx_sug  = nomes_db.index(sugestao) + 1 if sugestao else 0
        conf_str = "Auto-sugerido" if sugestao else "Não reconhecido"

        with st.container(border=True):
            col_info, col_badge = st.columns([4, 1])
            with col_info:
                st.markdown(f"""
                <div style="margin-bottom:8px;">
                  <span style="font-weight:700;color:{CORES['texto_principal']};font-size:0.95rem;">
                      "{row['nome']}"</span>
                  <span style="color:{CORES['texto_muted']};font-size:0.8rem;margin-left:8px;">
                      · {int(row['horas'])}h · {int(row.get('estudos_biblicos',0))} estudos</span>
                </div>""", unsafe_allow_html=True)
            with col_badge:
                st.markdown(
                    f'<span style="font-size:0.75rem;font-weight:700;color:{CORES["texto_muted2"]}">'
                    f'{conf_str}</span>', unsafe_allow_html=True)

            if sugestao:
                st.markdown(f"""
                <div style="background:{CORES['atencao_bg']};border:1px solid {CORES['atencao_borda']};border-radius:8px;
                    padding:6px 12px;margin-bottom:10px;font-size:0.8rem;color:{CORES['atencao']};">
                    💡 Sugestão: <strong>{sugestao}</strong>
                </div>""", unsafe_allow_html=True)

            if pode_editar:
                c1, c2 = st.columns(2)
                vincular = c1.selectbox(
                    "Vincular a:", ["-- Novo Membro --"] + nomes_db,
                    index=idx_sug, key=f"v_{row['id']}"
                )
                cat_v = c2.selectbox("Categoria:", categorias_lista, key=f"c_{row['id']}")

                col_confirm, col_del = st.columns([2, 1])
                with col_confirm:
                    if st.button("✔ Confirmar Vinculação", key=f"b_{row['id']}",
                                 type="primary", use_container_width=True):
                        nome_final = row['nome'] if vincular == "-- Novo Membro --" else vincular
                        atualizar_membro(nome_final, cat_v, novo=(vincular == "-- Novo Membro --"))
                        inicializar_db().collection("relatorios_parque_alianca") \
                            .document(row['id']).update({"nome": nome_final})
                        carregar_relatorios_cached.clear()
                        st.rerun()
                with col_del:
                    if st.button("🗑 Deletar", key=f"del_{row['id']}", use_container_width=True):
                        deletar_relatorio(row['id'])
