# =============================================================
# modulo/mod_configuracao.py
# Aba "CONFIGURAÇÃO" — editar relatórios do mês, gerenciar membros
# (ativos/inativos), cadastrar novo membro e (NOVO) gerenciar
# usuários e permissões de acesso por aba.
#
# ATUALIZAÇÃO:
#  - Nova sub-aba "👥 USUÁRIOS E PERMISSÕES": cria usuários e define,
#    para cada aba do sistema, um de três níveis — sem acesso,
#    somente visualizar, ou visualizar e editar.
#  - aceita pode_editar=True/False (permissão da própria aba
#    Configuração). Sem edição, tudo aparece só para consulta.
#
# CORREÇÃO (v1.1):
#  - Os dois conjuntos de sub-abas deste arquivo (o principal — Editar
#    Relatórios/Gerenciar Membros/Novo Membro/Usuários e Permissões —
#    e o aninhado dentro de Gerenciar Membros — Ativos/Inativos) usavam
#    st.tabs(), que perde a aba selecionada sempre que uma ação chama
#    st.rerun(). E quase toda ação aqui chama (salvar relatório,
#    excluir, salvar membro, criar/editar usuário). O sintoma era o
#    conteúdo de todas as sub-abas aparecendo junto depois de qualquer
#    uma dessas ações.
#    Trocado por abas_persistentes() (tabs_persistentes.py) nos dois
#    conjuntos — a aba ativa fica em st.session_state e sobrevive a
#    qualquer rerun.
# =============================================================
import os
import sys

import streamlit as st

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import (
    inicializar_db, atualizar_membro, deletar_relatorio, deletar_membro,
    carregar_relatorios_cached, carregar_usuarios, salvar_usuario, deletar_usuario,
)
from utilitarios import cargos_para_lista
from constantes import (
    categorias_lista, _GENEROS, _CLASSES, _STATUS_OPCOES, _CARGOS_LISTA,
    ABAS_SISTEMA, NIVEIS_PERMISSAO, NIVEIS_PERMISSAO_LABELS,
)
import permissoes
from tabs_persistentes import abas_persistentes


def aba_configuracao(df, df_ok, df_mes, mes_sel, membros_db, pode_editar=True):
    idx_cfg = abas_persistentes([
        "✏️ EDITAR RELATÓRIOS",
        "👥 GERENCIAR MEMBROS",
        "➕ NOVO MEMBRO",
        "🔐 USUÁRIOS E PERMISSÕES",
    ], key="abas_configuracao")

    if not pode_editar:
        permissoes.aviso_somente_leitura()

    # ---- Sub-aba: Editar Relatórios ----
    if idx_cfg == 0:
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
                                                  index=idx_cat, key=f"e_c_{r['id']}",
                                                  disabled=not pode_editar)
                        novas_h  = ce2.number_input("Horas",   value=int(r['horas']),
                                                    key=f"e_h_{r['id']}", disabled=not pode_editar)
                        novos_e  = ce3.number_input("Estudos", value=int(r['estudos_biblicos']),
                                                    key=f"e_e_{r['id']}", disabled=not pode_editar)

                        if pode_editar:
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
    elif idx_cfg == 1:
        st.markdown("#### 👥 Gerenciar Membros")
        st.caption("Categoria aqui é a FONTE DA VERDADE para todos os relatórios.")

        idx_membros = abas_persistentes(
            ["👥 Membros Ativos", "💤 Membros Inativos"], key="abas_membros"
        )

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
                                             key=f"cat_{nome}", disabled=not pode_editar)
                    data_nasc = st.text_input("📅 Nascimento", value=m.get('data_nascimento',''),
                                               placeholder="DD/MM/AAAA", key=f"nasc_{nome}",
                                               disabled=not pode_editar)
                    data_bat  = st.text_input("🕊️ Batismo",   value=m.get('data_batismo',''),
                                               placeholder="DD/MM/AAAA", key=f"bat_{nome}",
                                               disabled=not pode_editar)
                    tel_emer  = st.text_input("📞 Tel. Emergência",
                                               value=m.get('telefone_emergencia',''),
                                               placeholder="(XX) XXXXX-XXXX", key=f"tel_{nome}",
                                               disabled=not pode_editar)

                with col_b:
                    st.markdown("##### 🏷️ Classificação & Cargo")
                    gen_val  = m.get('genero','')
                    nova_gen = st.selectbox("Gênero", _GENEROS,
                                             index=_GENEROS.index(gen_val) if gen_val in _GENEROS else 0,
                                             key=f"gen_{nome}", disabled=not pode_editar)
                    cls_val  = m.get('classe','')
                    nova_cls = st.selectbox("Classe", _CLASSES,
                                             index=_CLASSES.index(cls_val) if cls_val in _CLASSES else 0,
                                             key=f"cls_{nome}", disabled=not pode_editar)
                    status_atual = m.get('status', 'Ativo')
                    novo_status  = st.selectbox("Status", _STATUS_OPCOES,
                                                 index=_STATUS_OPCOES.index(status_atual) if status_atual in _STATUS_OPCOES else 0,
                                                 key=f"status_{nome}", disabled=not pode_editar)
                    cargos_atuais = cargos_para_lista(m.get('cargo',''))
                    st.markdown("**Cargo(s)**")
                    novos_cargos = []
                    for cargo_op in _CARGOS_LISTA:
                        if st.checkbox(cargo_op, value=(cargo_op in cargos_atuais),
                                       key=f"cgo_{nome}_{cargo_op}", disabled=not pode_editar):
                            novos_cargos.append(cargo_op)

                if pode_editar:
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

        if idx_membros == 0:
            ativos = [n for n in membros_ordenados if membros_db[n].get('status', 'Ativo') == 'Ativo']
            if ativos:
                for nome in ativos:
                    renderizar_formulario_membro(nome)
            else:
                st.info("Nenhum membro ativo cadastrado.")

        elif idx_membros == 1:
            inativos = [n for n in membros_ordenados if membros_db[n].get('status', 'Ativo') == 'Inativo']
            if inativos:
                for nome in inativos:
                    renderizar_formulario_membro(nome)
            else:
                st.info("Nenhum membro inativo.")

    # ---- Sub-aba: Novo Membro ----
    elif idx_cfg == 2:
        st.markdown("#### ➕ Cadastrar Novo Membro")
        if not pode_editar:
            st.caption("Sem permissão de edição nesta aba.")
        else:
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

    # ---- Sub-aba: Usuários e Permissões ----
    elif idx_cfg == 3:
        _sub_usuarios_e_permissoes(pode_editar=pode_editar)


def _seletor_permissoes(prefixo_key: str, permissoes_atuais: dict, admin: bool):
    """
    Desenha um seletor de nível (sem_acesso/visualizar/editar) para
    cada aba do sistema. Retorna o dict {aba_id: nivel} escolhido.
    Se admin=True, os seletores ficam desabilitados (admin sempre
    tem acesso total, não precisa configurar aba a aba).
    """
    novo = {}
    st.markdown("**Permissões por aba**")
    if admin:
        st.caption("Usuário administrador — acesso total automático em todas as abas.")

    for aba in ABAS_SISTEMA:
        nivel_atual = permissoes_atuais.get(aba["id"], "sem_acesso")
        idx = NIVEIS_PERMISSAO.index(nivel_atual) if nivel_atual in NIVEIS_PERMISSAO else 0
        col_lbl, col_sel = st.columns([1.3, 2])
        with col_lbl:
            st.markdown(f"{aba['icone']} {aba['label']}")
        with col_sel:
            escolha = st.radio(
                aba["label"], NIVEIS_PERMISSAO,
                index=idx, horizontal=True, disabled=admin,
                key=f"{prefixo_key}_{aba['id']}",
                format_func=lambda v: NIVEIS_PERMISSAO_LABELS[v],
                label_visibility="collapsed",
            )
        novo[aba["id"]] = escolha
    return novo


def _sub_usuarios_e_permissoes(pode_editar=True):
    st.markdown("#### 🔐 Usuários e Permissões")
    st.caption(
        "Crie um usuário para cada pessoa que precisa acessar o sistema e defina, "
        "aba por aba, se ela pode **visualizar apenas** ou **visualizar e editar**. "
        "Quem não recebe nenhuma permissão numa aba simplesmente não a vê."
    )

    usuarios = carregar_usuarios()

    st.markdown("---")
    st.markdown("##### 👤 Usuários cadastrados")

    if not usuarios:
        st.info("Nenhum usuário cadastrado ainda no banco. "
                 "O acesso administrador de fábrica continua funcionando normalmente.")
    else:
        for uid, dados in sorted(usuarios.items()):
            nome_exib = dados.get("nome_exibicao", uid)
            tag_admin = " · 🛡️ Administrador" if dados.get("admin") else ""
            with st.expander(f"👤 {nome_exib}  ({uid}){tag_admin}"):
                if pode_editar:
                    nova_senha = st.text_input(
                        "Nova senha (deixe em branco para manter a atual)",
                        type="password", key=f"senha_{uid}",
                    )
                    novo_nome = st.text_input("Nome de exibição", value=nome_exib, key=f"nome_{uid}")
                    novo_admin = st.checkbox("Administrador (acesso total automático)",
                                              value=dados.get("admin", False), key=f"admin_{uid}")

                    novas_perm = _seletor_permissoes(f"perm_{uid}", dados.get("permissoes", {}), novo_admin)

                    col_s, col_d = st.columns([3, 1])
                    with col_s:
                        if st.button("💾 Salvar alterações", key=f"save_user_{uid}",
                                     type="primary", use_container_width=True):
                            salvar_usuario(uid, nova_senha, novo_nome, novas_perm, admin=novo_admin)
                            st.toast(f"✅ Usuário '{novo_nome}' atualizado!")
                            st.rerun()
                    with col_d:
                        with st.popover("🗑️ Excluir", use_container_width=True):
                            st.error("Ação irreversível.")
                            if st.button(f"Sim, excluir {uid}", key=f"conf_del_user_{uid}",
                                         type="primary", use_container_width=True):
                                deletar_usuario(uid)
                                st.toast(f"🗑️ Usuário '{uid}' removido.")
                                st.rerun()
                else:
                    st.caption("Sem permissão de edição nesta aba.")
                    for aba in ABAS_SISTEMA:
                        nivel = "editar" if dados.get("admin") else dados.get("permissoes", {}).get(aba["id"], "sem_acesso")
                        st.markdown(f"- {aba['icone']} {aba['label']}: **{NIVEIS_PERMISSAO_LABELS[nivel]}**")

    if pode_editar:
        st.markdown("---")
        st.markdown("##### ➕ Criar novo usuário")
        with st.form("novo_usuario_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            novo_username = c1.text_input("Nome de usuário (login) *", placeholder="ex: maria")
            novo_nome_ex  = c2.text_input("Nome de exibição", placeholder="ex: Maria Silva")
            c3, c4 = st.columns(2)
            senha_inicial = c3.text_input("Senha *", type="password")
            eh_admin      = c4.checkbox("Administrador (acesso total automático)")

            permissoes_novo_usuario = {}
            if not eh_admin:
                st.markdown("**Permissões por aba**")
                for aba in ABAS_SISTEMA:
                    col_lbl, col_sel = st.columns([1.3, 2])
                    with col_lbl:
                        st.markdown(f"{aba['icone']} {aba['label']}")
                    with col_sel:
                        permissoes_novo_usuario[aba["id"]] = st.radio(
                            aba["label"], NIVEIS_PERMISSAO, index=0, horizontal=True,
                            key=f"novo_perm_{aba['id']}",
                            format_func=lambda v: NIVEIS_PERMISSAO_LABELS[v],
                            label_visibility="collapsed",
                        )
            else:
                st.caption("Administrador recebe acesso total automaticamente — nada a configurar aqui.")

            if st.form_submit_button("➕ Criar Usuário", type="primary", use_container_width=True):
                if not novo_username.strip() or not senha_inicial:
                    st.error("Informe usuário e senha.")
                else:
                    salvar_usuario(
                        novo_username.strip(), senha_inicial,
                        novo_nome_ex.strip() or novo_username.strip(),
                        permissoes_novo_usuario, admin=eh_admin,
                    )
                    st.success(f"✅ Usuário '{novo_username.strip()}' criado!")
                    st.rerun()
