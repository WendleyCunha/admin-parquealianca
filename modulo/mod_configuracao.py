# =============================================================
# modulo/mod_configuracao.py
# Aba "CONFIGURAÇÃO" — editar relatórios do mês, gerenciar membros
# (ativos/inativos) e cadastrar novo membro.
#
# Origem: Seção 17 ("ABA: CONFIGURAÇÃO") do antigo main.py monolítico.
# =============================================================
import os
import sys

import streamlit as st

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import inicializar_db, atualizar_membro, deletar_relatorio, deletar_membro, carregar_relatorios_cached
from utilitarios import cargos_para_lista
from constantes import categorias_lista, _GENEROS, _CLASSES, _STATUS_OPCOES, _CARGOS_LISTA


def aba_configuracao(df, df_ok, df_mes, mes_sel, membros_db):
    sub_cfg = st.tabs(["✏️ EDITAR RELATÓRIOS", "👥 GERENCIAR MEMBROS", "➕ NOVO MEMBRO"])

    # ---- Sub-aba: Editar Relatórios ----
    with sub_cfg[0]:
        st.markdown(f"#### Relatórios Identificados — {mes_sel}")
        if not df.empty:
            df_ok_mes = df[
                (df['mes_referencia'] == mes_sel) &
                (df['status_validacao'] == "IDENTIFICADO")
            ]
            if df_ok_mes.empty:
                st.info("Nenhum relatório identificado neste mês.")
            else:
                for _, r in df_ok_mes.sort_values('nome_oficial').iterrows():
                    with st.expander(f"📝 {r['nome_oficial']} — {int(r['horas'])}h"):
                        ce1, ce2, ce3 = st.columns([2, 1, 1])
                        idx_cat = (categorias_lista.index(r['cat_oficial'])
                                   if r['cat_oficial'] in categorias_lista else 0)
                        nova_cat = ce1.selectbox("Categoria", categorias_lista,
                                                  index=idx_cat, key=f"e_c_{r['id']}")
                        novas_h  = ce2.number_input("Horas",   value=int(r['horas']),
                                                    key=f"e_h_{r['id']}")
                        novos_e  = ce3.number_input("Estudos", value=int(r['estudos_biblicos']),
                                                    key=f"e_e_{r['id']}")

                        col_save, col_del = st.columns(2)
                        with col_save:
                            if st.button("💾 Salvar", key=f"s_b_{r['id']}",
                                         type="primary", use_container_width=True):
                                try:
                                    inicializar_db().collection("relatorios_parque_alianca") \
                                        .document(r['id']).update({
                                            "horas": novas_h, "estudos_biblicos": novos_e,
                                            "categoria_mes": nova_cat,
                                        })
                                    carregar_relatorios_cached.clear()
                                    st.toast("💾 Alterações salvas com sucesso para este mês!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar alterações: {e}")

                        with col_del:
                            with st.popover("🗑️ Deletar", use_container_width=True):
                                st.error("Atenção! Ação irreversível.")
                                st.write(f"Deseja apagar definitivamente o relatório de "
                                         f"**{r['nome_oficial']}** deste mês?")
                                if st.button("Sim, Excluir", key=f"conf_del_{r['id']}",
                                             type="primary", use_container_width=True):
                                    deletar_relatorio(r['id'])

    # ---- Sub-aba: Gerenciar Membros ----
    with sub_cfg[1]:
        st.markdown("#### 👥 Gerenciar Membros")
        st.caption("Categoria aqui é a FONTE DA VERDADE para todos os relatórios.")

        tab_ativos, tab_inativos = st.tabs(["👥 Membros Ativos", "💤 Membros Inativos"])

        def renderizar_formulario_membro(nome):
            m        = membros_db[nome]
            cat_icon = {"PUBLICADOR": "👤", "PIONEIRO AUXILIAR": "💎",
                        "PIONEIRO REGULAR": "⭐"}.get(m.get('categoria',''), "👤")

            with st.expander(f"{cat_icon} **{nome}** — {m.get('categoria','PUBLICADOR')}"):
                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown("##### 📋 Dados Pessoais")
                    cat_gravada = m.get('categoria', 'PUBLICADOR')
                    if cat_gravada not in categorias_lista:
                        cat_gravada = 'PUBLICADOR'
                    nova_cat = st.selectbox("Categoria de Serviço", categorias_lista,
                                             index=categorias_lista.index(cat_gravada),
                                             key=f"cat_{nome}")
                    data_nasc = st.text_input("📅 Nascimento", value=m.get('data_nascimento',''),
                                               placeholder="DD/MM/AAAA", key=f"nasc_{nome}")
                    data_bat  = st.text_input("🕊️ Batismo",   value=m.get('data_batismo',''),
                                               placeholder="DD/MM/AAAA", key=f"bat_{nome}")
                    tel_emer  = st.text_input("📞 Tel. Emergência",
                                               value=m.get('telefone_emergencia',''),
                                               placeholder="(XX) XXXXX-XXXX", key=f"tel_{nome}")

                with col_b:
                    st.markdown("##### 🏷️ Classificação & Cargo")
                    gen_val  = m.get('genero','')
                    nova_gen = st.selectbox("Gênero", _GENEROS,
                                             index=_GENEROS.index(gen_val) if gen_val in _GENEROS else 0,
                                             key=f"gen_{nome}")
                    cls_val  = m.get('classe','')
                    nova_cls = st.selectbox("Classe", _CLASSES,
                                             index=_CLASSES.index(cls_val) if cls_val in _CLASSES else 0,
                                             key=f"cls_{nome}")
                    status_atual = m.get('status', 'Ativo')
                    novo_status  = st.selectbox("Status", _STATUS_OPCOES,
                                                 index=_STATUS_OPCOES.index(status_atual) if status_atual in _STATUS_OPCOES else 0,
                                                 key=f"status_{nome}")
                    cargos_atuais = cargos_para_lista(m.get('cargo',''))
                    st.markdown("**Cargo(s)**")
                    novos_cargos = []
                    for cargo_op in _CARGOS_LISTA:
                        if st.checkbox(cargo_op, value=(cargo_op in cargos_atuais),
                                       key=f"cgo_{nome}_{cargo_op}"):
                            novos_cargos.append(cargo_op)

                st.divider()
                col_save_m, col_del_m = st.columns([3, 1])

                with col_save_m:
                    if st.button("💾 Salvar Alterações", key=f"save_{nome}",
                                 use_container_width=True, type="primary"):
                        extra = {
                            "data_nascimento":     data_nasc,
                            "data_batismo":        data_bat,
                            "telefone_emergencia": tel_emer,
                            "genero":              nova_gen,
                            "classe":              nova_cls,
                            "cargo":               novos_cargos,
                            "status":              novo_status,
                        }
                        atualizar_membro(nome, nova_cat, extra=extra)
                        st.toast(f"✅ {nome} atualizado!")
                        st.rerun()

                with col_del_m:
                    with st.popover("🗑️ Deletar", use_container_width=True):
                        st.error("⚠️ Ação irreversível!")
                        st.write(f"Remove **{nome}** permanentemente do banco de dados.")
                        if st.button(f"Sim, excluir {nome.split()[0]}", key=f"conf_del_m_{nome}",
                                     type="primary", use_container_width=True):
                            deletar_membro(nome)

        membros_ordenados = sorted(membros_db.keys())

        with tab_ativos:
            ativos = [n for n in membros_ordenados if membros_db[n].get('status', 'Ativo') == 'Ativo']
            if ativos:
                for nome in ativos:
                    renderizar_formulario_membro(nome)
            else:
                st.info("Nenhum membro ativo cadastrado.")

        with tab_inativos:
            inativos = [n for n in membros_ordenados if membros_db[n].get('status', 'Ativo') == 'Inativo']
            if inativos:
                for nome in inativos:
                    renderizar_formulario_membro(nome)
            else:
                st.info("Nenhum membro inativo.")

    # ---- Sub-aba: Novo Membro ----
    with sub_cfg[2]:
        st.markdown("#### ➕ Cadastrar Novo Membro")
        with st.form("novo_membro", clear_on_submit=True):
            st.markdown("##### Dados Obrigatórios")
            c1, c2 = st.columns(2)
            nm = c1.text_input("Nome Completo *")
            ct = c2.selectbox("Categoria *", categorias_lista)

            st.markdown("##### Dados do Cartão S-21")
            c3, c4 = st.columns(2)
            data_nasc_n = c3.text_input("📅 Nascimento", placeholder="DD/MM/AAAA")
            data_bat_n  = c4.text_input("🕊️ Batismo",    placeholder="DD/MM/AAAA")

            c5, c6 = st.columns(2)
            gen_n = c5.selectbox("Gênero", ["","Masculino","Feminino"])
            cls_n = c6.selectbox("Classe", ["","Outras ovelhas","Ungido"])

            st.markdown("**Cargo(s)**")
            cargos_novos_form = []
            cols_form = st.columns(len(_CARGOS_LISTA))
            for idx_c, cargo_op in enumerate(_CARGOS_LISTA):
                if cols_form[idx_c].checkbox(cargo_op, key=f"new_cgo_{cargo_op}"):
                    cargos_novos_form.append(cargo_op)

            tel_n = st.text_input("📞 Telefone de Emergência", placeholder="(XX) XXXXX-XXXX")

            if st.form_submit_button("➕ Adicionar Membro", use_container_width=True, type="primary"):
                if nm.strip():
                    extra_n = {
                        "data_nascimento":     data_nasc_n,
                        "data_batismo":        data_bat_n,
                        "telefone_emergencia": tel_n,
                        "genero":              gen_n,
                        "classe":              cls_n,
                        "cargo":               cargos_novos_form,
                        "status":              "Ativo",
                    }
                    atualizar_membro(nm.strip(), ct, novo=True, extra=extra_n)
                    st.success(f"✅ {nm.strip()} adicionado!")
                    st.rerun()
                else:
                    st.error("Informe o nome completo.")
