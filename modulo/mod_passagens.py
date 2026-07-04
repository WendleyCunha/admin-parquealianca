# =============================================================
# modulo/mod_passagens.py
# Módulo VGP Passagens — controle de reservas, pagamentos e
# embarque para eventos com ônibus fretado.
#
# ATUALIZAÇÃO:
#  - Removidos os gradientes escuros (#161514/#2a2620) do cabeçalho
#    e do card "nenhum evento ativo" — agora usam a mesma paleta
#    clara dourada/creme do resto do app.
#  - Aceita pode_editar=True/False: sem edição, os formulários de
#    reserva/embarque/ajustes ficam ocultos (a visão de reservas,
#    pendências e KPIs continua visível).
# =============================================================
import os
import sys
import io
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import inicializar_db
import permissoes

CAPACIDADE = 46


def atualizar_cadastro_central(dados_pax):
    db = inicializar_db()
    if db:
        pax_id = dados_pax['nome'].lower().replace(" ", "")
        db.collection("cadastro_geral").document(pax_id).set({
            "nome": dados_pax['nome'], "rg": dados_pax.get('rg', ""),
            "cpf": dados_pax.get('cpf', ""), "grupo": dados_pax.get('grupo', "Geral"),
            "ultima_atualizacao": datetime.now()
        }, merge=True)


def buscar_pessoa_central(nome_pesquisa):
    db = inicializar_db()
    if not db or not nome_pesquisa: return None
    nome_busca = nome_pesquisa.lower().strip()
    for doc in db.collection("cadastro_geral").stream():
        dados = doc.to_dict()
        if nome_busca in dados.get('nome', '').lower():
            return dados
    return None


def criar_evento(nome, datas, valor_passagem):
    db = inicializar_db()
    if db:
        id_evento = f"{nome.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
        db.collection("eventos").document(id_evento).set({
            "nome": nome, "datas": datas, "valor": valor_passagem,
            "status": "ativo", "criado_em": datetime.now(),
            "frotas": {dia: 1 for dia in datas}
        })
        return id_evento


def adicionar_novo_onibus(id_evento, dia):
    db = inicializar_db()
    if db:
        doc_ref = db.collection("eventos").document(id_evento)
        evento  = doc_ref.get().to_dict()
        frotas  = evento.get('frotas', {d: 1 for d in evento['datas']})
        frotas[dia] = frotas.get(dia, 1) + 1
        doc_ref.update({"frotas": frotas})


def salvar_passageiro(id_evento, dados_pax):
    db = inicializar_db()
    if db:
        sufixo = dados_pax['rg'] if dados_pax.get('rg') else "reserva"
        pax_id = f"{dados_pax['nome']}_{sufixo}".lower().replace(" ", "")
        if 'embarcou' not in dados_pax: dados_pax['embarcou'] = False
        db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).set(dados_pax)
        atualizar_cadastro_central(dados_pax)


def atualizar_embarque(id_evento, pax, status):
    db = inicializar_db()
    if db:
        sufixo = pax['rg'] if pax.get('rg') else "reserva"
        pax_id = f"{pax['nome']}_{sufixo}".lower().replace(" ", "")
        db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).update({"embarcou": status})


def deletar_passageiro(id_evento, nome, rg):
    db = inicializar_db()
    if db:
        sufixo = rg if rg else "reserva"
        pax_id = f"{nome}_{sufixo}".lower().replace(" ", "")
        db.collection("eventos").document(id_evento).collection("passageiros").document(pax_id).delete()


def carregar_passageiros(id_evento):
    db = inicializar_db()
    return [p.to_dict() for p in db.collection("eventos").document(id_evento).collection("passageiros").stream()]


def carregar_eventos():
    db = inicializar_db()
    if not db: return {}
    return {doc.id: doc.to_dict() for doc in db.collection("eventos").where("status", "==", "ativo").stream()}


@st.dialog("Gerenciar Reserva")
def gerenciar_pax_dialog(pax, id_evento, evento_atual):
    st.markdown("### 👤 " + pax['nome'])
    total_devido    = pax.get('valor_total', len(pax.get('dias_onibus', [])) * evento_atual['valor'])
    pago_atualmente = pax.get('valor_pago', 0.0)
    c1, c2 = st.columns(2)
    c1.metric("Total da Passagem", "R$ %.2f" % total_devido)
    c2.metric("Saldo Pendente",    "R$ %.2f" % (total_devido - pago_atualmente), delta_color="inverse")

    with st.form("edit_pax_final"):
        nome = st.text_input("Nome", value=pax['nome'])
        cc1, cc2 = st.columns(2)
        rg  = cc1.text_input("RG",  value=pax.get('rg', ""))
        cpf = cc2.text_input("CPF", value=pax.get('cpf', ""))
        grupos = ["Rosas", "Engenho", "Cohab", "Geral"]
        g_atual = pax.get('grupo', 'Geral')
        grupo = st.selectbox("Grupo", grupos, index=grupos.index(g_atual) if g_atual in grupos else 3)

        st.divider()
        st.markdown("**💰 Registrar Recebimento**")
        cr1, cr2, cr3 = st.columns(3)
        valor_recebido = cr1.number_input("Recebido agora", min_value=0.0, value=0.0, step=5.0)
        valor_entregue = cr2.number_input("Troco entregue", min_value=0.0, value=0.0)
        if valor_entregue > 0 and valor_recebido > 0:
            cr3.success("Troco: R$ %.2f" % max(valor_entregue - valor_recebido, 0))

        st.divider()
        st.markdown("**🗓 Viagens**")
        novas_viagens  = []
        viagens_atuais = {v['dia']: v['bus'] for v in pax.get('dias_onibus', [])}
        for dia in evento_atual['datas']:
            cd1, cd2 = st.columns([1, 2])
            if cd1.checkbox(dia, value=dia in viagens_atuais, key="edit_chk_" + dia):
                n_frotas    = evento_atual.get('frotas', {}).get(dia, 1)
                bus_default = viagens_atuais.get(dia, 1)
                bus_sel     = cd2.selectbox("Ônibus " + dia, range(1, n_frotas + 1),
                                            index=min(bus_default - 1, n_frotas - 1),
                                            key="edit_sel_" + dia)
                novas_viagens.append({"dia": dia, "bus": bus_sel})

        st.divider()
        novo_total_pago = pago_atualmente + valor_recebido
        pago     = st.toggle("💰 Pagamento quitado", value=pax.get('pago', False) or (novo_total_pago >= total_devido))
        embarque = st.toggle("🚌 Embarcou",           value=pax.get('embarcou', False))

        cb1, cb2 = st.columns(2)
        if cb1.form_submit_button("💾 Salvar", use_container_width=True, type="primary"):
            if nome != pax['nome'] or rg != pax.get('rg', ""):
                deletar_passageiro(id_evento, pax['nome'], pax.get('rg', ""))
            pax.update({"nome": nome, "rg": rg, "cpf": cpf, "grupo": grupo,
                        "dias_onibus": novas_viagens, "pago": pago, "embarcou": embarque,
                        "valor_total": evento_atual['valor'] * len(novas_viagens),
                        "valor_pago": novo_total_pago})
            salvar_passageiro(id_evento, pax)
            st.rerun()
        if cb2.form_submit_button("🗑️ Excluir", use_container_width=True):
            deletar_passageiro(id_evento, pax['nome'], pax.get('rg', ""))
            st.rerun()


def renderizar_cabecalho_passagens(evento, df, id_sel, pode_editar=True):
    total      = len(df) if not df.empty else 0
    pagos      = int(df['pago'].sum())         if not df.empty and 'pago'      in df.columns else 0
    pendente   = total - pagos
    arrecadado = float(df['valor_pago'].sum()) if not df.empty and 'valor_pago' in df.columns else 0.0
    a_receber  = float((df['valor_total'].fillna(0) - df['valor_pago'].fillna(0)).clip(lower=0).sum()) \
                 if not df.empty and 'valor_total' in df.columns else 0.0
    pct        = round((pagos / total) * 100) if total else 0
    datas_str  = ", ".join(evento.get("datas", []))
    nome_ev    = evento.get('nome', '')

    # ---- Montar HTML dos cards de frota ----
    frotas_html  = ""
    needs_add    = {}
    for dia in evento.get('datas', []):
        n_frotas = evento.get('frotas', {}).get(dia, 1)
        for b in range(1, n_frotas + 1):
            qtd = 0
            if not df.empty:
                for _, p in df.iterrows():
                    for v in (p.get('dias_onibus') or []):
                        if v.get('dia') == dia and v.get('bus') == b:
                            qtd += 1
            perc     = min(round((qtd / CAPACIDADE) * 100), 100)
            cor      = "#e05c5c" if qtd >= CAPACIDADE else ("#2E6DA4" if perc > 80 else "#3fae66")
            lotado   = "<div style='font-size:0.6rem;color:#c14b4b;font-weight:700;margin-top:3px;'>🔴 Lotado</div>" \
                       if qtd >= CAPACIDADE else ""
            frotas_html += (
                "<div style='background:#FFFFFF;border:1px solid #D7E6F4;"
                "border-radius:10px;padding:11px 13px;min-width:130px;flex:1;'>"
                "<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px;'>"
                "<span style='font-size:0.72rem;font-weight:700;color:#1A1A1A;'>" + dia + " · Ônibus " + str(b) + "</span>"
                "<span style='font-size:0.65rem;font-weight:600;color:#5B7BA6;'>" + str(perc) + "%</span>"
                "</div>"
                "<div style='background:#E7F0FA;border-radius:4px;height:6px;overflow:hidden;margin-bottom:5px;'>"
                "<div style='width:" + str(perc) + "%;height:100%;background:" + cor + ";border-radius:4px;'></div>"
                "</div>"
                "<div style='font-size:0.63rem;color:#5B7BA6;'>" + str(qtd) + " / " + str(CAPACIDADE) + " passageiros</div>"
                + lotado +
                "</div>"
            )
            if qtd >= CAPACIDADE and b == n_frotas:
                needs_add[dia] = b + 1

    # ---- Montar HTML dos KPIs ----
    def kpi(lbl, val, sub, cor="#1A1A1A"):
        return (
            "<div style='background:#FFFFFF;border:1px solid #D7E6F4;"
            "border-radius:11px;padding:12px 14px;flex:1;min-width:110px;'>"
            "<div style='font-size:0.62rem;color:#5B7BA6;text-transform:uppercase;"
            "letter-spacing:0.09em;font-weight:700;margin-bottom:5px;'>" + lbl + "</div>"
            "<div style='font-size:1.4rem;font-weight:700;color:" + cor + ";line-height:1;'>" + str(val) + "</div>"
            "<div style='font-size:0.65rem;color:#9FB6D0;margin-top:3px;'>" + sub + "</div>"
            "</div>"
        )

    kpis_html = (
        kpi("Reservas",   total,                            "passageiros")
      + kpi("Pagos",      pagos,                            str(pct) + "% confirmados", "#1F4E86")
      + kpi("Pendentes",  pendente,                         "aguardando",                "#3B6FA0")
      + kpi("Arrecadado", "R$ {:,.0f}".format(arrecadado),  "recebido",                  "#1F4E86")
      + kpi("A Receber",  "R$ {:,.0f}".format(a_receber),   "em aberto",                 "#3B6FA0")
    )

    n_frotas_total       = sum(evento.get('frotas', {}).get(d, 1) for d in evento.get('datas', []))
    linhas_frota_mobile  = n_frotas_total
    altura = (
        72
        + 3 * 78
        + 50
        + linhas_frota_mobile * 82
        + 56
    )

    # Cabeçalho do módulo — claro, dourado/creme (mesma paleta do resto do app).
    html = (
        "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap' rel='stylesheet'>"
        "<style>* { box-sizing:border-box; } body { background:transparent; overflow:hidden; margin:0; }</style>"
        "<div id='root' style='font-family:Inter,sans-serif;"
        "background:linear-gradient(180deg,#FFFFFF 0%,#F3F8FE 100%);"
        "border:1px solid #2E6DA4;border-radius:16px;padding:24px 24px 20px;color:#1A1A1A;'>"

        "<div style='font-size:1.5rem;font-weight:700;letter-spacing:-0.5px;color:#1F4E86;'>"
        "🕊️ " + nome_ev +
        "</div>"
        "<div style='font-size:0.8rem;color:#6B6B6B;margin-top:4px;font-weight:400;'>"
        "Controle de Passagens · " + datas_str +
        "</div>"

        "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));"
        "gap:10px;margin-top:16px;'>"
        + kpis_html +
        "</div>"

        "<div style='border-top:1px solid #D7E6F4;margin:16px 0 14px;'></div>"

        "<div style='font-size:0.6rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;"
        "color:#5B7BA6;margin-bottom:10px;'>Ocupação por Frota</div>"
        "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px;'>"
        + frotas_html +
        "</div>"

        "</div>"

        "<script>"
        "function reportH(){"
        "  var h=document.getElementById('root').getBoundingClientRect().height+8;"
        "  window.parent.postMessage({type:'streamlit:setFrameHeight',height:h},'*');"
        "}"
        "window.addEventListener('load', function(){ setTimeout(reportH, 50); });"
        "new ResizeObserver(function(){ setTimeout(reportH, 50); })"
        "  .observe(document.getElementById('root'));"
        "</script>"
    )

    components.html(html, height=altura, scrolling=False)

    if needs_add and pode_editar:
        cols = st.columns(len(needs_add))
        for idx, (dia, prox) in enumerate(needs_add.items()):
            with cols[idx]:
                if st.button("➕ Adicionar Ônibus " + str(prox) + " — " + dia, key="hdr_add_" + dia):
                    adicionar_novo_onibus(id_sel, dia)
                    st.rerun()


def exibir_modulo_passagens(pode_editar=True):
    if not pode_editar:
        permissoes.aviso_somente_leitura()

    eventos_ativos = carregar_eventos()

    if not eventos_ativos:
        components.html(
            "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap' rel='stylesheet'>"
            "<div style='font-family:Inter,sans-serif;background:linear-gradient(180deg,#FFFFFF 0%,#F3F8FE 100%);"
            "border:1px solid #2E6DA4;border-radius:16px;padding:24px;color:#1A1A1A;'>"
            "<div style='font-size:1.5rem;font-weight:700;color:#1F4E86;'>🕊️ VGP Passagens</div>"
            "<div style='font-size:0.82rem;color:#6B6B6B;margin-top:4px;'>"
            "Nenhum evento ativo" + ("" if pode_editar else " — contate um administrador") +
            "</div></div>",
            height=110
        )
        if pode_editar:
            with st.form("criar_evento_inicial"):
                st.subheader("Novo Evento")
                n_ev = st.text_input("Nome do Evento (ex: Assembleia Março)")
                v_ev = st.number_input("Valor da Passagem (R$)", min_value=0.0, value=50.0, step=5.0)
                d_ev = st.multiselect("Dias de Operação", ["Sexta", "Sábado", "Domingo"])
                if st.form_submit_button("🚀 Criar Evento", type="primary"):
                    if n_ev and d_ev:
                        criar_evento(n_ev, d_ev, v_ev)
                        st.rerun()
                    else:
                        st.error("Informe o nome e ao menos um dia.")
        return

    c1, c2 = st.columns([4, 1])
    with c2:
        id_sel = st.selectbox("", list(eventos_ativos.keys()),
                              format_func=lambda x: eventos_ativos[x]['nome'],
                              label_visibility="collapsed", key="passagens_evento_sel")

    evento    = eventos_ativos[id_sel]
    pax_lista = carregar_passageiros(id_sel)
    df        = pd.DataFrame(pax_lista)

    if not df.empty:
        for col, default in [('grupo','Geral'),('pago',False),('valor_pago',0.0),
                              ('valor_total',0.0),('embarcou',False)]:
            if col not in df.columns: df[col] = default
            df[col] = df[col].fillna(default)

    renderizar_cabecalho_passagens(evento, df, id_sel, pode_editar=pode_editar)

    labels_tabs = ["📝 Reserva & Pagamentos", "🚌 Chamada de Embarque"]
    if pode_editar:
        labels_tabs.append("⚙️ Ajustes")
    tabs_pax = st.tabs(labels_tabs)
    tab_reserva, tab_chamada = tabs_pax[0], tabs_pax[1]
    tab_ajustes = tabs_pax[2] if pode_editar else None

    # ---- ABA 1: RESERVA + PENDENTES ----
    with tab_reserva:
        col_form, col_pend = st.columns([1, 1], gap="large")

        with col_form:
            if pode_editar:
                st.markdown("**Nova Reserva**")
                busca_nome = st.text_input("🔍 Buscar cadastro existente", placeholder="Digite parte do nome...")
                mestre = buscar_pessoa_central(busca_nome) if busca_nome else None
                if mestre:
                    st.success("✅ Cadastro encontrado: **" + mestre['nome'] + "**")

                with st.form("reserva_form", clear_on_submit=True):
                    nome_f  = st.text_input("Nome Completo *", value=mestre['nome'] if mestre else busca_nome)
                    ci1, ci2 = st.columns(2)
                    rg_f  = ci1.text_input("RG",  value=mestre.get('rg',  '') if mestre else "")
                    cpf_f = ci2.text_input("CPF", value=mestre.get('cpf', '') if mestre else "")
                    grupo_f = st.selectbox("Grupo / Localização", ["Rosas", "Engenho", "Cohab", "Geral"])
                    st.markdown("**Viagens:**")
                    viagens = []
                    for dia in evento['datas']:
                        cv1, cv2 = st.columns([1, 2])
                        if cv1.checkbox(dia, key="f_res_" + dia):
                            f_dia = evento.get('frotas', {}).get(dia, 1)
                            b_sel = cv2.selectbox("Ônibus " + dia, range(1, f_dia + 1), key="f_bus_" + dia)
                            viagens.append({"dia": dia, "bus": b_sel})
                    pago_f = st.toggle("Pagamento confirmado neste ato")
                    if st.form_submit_button("✅ Confirmar Reserva", type="primary", use_container_width=True):
                        if nome_f and viagens:
                            vt = evento['valor'] * len(viagens)
                            salvar_passageiro(id_sel, {
                                "nome": nome_f, "rg": rg_f, "cpf": cpf_f, "grupo": grupo_f,
                                "dias_onibus": viagens, "pago": pago_f, "embarcou": False,
                                "valor_total": vt, "valor_pago": vt if pago_f else 0.0
                            })
                            st.success("Reserva gravada com sucesso!")
                            st.rerun()
                        else:
                            st.error("Informe o nome e selecione ao menos um dia.")
            else:
                st.caption("Sem permissão para lançar novas reservas nesta conta.")

        with col_pend:
            st.markdown("**Pagamentos Pendentes**")
            if not df.empty:
                pendentes = df[df['pago'] == False].sort_values('nome')
                if pendentes.empty:
                    st.markdown(
                        "<div style='text-align:center;padding:40px 0;color:#5B7BA6;'>"
                        "<div style='font-size:2rem;'>✅</div>"
                        "<div style='font-weight:600;margin-top:8px;'>Todos pagos!</div>"
                        "</div>", unsafe_allow_html=True)
                else:
                    total_pend = 0.0
                    for _, r in pendentes.iterrows():
                        v_total = float(r.get('valor_total') or 0) or (len(r.get('dias_onibus') or []) * evento['valor'])
                        v_pago  = float(r.get('valor_pago')  or 0)
                        v_falta = max(v_total - v_pago, 0)
                        total_pend += v_falta
                        grp_tag = r.get('grupo', 'Geral')
                        if pode_editar:
                            ci, cb = st.columns([5, 1])
                        else:
                            ci = st.container()
                        with ci:
                            st.markdown(
                                "<div style='background:white;border:1px solid #D7E6F4;"
                                "border-left:4px solid #e05c5c;border-radius:10px;"
                                "padding:10px 13px;margin-bottom:7px;"
                                "display:flex;justify-content:space-between;align-items:center;'>"
                                "<div>"
                                "<div style='font-weight:600;font-size:0.87rem;color:#1A1A1A;'>" + r['nome'] + "</div>"
                                "<div style='font-size:0.74rem;color:#5B7BA6;margin-top:2px;'>"
                                "📍 " + grp_tag + " · " + str(len(r.get('dias_onibus') or [])) + " viagem(ns)</div>"
                                "</div>"
                                "<div style='font-weight:700;font-size:0.9rem;color:#c14b4b;"
                                "white-space:nowrap;margin-left:8px;'>"
                                "– R$ {:,.2f}".format(v_falta) + "</div>"
                                "</div>", unsafe_allow_html=True)
                        if pode_editar:
                            with cb:
                                if st.button("✏️", key="ed_pe_" + r['nome'], help="Editar / Receber pagamento"):
                                    gerenciar_pax_dialog(r.to_dict(), id_sel, evento)

                    st.markdown(
                        "<div style='background:#E7F0FA;border:1px solid #BBD3EC;border-radius:8px;"
                        "padding:10px 14px;margin-top:10px;font-size:0.85rem;"
                        "display:flex;justify-content:space-between;align-items:center;'>"
                        "<strong>Total em aberto:</strong>"
                        "<span style='font-weight:700;color:#1F4E86;'>R$ {:,.2f}</span>".format(total_pend) +
                        "</div>", unsafe_allow_html=True)
            else:
                st.info("Nenhuma reserva lançada ainda.")

    # ---- ABA 2: CHAMADA ----
    with tab_chamada:
        if df.empty:
            st.info("Nenhuma reserva para exibir.")
        else:
            df_pagos = df[df['pago'] == True].copy()
            if df_pagos.empty:
                st.markdown(
                    "<div style='text-align:center;padding:60px 0;color:#5B7BA6;'>"
                    "<div style='font-size:2.5rem;'>🕊️</div>"
                    "<div style='font-weight:600;margin-top:10px;'>Nenhum pagamento confirmado ainda.</div>"
                    "<div style='font-size:0.82rem;margin-top:6px;'>Só passageiros com pagamento quitado aparecem aqui.</div>"
                    "</div>", unsafe_allow_html=True)
            else:
                tot_p  = len(df_pagos)
                emb_t  = int(df_pagos['embarcou'].sum())
                falt_t = tot_p - emb_t
                st.markdown(
                    "<div style='display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;'>"
                    "<div style='background:white;border:1px solid #D7E6F4;border-radius:10px;"
                    "padding:12px 18px;flex:1;min-width:110px;'>"
                    "<div style='font-size:0.62rem;color:#5B7BA6;text-transform:uppercase;"
                    "letter-spacing:.08em;font-weight:700;'>Confirmados</div>"
                    "<div style='font-size:1.5rem;font-weight:700;color:#1A1A1A;'>" + str(tot_p) + "</div></div>"

                    "<div style='background:white;border:1px solid #D7E6F4;border-left:3px solid #3fae66;"
                    "border-radius:10px;padding:12px 18px;flex:1;min-width:110px;'>"
                    "<div style='font-size:0.62rem;color:#5B7BA6;text-transform:uppercase;"
                    "letter-spacing:.08em;font-weight:700;'>Embarcados</div>"
                    "<div style='font-size:1.5rem;font-weight:700;color:#2f8f52;'>" + str(emb_t) + "</div></div>"

                    "<div style='background:white;border:1px solid #D7E6F4;border-left:3px solid #2E6DA4;"
                    "border-radius:10px;padding:12px 18px;flex:1;min-width:110px;'>"
                    "<div style='font-size:0.62rem;color:#5B7BA6;text-transform:uppercase;"
                    "letter-spacing:.08em;font-weight:700;'>Aguardando</div>"
                    "<div style='font-size:1.5rem;font-weight:700;color:#3B6FA0;'>" + str(falt_t) + "</div></div>"
                    "</div>", unsafe_allow_html=True)

                for grp in sorted(df_pagos['grupo'].unique()):
                    df_grp = df_pagos[df_pagos['grupo'] == grp]
                    n_grp  = len(df_grp)
                    e_grp  = int(df_grp['embarcou'].sum())
                    with st.expander("📍 " + grp.upper() + "  —  " + str(e_grp) + "/" + str(n_grp) + " embarcados", expanded=True):
                        cf, co = st.columns(2)
                        with cf:
                            st.markdown("<div style='font-size:0.7rem;font-weight:700;text-transform:uppercase;"
                                        "letter-spacing:.08em;color:#3B6FA0;margin-bottom:8px;'>⏳ Aguardando</div>",
                                        unsafe_allow_html=True)
                            for _, p in df_grp[df_grp['embarcou'] == False].sort_values('nome').iterrows():
                                if pode_editar:
                                    cn, cb = st.columns([5, 1])
                                else:
                                    cn = st.container()
                                cn.markdown("<div style='font-weight:500;font-size:0.87rem;color:#1A1A1A;"
                                            "padding:6px 0;border-bottom:1px solid #E7F0FA;'>" + p['nome'] + "</div>",
                                            unsafe_allow_html=True)
                                if pode_editar and cb.button("✅", key="emb_" + grp + "_" + p['nome']):
                                    atualizar_embarque(id_sel, p.to_dict(), True); st.rerun()
                        with co:
                            st.markdown("<div style='font-size:0.7rem;font-weight:700;text-transform:uppercase;"
                                        "letter-spacing:.08em;color:#2f8f52;margin-bottom:8px;'>🟢 Embarcados</div>",
                                        unsafe_allow_html=True)
                            for _, p in df_grp[df_grp['embarcou'] == True].sort_values('nome').iterrows():
                                if pode_editar:
                                    cn, cb = st.columns([5, 1])
                                else:
                                    cn = st.container()
                                cn.markdown("<div style='font-weight:500;font-size:0.87rem;color:#5B7BA6;"
                                            "text-decoration:line-through;padding:6px 0;"
                                            "border-bottom:1px solid #E7F0FA;'>" + p['nome'] + "</div>",
                                            unsafe_allow_html=True)
                                if pode_editar and cb.button("↩️", key="rem_" + grp + "_" + p['nome']):
                                    atualizar_embarque(id_sel, p.to_dict(), False); st.rerun()

    # ---- ABA 3: AJUSTES (só existe se pode_editar) ----
    if pode_editar and tab_ajustes is not None:
        with tab_ajustes:
            ca1, ca2 = st.columns(2)
            with ca1:
                st.markdown("**Novo Evento**")
                with st.form("criar_evento_adj"):
                    n_ev = st.text_input("Nome do Evento")
                    v_ev = st.number_input("Valor da Passagem (R$)", min_value=0.0, value=50.0, step=5.0)
                    d_ev = st.multiselect("Dias de Operação", ["Sexta", "Sábado", "Domingo"])
                    if st.form_submit_button("🚀 Criar Evento", type="primary"):
                        if n_ev and d_ev:
                            criar_evento(n_ev, d_ev, v_ev); st.rerun()
                st.divider()
                st.markdown("**Exportar Dados**")
                if not df.empty:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Passageiros')
                    st.download_button("📥 Baixar Excel", output.getvalue(),
                                       "lista_" + id_sel + ".xlsx", use_container_width=True)
            with ca2:
                st.markdown("**Encerrar Evento**")
                with st.container(border=True):
                    st.warning("Encerrar **" + evento['nome'] + "** o moverá para o histórico.")
                    confirmacao = st.text_input("Digite o nome do evento para confirmar:", placeholder=evento['nome'])
                    if st.button("🏁 Arquivar Evento", type="primary", use_container_width=True):
                        if confirmacao.strip().lower() == evento['nome'].strip().lower():
                            inicializar_db().collection("eventos").document(id_sel).update({"status": "finalizado"})
                            st.success("Evento arquivado.")
                            st.rerun()
                        else:
                            st.error("Nome não confere. Tente novamente.")
