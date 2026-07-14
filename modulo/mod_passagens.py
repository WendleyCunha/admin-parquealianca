# =============================================================
# modulo/mod_passagens.py
# Aba "PASSAGENS" (VGP) — controle de reservas, pagamentos e
# embarque para eventos/excursões da congregação.
#
# CORREÇÃO (v2.0) — INTEGRAÇÃO COMPLETA AO SISTEMA:
#  - Este arquivo era originalmente um app Streamlit standalone
#    (tinha seu próprio st.set_page_config() e bloco <style>, e se
#    conectava a um projeto Firestore separado, "bancowendley").
#    Isso quebrava a integração de duas formas:
#      1) st.set_page_config() só pode ser chamado UMA VEZ por app —
#         como o main.py já chama, essa segunda chamada aqui geraria
#         erro do Streamlit.
#      2) Rodava num banco de dados diferente do resto do sistema
#         (bancowendley em vez de wendleydesenvolvimento), então os
#         dados de passageiros ficavam isolados dos outros módulos.
#    Corrigido: removido o set_page_config() e o <style> duplicados
#    (o estilo.py central já cobre isso), e trocado o Firestore
#    próprio pelo inicializar_db() de database.py — o mesmo banco
#    usado por todo o resto do app.
#    ATENÇÃO: como o banco muda, dados que existiam no projeto antigo
#    (bancowendley) não aparecem automaticamente aqui — são bancos
#    físicos diferentes. Use o bloco "Importar Passageiros de
#    Planilha" (já existente neste arquivo) para trazê-los de volta,
#    se necessário.
#
#  - As abas (Reserva & Pagamentos / Chamada de Embarque / Ajustes)
#    usavam st.tabs(), que perde a aba selecionada em qualquer rerun
#    — e aqui quase toda ação causa rerun (confirmar reserva, marcar
#    embarque, salvar no diálogo de gerenciar reserva, importar
#    planilha). Trocado por abas_persistentes() (tabs_persistentes.py).
#
# CORREÇÃO (v2.1) — EVENTO NÃO ACEITAVA EDIÇÃO DE VALOR/CUSTO:
#  - Não existia NENHUMA forma de editar um evento já criado (valor
#    da passagem, custo do ônibus, etc.) — só era possível CRIAR um
#    evento novo ou ARQUIVAR o existente. Por isso qualquer alteração
#    feita "no valor" de um evento ativo simplesmente não tinha para
#    onde ser gravada. Adicionada atualizar_evento() + bloco "Editar
#    Evento Atual" na aba Ajustes.
#  - Adicionado o campo "custo_onibus" (o quanto a viação cobra por
#    ônibus fretado, ex. R$ 1.770,00), separado do "valor" (preço da
#    passagem cobrado do passageiro). São conceitos diferentes:
#    um é o que você RECEBE por passageiro, outro é o que você PAGA
#    pra empresa por veículo contratado.
#  - Cabeçalho agora mostra: nº de ônibus contratados, custo total da
#    frota e quanto falta sair do seu bolso se o evento fechar hoje.
# =============================================================
import os
import sys
import io
import time
import math
import ast
from collections import Counter
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import inicializar_db
from tabs_persistentes import abas_persistentes

CAPACIDADE = 46
GRUPOS_PADRAO = ["Rosas", "Engenho", "Cohab", "Geral"]
CUSTO_ONIBUS_PADRAO = 1770.00  # valor cobrado pela viação por ônibus fretado

# =========================================================
# DADOS
# =========================================================

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

def criar_evento(nome, datas, valor_passagem, custo_onibus=CUSTO_ONIBUS_PADRAO):
    db = inicializar_db()
    if db:
        id_evento = f"{nome.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
        db.collection("eventos").document(id_evento).set({
            "nome": nome, "datas": datas, "valor": valor_passagem,
            "custo_onibus": custo_onibus,
            "status": "ativo", "criado_em": datetime.now(),
            "frotas": {dia: 1 for dia in datas}
        })
        return id_evento

def atualizar_evento(id_evento, valor_passagem=None, custo_onibus=None):
    """Atualiza campos de um evento JÁ EXISTENTE (valor da passagem e/ou
    custo por ônibus). Antes desta função não havia NENHUM jeito de
    persistir alterações num evento ativo — só criar um novo ou
    arquivar o atual. Isso é o que faltava para 'gravar' esse tipo de
    ajuste.
    Observação: alterar o valor aqui vale só para novas reservas e para
    o cálculo de custo total da frota; passageiros já cadastrados
    mantêm o valor_total que foi gravado no momento da reserva (assim
    como já acontece ao editar uma reserva individual)."""
    db = inicializar_db()
    if not db:
        return False
    dados = {}
    if valor_passagem is not None:
        dados["valor"] = valor_passagem
    if custo_onibus is not None:
        dados["custo_onibus"] = custo_onibus
    if not dados:
        return False
    db.collection("eventos").document(id_evento).update(dados)
    return True

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
    if not db:
        return []
    return [p.to_dict() for p in db.collection("eventos").document(id_evento).collection("passageiros").stream()]

def carregar_eventos():
    db = inicializar_db()
    if not db: return {}
    return {doc.id: doc.to_dict() for doc in db.collection("eventos").where("status", "==", "ativo").stream()}

# =========================================================
# IMPORTAÇÃO DE PLANILHA (evento antigo → Firestore novo)
# =========================================================
# A planilha aceita é a mesma exportada pela própria aba "Exportar Dados"
# do sistema (colunas: grupo, cpf, nome, valor_pago, embarcou, valor_total,
# dias_onibus, rg, pago). "dias_onibus" vem como texto no formato
# "[{'bus': 1, 'dia': 'Sábado'}, ...]" — por isso usamos ast.literal_eval
# para transformar de volta em lista de dicionários.

def _parse_dias_onibus(valor):
    """Converte a coluna 'dias_onibus' (string tipo lista de dict) de volta
    para lista de dicts [{'dia':..., 'bus':...}, ...]. Tolerante a células
    vazias, NaN ou já-lista."""
    if isinstance(valor, list):
        return valor
    if valor is None:
        return []
    try:
        if pd.isna(valor):
            return []
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if not texto or texto == "[]":
        return []
    try:
        parsed = ast.literal_eval(texto)
        if isinstance(parsed, list):
            return [v for v in parsed if isinstance(v, dict) and v.get("dia")]
    except Exception:
        pass
    return []

def _texto_ou_vazio(valor) -> str:
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()

def detectar_datas_frotas_valor(df_import: pd.DataFrame):
    """Varre a planilha e descobre sozinho: quais dias aparecem, quantos
    ônibus (frotas) cada dia teve, e qual foi o valor cobrado por dia de
    passagem (o mais comum entre as linhas preenchidas)."""
    datas_encontradas = []
    frotas = {}
    valores_por_dia = []
    for _, row in df_import.iterrows():
        dias = _parse_dias_onibus(row.get("dias_onibus"))
        vt = row.get("valor_total") or 0
        try:
            vt = float(vt)
        except (TypeError, ValueError):
            vt = 0.0
        if dias and vt:
            valores_por_dia.append(round(vt / len(dias), 2))
        for v in dias:
            dia = v.get("dia")
            bus = v.get("bus", 1) or 1
            if dia and dia not in datas_encontradas:
                datas_encontradas.append(dia)
            if dia:
                frotas[dia] = max(frotas.get(dia, 1), int(bus))
    valor_padrao = Counter(valores_por_dia).most_common(1)[0][0] if valores_por_dia else 50.0
    return datas_encontradas, frotas, valor_padrao

def linha_para_passageiro(row):
    """Converte uma linha da planilha num dict de passageiro pronto para
    salvar_passageiro(). Retorna None se a linha não tiver nome (linha
    vazia/decorativa que às vezes sobra na exportação)."""
    nome = _texto_ou_vazio(row.get("nome"))
    if not nome:
        return None
    grupo = _texto_ou_vazio(row.get("grupo")) or "Geral"
    if grupo not in GRUPOS_PADRAO:
        grupo = "Geral"
    pago_raw = row.get("pago")
    embarcou_raw = row.get("embarcou")
    try:
        pago = bool(pago_raw) if not pd.isna(pago_raw) else False
    except (TypeError, ValueError):
        pago = bool(pago_raw)
    try:
        embarcou = bool(embarcou_raw) if not pd.isna(embarcou_raw) else False
    except (TypeError, ValueError):
        embarcou = bool(embarcou_raw)
    try:
        valor_total = float(row.get("valor_total") or 0)
    except (TypeError, ValueError):
        valor_total = 0.0
    try:
        valor_pago = float(row.get("valor_pago") or 0)
    except (TypeError, ValueError):
        valor_pago = 0.0
    return {
        "nome": nome,
        "rg": _texto_ou_vazio(row.get("rg")),
        "cpf": _texto_ou_vazio(row.get("cpf")),
        "grupo": grupo,
        "dias_onibus": _parse_dias_onibus(row.get("dias_onibus")),
        "pago": pago,
        "embarcou": embarcou,
        "valor_total": valor_total,
        "valor_pago": valor_pago,
    }

def importar_evento_de_planilha(nome_evento: str, datas: list, valor_passagem: float,
                                 frotas: dict, passageiros: list, custo_onibus: float = CUSTO_ONIBUS_PADRAO):
    """Cria um evento NOVO no Firestore e importa cada passageiro da
    planilha antiga para dentro dele — é o 'subir os dados' do relatório
    antigo para o sistema novo."""
    db = inicializar_db()
    if not db:
        return None, 0
    id_evento = f"{nome_evento.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    db.collection("eventos").document(id_evento).set({
        "nome": nome_evento, "datas": datas, "valor": valor_passagem,
        "custo_onibus": custo_onibus,
        "status": "ativo", "criado_em": datetime.now(),
        "frotas": frotas or {d: 1 for d in datas},
        "origem": "importado_planilha",
    })
    qtd = 0
    for pax in passageiros:
        salvar_passageiro(id_evento, pax)
        qtd += 1
    return id_evento, qtd

# =========================================================
# DIÁLOGO
# =========================================================

@st.dialog("Gerenciar Reserva")
def gerenciar_pax_dialog(pax, id_evento, evento_atual):
    st.markdown("### 👤 " + pax['nome'])
    total_devido    = pax.get('valor_total', len(pax.get('dias_onibus', [])) * evento_atual['valor'])
    pago_atualmente = pax.get('valor_pago', 0.0)
    c1, c2 = st.columns(2)
    c1.metric("Total da Passagem", "R$ %.2f" % total_devido)
    c2.metric("Saldo Pendente",    "R$ %.2f" % (total_devido - pago_atualmente), delta_color="inverse")

    if pax.get('pago') or pax.get('embarcou'):
        tags = []
        if pax.get('pago'): tags.append("💰 pago")
        if pax.get('embarcou'): tags.append("🚌 embarcado")
        st.caption("Situação atual: " + " · ".join(tags) +
                   " — você pode alterar tudo abaixo (estornar pagamento, cancelar embarque, "
                   "trocar viagens etc.) e salvar normalmente.")

    with st.form("edit_pax_final"):
        nome = st.text_input("Nome", value=pax['nome'])
        cc1, cc2 = st.columns(2)
        rg  = cc1.text_input("RG",  value=pax.get('rg', ""))
        cpf = cc2.text_input("CPF", value=pax.get('cpf', ""))
        grupos = GRUPOS_PADRAO
        g_atual = pax.get('grupo', 'Geral')
        grupo = st.selectbox("Grupo", grupos, index=grupos.index(g_atual) if g_atual in grupos else 3)

        st.divider()
        st.markdown("**💰 Ajustar Pagamento**")
        st.caption("Use valor positivo para registrar um novo recebimento, ou "
                   "**negativo** para devolver/estornar valor já pago.")
        cr1, cr2, cr3 = st.columns(3)
        valor_recebido = cr1.number_input("Recebido agora (± )", value=0.0, step=5.0,
                                          help="Positivo = recebendo agora. Negativo = devolvendo dinheiro ao passageiro.")
        valor_entregue = cr2.number_input("Troco entregue", min_value=0.0, value=0.0)
        if valor_entregue > 0 and valor_recebido > 0:
            cr3.success("Troco: R$ %.2f" % max(valor_entregue - valor_recebido, 0))
        if valor_recebido < 0:
            cr3.warning("Estornando R$ %.2f" % abs(valor_recebido))

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
        novo_total_pago = max(pago_atualmente + valor_recebido, 0.0)
        pago     = st.toggle("💰 Pagamento quitado", value=pax.get('pago', False))
        embarque = st.toggle("🚌 Embarcou",           value=pax.get('embarcou', False))
        st.caption("Os toggles acima refletem o estado salvo — desmarque para cancelar "
                   "embarque ou reabrir como pendente após um estorno.")

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

# =========================================================
# CABEÇALHO — usa components.html para garantir render
# =========================================================

def renderizar_cabecalho(evento, df, id_sel, pode_editar=True):
    total      = len(df) if not df.empty else 0
    pagos      = int(df['pago'].sum())         if not df.empty and 'pago'      in df.columns else 0
    pendente   = total - pagos
    arrecadado = float(df['valor_pago'].sum()) if not df.empty and 'valor_pago' in df.columns else 0.0

    # "A Receber" tem que usar EXATAMENTE a mesma regra da aba Pendentes:
    # soma o saldo em aberto só de quem está com 'pago' == False. Antes isso
    # era calculado em cima de TODAS as linhas (valor_total - valor_pago),
    # o que inflava o número sempre que alguém marcado como pago não tinha
    # 'valor_pago' gravado (ex.: dado antigo/importado) — nesse caso o campo
    # vira 0 e o valor dele inteiro era contado como "a receber" por engano,
    # mesmo já estando quitado.
    a_receber = 0.0
    if not df.empty and 'pago' in df.columns:
        pendentes_df = df[df['pago'] == False]
        for _, r in pendentes_df.iterrows():
            v_total = float(r.get('valor_total') or 0) or (len(r.get('dias_onibus') or []) * evento['valor'])
            v_pago  = float(r.get('valor_pago') or 0)
            a_receber += max(v_total - v_pago, 0)

    pct        = round((pagos / total) * 100) if total else 0
    datas_str  = ", ".join(evento.get("datas", []))
    nome_ev    = evento.get('nome', '')

    # ---- Custo da frota contratada x arrecadação (o que importa pra
    #      responder "quanto falta sair do meu bolso se eu fechar hoje") ----
    total_onibus     = sum(evento.get('frotas', {}).get(d, 1) for d in evento.get('datas', []))
    custo_por_onibus = evento.get('custo_onibus', CUSTO_ONIBUS_PADRAO)
    custo_total_frota = total_onibus * custo_por_onibus
    # "Fechar hoje" = parar de vender passagem nova, mas ainda cobrar quem já
    # reservou (arrecadado + a_receber = tudo que está garantido). O que
    # faltar disso pro custo da frota é o que sai do bolso.
    saldo_se_fechar_hoje = custo_total_frota - (arrecadado + a_receber)  # >0 = sai do bolso; <=0 = sobra

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
            cor      = "#f87171" if qtd >= CAPACIDADE else ("#fbbf24" if perc > 80 else "#4ade80")
            lotado   = "<div style='font-size:0.6rem;color:#f87171;font-weight:700;margin-top:3px;'>🔴 Lotado</div>" \
                       if qtd >= CAPACIDADE else ""
            frotas_html += (
                "<div style='background:rgba(255,255,255,0.09);border:1px solid rgba(255,255,255,0.15);"
                "border-radius:10px;padding:11px 13px;min-width:130px;flex:1;'>"
                "<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px;'>"
                "<span style='font-size:0.72rem;font-weight:700;color:white;'>" + dia + " · Ônibus " + str(b) + "</span>"
                "<span style='font-size:0.65rem;font-weight:600;color:rgba(255,255,255,0.5);'>" + str(perc) + "%</span>"
                "</div>"
                "<div style='background:rgba(255,255,255,0.14);border-radius:4px;height:6px;overflow:hidden;margin-bottom:5px;'>"
                "<div style='width:" + str(perc) + "%;height:100%;background:" + cor + ";border-radius:4px;'></div>"
                "</div>"
                "<div style='font-size:0.63rem;color:rgba(255,255,255,0.42);'>" + str(qtd) + " / " + str(CAPACIDADE) + " passageiros</div>"
                + lotado +
                "</div>"
            )
            if qtd >= CAPACIDADE and b == n_frotas:
                needs_add[dia] = b + 1

    # ---- Montar HTML dos KPIs ----
    def kpi(lbl, val, sub, cor="white"):
        return (
            "<div style='background:rgba(255,255,255,0.11);border:1px solid rgba(255,255,255,0.18);"
            "border-radius:11px;padding:12px 14px;flex:1;min-width:110px;'>"
            "<div style='font-size:0.62rem;color:rgba(255,255,255,0.55);text-transform:uppercase;"
            "letter-spacing:0.09em;font-weight:700;margin-bottom:5px;'>" + lbl + "</div>"
            "<div style='font-size:1.4rem;font-weight:700;color:" + cor + ";line-height:1;'>" + str(val) + "</div>"
            "<div style='font-size:0.65rem;color:rgba(255,255,255,0.4);margin-top:3px;'>" + sub + "</div>"
            "</div>"
        )

    lista_kpis = [
        kpi("Reservas",   total,                             "passageiros"),
        kpi("Pagos",      pagos,                             str(pct) + "% confirmados", "#a8e6cf"),
        kpi("Pendentes",  pendente,                          "aguardando",                "#ffd166"),
        kpi("Arrecadado", "R$ {:,.0f}".format(arrecadado),  "recebido",                  "#a8e6cf"),
        kpi("A Receber",  "R$ {:,.0f}".format(a_receber),   "em aberto",                 "#ffd166"),
        kpi("Custo da Frota", "R$ {:,.0f}".format(custo_total_frota),
            str(total_onibus) + " ônibus × R$ {:,.0f}".format(custo_por_onibus), "white"),
        kpi("Se Fechar Hoje",
            "R$ {:,.0f}".format(abs(saldo_se_fechar_hoje)),
            "do seu bolso" if saldo_se_fechar_hoje > 0 else "de sobra / cobre o custo",
            "#f87171" if saldo_se_fechar_hoje > 0 else "#a8e6cf"),
    ]
    kpis_html = "".join(lista_kpis)

    # ---- Calcular altura conservadora (pior caso = mobile 1 coluna) ----
    n_frotas_total       = sum(evento.get('frotas', {}).get(d, 1) for d in evento.get('datas', []))
    linhas_frota_mobile  = n_frotas_total
    linhas_kpi_mobile    = math.ceil(len(lista_kpis) / 2)  # ~2 kpis por linha no mobile
    altura = (
        72
        + linhas_kpi_mobile * 78
        + 50
        + linhas_frota_mobile * 82
        + 56
    )

    # ---- HTML completo com JS de auto-resize ----
    html = (
        "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap' rel='stylesheet'>"
        "<style>* { box-sizing:border-box; } body { background:transparent; overflow:hidden; margin:0; }</style>"
        "<div id='root' style='font-family:Inter,sans-serif;"
        "background:linear-gradient(135deg,#1a3a6b 0%,#2456a4 100%);"
        "border-radius:16px;padding:24px 24px 20px;color:white;'>"

        "<div style='font-size:1.5rem;font-weight:700;letter-spacing:-0.5px;color:white;'>"
        "🕊️ " + nome_ev +
        "</div>"
        "<div style='font-size:0.8rem;color:rgba(255,255,255,0.6);margin-top:4px;font-weight:400;'>"
        "Controle de Passagens · " + datas_str +
        "</div>"

        "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));"
        "gap:10px;margin-top:16px;'>"
        + kpis_html +
        "</div>"

        "<div style='border-top:1px solid rgba(255,255,255,0.15);margin:16px 0 14px;'></div>"

        "<div style='font-size:0.6rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;"
        "color:rgba(255,255,255,0.45);margin-bottom:10px;'>Ocupação por Frota</div>"
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

    # Botões de adicionar ônibus (fora do HTML) — só quem pode editar
    if needs_add and pode_editar:
        cols = st.columns(len(needs_add))
        for idx, (dia, prox) in enumerate(needs_add.items()):
            with cols[idx]:
                if st.button("➕ Adicionar Ônibus " + str(prox) + " — " + dia, key="hdr_add_" + dia):
                    adicionar_novo_onibus(id_sel, dia)
                    st.rerun()


# =========================================================
# EXPORTAÇÃO — LISTA DE CHAMADA (Excel)
# =========================================================

def gerar_excel_chamada(df_pagos: pd.DataFrame) -> bytes:
    """Monta a planilha da lista de chamada a partir dos passageiros com
    pagamento confirmado: uma linha por pessoa, com grupo, viagens e status
    de embarque — pronta pra imprimir e usar no dia do evento. Só entram
    aqui quem já pagou, seguindo a mesma regra da própria aba de Chamada
    (quem não pagou nem aparece na lista de embarque)."""
    linhas = []
    for _, p in df_pagos.sort_values(['grupo', 'nome']).iterrows():
        viagens_txt = ", ".join(
            f"{v.get('dia')} (Ônibus {v.get('bus')})" for v in (p.get('dias_onibus') or [])
        )
        linhas.append({
            "Grupo": p.get('grupo', 'Geral'),
            "Nome": p.get('nome', ''),
            "RG": p.get('rg', ''),
            "Viagens": viagens_txt,
            "Embarcou": "Sim" if p.get('embarcou') else "Não",
        })
    df_export = pd.DataFrame(linhas)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Chamada de Embarque')
        worksheet = writer.sheets['Chamada de Embarque']
        for i, col in enumerate(df_export.columns):
            maior_valor = df_export[col].astype(str).map(len).max() if not df_export.empty else 0
            worksheet.set_column(i, i, max(maior_valor, len(col)) + 2)
    return output.getvalue()


# =========================================================
# PRINCIPAL
# =========================================================

def exibir_modulo_passagens(pode_editar=True):
    eventos_ativos = carregar_eventos()

    if not eventos_ativos:
        components.html(
            "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap' rel='stylesheet'>"
            "<div style='font-family:Inter,sans-serif;background:linear-gradient(135deg,#1a3a6b 0%,#2456a4 100%);"
            "border-radius:16px;padding:24px;color:white;'>"
            "<div style='font-size:1.5rem;font-weight:700;color:white;'>🕊️ VGP Passagens</div>"
            "<div style='font-size:0.82rem;color:rgba(255,255,255,0.6);margin-top:4px;'>"
            "Nenhum evento ativo" + ("" if pode_editar else " — fale com um administrador") +
            "</div></div>",
            height=110
        )
        if not pode_editar:
            st.info("🔒 Você não tem permissão para criar eventos. Fale com um administrador.")
            return
        with st.form("criar_evento_inicial"):
            st.subheader("Novo Evento")
            n_ev = st.text_input("Nome do Evento (ex: Assembleia Março)")
            v_ev = st.number_input("Valor da Passagem por passageiro/dia (R$)", min_value=0.0, value=50.0, step=5.0)
            c_ev = st.number_input("Custo do Ônibus contratado (R$ por ônibus/dia)",
                                   min_value=0.0, value=CUSTO_ONIBUS_PADRAO, step=10.0,
                                   help="Quanto a viação cobra por cada ônibus fretado. Usado para calcular "
                                        "quanto falta sair do seu bolso se o evento fechar hoje.")
            d_ev = st.multiselect("Dias de Operação", ["Sexta", "Sábado", "Domingo"])
            if st.form_submit_button("🚀 Criar Evento", type="primary"):
                if n_ev and d_ev:
                    criar_evento(n_ev, d_ev, v_ev, c_ev)
                    st.rerun()
                else:
                    st.error("Informe o nome e ao menos um dia.")

        st.divider()
        _bloco_importar_planilha()
        return

    # Seletor de evento
    c1, c2 = st.columns([4, 1])
    with c2:
        id_sel = st.selectbox("", list(eventos_ativos.keys()),
                              format_func=lambda x: eventos_ativos[x]['nome'],
                              label_visibility="collapsed")

    evento    = eventos_ativos[id_sel]
    pax_lista = carregar_passageiros(id_sel)
    df        = pd.DataFrame(pax_lista)

    if not df.empty:
        for col, default in [('grupo','Geral'),('pago',False),('valor_pago',0.0),
                              ('valor_total',0.0),('embarcou',False)]:
            if col not in df.columns: df[col] = default
            df[col] = df[col].fillna(default)

    # CABEÇALHO
    renderizar_cabecalho(evento, df, id_sel, pode_editar)

    # ABAS
    idx_ativa = abas_persistentes([
        "📝 Reserva & Pagamentos",
        "🚌 Chamada de Embarque",
        "⚙️ Ajustes",
    ], key="abas_passagens")

    # -------------------------------------------------------
    # ABA 1: RESERVA + PENDENTES
    # -------------------------------------------------------
    if idx_ativa == 0:
        col_form, col_pend = st.columns([1, 1], gap="large")

        with col_form:
            st.markdown("**Nova Reserva**")
            if not pode_editar:
                st.info("🔒 Você tem acesso somente leitura — não é possível criar novas reservas.")
            else:
                busca_nome = st.text_input("🔍 Buscar cadastro existente", placeholder="Digite parte do nome...")
                mestre = buscar_pessoa_central(busca_nome) if busca_nome else None
                if mestre:
                    st.success("✅ Cadastro encontrado: **" + mestre['nome'] + "**")

                with st.form("reserva_form", clear_on_submit=True):
                    nome_f  = st.text_input("Nome Completo *", value=mestre['nome'] if mestre else busca_nome)
                    ci1, ci2 = st.columns(2)
                    rg_f  = ci1.text_input("RG",  value=mestre.get('rg',  '') if mestre else "")
                    cpf_f = ci2.text_input("CPF", value=mestre.get('cpf', '') if mestre else "")
                    grupo_f = st.selectbox("Grupo / Localização", GRUPOS_PADRAO)
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

        with col_pend:
            st.markdown("**Pagamentos Pendentes**")
            if not df.empty:
                pendentes = df[df['pago'] == False].sort_values('nome')
                if pendentes.empty:
                    st.markdown(
                        "<div style='text-align:center;padding:40px 0;color:#94a3b8;'>"
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
                        ci, cb = st.columns([5, 1])
                        with ci:
                            st.markdown(
                                "<div style='background:white;border:1px solid #e8eaf0;"
                                "border-left:4px solid #ef4444;border-radius:10px;"
                                "padding:10px 13px;margin-bottom:7px;"
                                "display:flex;justify-content:space-between;align-items:center;'>"
                                "<div>"
                                "<div style='font-weight:600;font-size:0.87rem;color:#1e293b;'>" + r['nome'] + "</div>"
                                "<div style='font-size:0.74rem;color:#94a3b8;margin-top:2px;'>"
                                "📍 " + grp_tag + " · " + str(len(r.get('dias_onibus') or [])) + " viagem(ns)</div>"
                                "</div>"
                                "<div style='font-weight:700;font-size:0.9rem;color:#ef4444;"
                                "white-space:nowrap;margin-left:8px;'>"
                                "– R$ {:,.2f}".format(v_falta) + "</div>"
                                "</div>", unsafe_allow_html=True)
                        with cb:
                            if pode_editar and st.button("✏️", key="ed_pe_" + r['nome'], help="Editar / Receber pagamento"):
                                gerenciar_pax_dialog(r.to_dict(), id_sel, evento)

                    st.markdown(
                        "<div style='background:#fef9c3;border:1px solid #fde68a;border-radius:8px;"
                        "padding:10px 14px;margin-top:10px;font-size:0.85rem;"
                        "display:flex;justify-content:space-between;align-items:center;'>"
                        "<strong>Total em aberto:</strong>"
                        "<span style='font-weight:700;color:#92400e;'>R$ {:,.2f}</span>".format(total_pend) +
                        "</div>", unsafe_allow_html=True)
            else:
                st.info("Nenhuma reserva lançada ainda.")

    # -------------------------------------------------------
    # ABA 2: CHAMADA
    # -------------------------------------------------------
    elif idx_ativa == 1:
        if df.empty:
            st.info("Nenhuma reserva para exibir.")
        else:
            df_pagos = df[df['pago'] == True].copy()
            if df_pagos.empty:
                st.markdown(
                    "<div style='text-align:center;padding:60px 0;color:#94a3b8;'>"
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
                    "<div style='background:white;border:1px solid #e8eaf0;border-radius:10px;"
                    "padding:12px 18px;flex:1;min-width:110px;'>"
                    "<div style='font-size:0.62rem;color:#94a3b8;text-transform:uppercase;"
                    "letter-spacing:.08em;font-weight:700;'>Confirmados</div>"
                    "<div style='font-size:1.5rem;font-weight:700;color:#1a3a6b;'>" + str(tot_p) + "</div></div>"

                    "<div style='background:white;border:1px solid #e8eaf0;border-left:3px solid #22c55e;"
                    "border-radius:10px;padding:12px 18px;flex:1;min-width:110px;'>"
                    "<div style='font-size:0.62rem;color:#94a3b8;text-transform:uppercase;"
                    "letter-spacing:.08em;font-weight:700;'>Embarcados</div>"
                    "<div style='font-size:1.5rem;font-weight:700;color:#22c55e;'>" + str(emb_t) + "</div></div>"

                    "<div style='background:white;border:1px solid #e8eaf0;border-left:3px solid #f59e0b;"
                    "border-radius:10px;padding:12px 18px;flex:1;min-width:110px;'>"
                    "<div style='font-size:0.62rem;color:#94a3b8;text-transform:uppercase;"
                    "letter-spacing:.08em;font-weight:700;'>Aguardando</div>"
                    "<div style='font-size:1.5rem;font-weight:700;color:#f59e0b;'>" + str(falt_t) + "</div></div>"
                    "</div>", unsafe_allow_html=True)

                cexp, _ = st.columns([1, 2])
                with cexp:
                    st.download_button(
                        "📥 Baixar Lista de Chamada (Excel)",
                        gerar_excel_chamada(df_pagos),
                        "chamada_embarque_" + evento['nome'].lower().replace(' ', '_') + ".xlsx",
                        use_container_width=True
                    )
                st.write("")

                for grp in sorted(df_pagos['grupo'].unique()):
                    df_grp = df_pagos[df_pagos['grupo'] == grp]
                    n_grp  = len(df_grp)
                    e_grp  = int(df_grp['embarcou'].sum())
                    with st.expander("📍 " + grp.upper() + "  —  " + str(e_grp) + "/" + str(n_grp) + " embarcados", expanded=True):
                        cf, co = st.columns(2)
                        with cf:
                            st.markdown("<div style='font-size:0.7rem;font-weight:700;text-transform:uppercase;"
                                        "letter-spacing:.08em;color:#f59e0b;margin-bottom:8px;'>⏳ Aguardando</div>",
                                        unsafe_allow_html=True)
                            for _, p in df_grp[df_grp['embarcou'] == False].sort_values('nome').iterrows():
                                cn, ce, cb = st.columns([4, 1, 1])
                                cn.markdown("<div style='font-weight:500;font-size:0.87rem;color:#1e293b;"
                                            "padding:6px 0;border-bottom:1px solid #f1f5f9;'>" + p['nome'] + "</div>",
                                            unsafe_allow_html=True)
                                if pode_editar and ce.button("✏️", key="ed_wait_" + grp + "_" + p['nome'], help="Editar / estornar pagamento"):
                                    gerenciar_pax_dialog(p.to_dict(), id_sel, evento)
                                if cb.button("✅", key="emb_" + grp + "_" + p['nome'], help="Confirmar embarque"):
                                    atualizar_embarque(id_sel, p.to_dict(), True); st.rerun()
                        with co:
                            st.markdown("<div style='font-size:0.7rem;font-weight:700;text-transform:uppercase;"
                                        "letter-spacing:.08em;color:#22c55e;margin-bottom:8px;'>🟢 Embarcados</div>",
                                        unsafe_allow_html=True)
                            for _, p in df_grp[df_grp['embarcou'] == True].sort_values('nome').iterrows():
                                cn, ce, cb = st.columns([4, 1, 1])
                                cn.markdown("<div style='font-weight:500;font-size:0.87rem;color:#94a3b8;"
                                            "text-decoration:line-through;padding:6px 0;"
                                            "border-bottom:1px solid #f1f5f9;'>" + p['nome'] + "</div>",
                                            unsafe_allow_html=True)
                                if pode_editar and ce.button("✏️", key="ed_board_" + grp + "_" + p['nome'], help="Editar / estornar pagamento"):
                                    gerenciar_pax_dialog(p.to_dict(), id_sel, evento)
                                if cb.button("↩️", key="rem_" + grp + "_" + p['nome'], help="Cancelar embarque"):
                                    atualizar_embarque(id_sel, p.to_dict(), False); st.rerun()

    # -------------------------------------------------------
    # ABA 3: AJUSTES
    # -------------------------------------------------------
    elif idx_ativa == 2:
        ca1, ca2 = st.columns(2)
        with ca1:
            st.markdown("**Novo Evento**")
            if not pode_editar:
                st.caption("🔒 Somente leitura.")
            else:
                with st.form("criar_evento_adj"):
                    n_ev = st.text_input("Nome do Evento")
                    v_ev = st.number_input("Valor da Passagem por passageiro/dia (R$)", min_value=0.0, value=50.0, step=5.0)
                    c_ev = st.number_input("Custo do Ônibus contratado (R$ por ônibus/dia)",
                                           min_value=0.0, value=CUSTO_ONIBUS_PADRAO, step=10.0)
                    d_ev = st.multiselect("Dias de Operação", ["Sexta", "Sábado", "Domingo"])
                    if st.form_submit_button("🚀 Criar Evento", type="primary"):
                        if n_ev and d_ev:
                            criar_evento(n_ev, d_ev, v_ev, c_ev); st.rerun()
            st.divider()
            st.markdown("**Exportar Dados**")
            if not df.empty:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Passageiros')
                st.download_button("📥 Baixar Excel", output.getvalue(),
                                   "lista_" + id_sel + ".xlsx", use_container_width=True)
        with ca2:
            st.markdown("**Editar Evento Atual**")
            if not pode_editar:
                st.caption("🔒 Somente leitura.")
            else:
                with st.form("editar_evento_atual"):
                    st.caption("Ajusta valor da passagem e/ou custo do ônibus de **" + evento['nome'] + "**. "
                               "Reservas já lançadas mantêm o valor com que foram gravadas.")
                    novo_valor  = st.number_input("Valor da Passagem por passageiro/dia (R$)",
                                                  min_value=0.0, value=float(evento.get('valor', 50.0)), step=5.0)
                    novo_custo  = st.number_input("Custo do Ônibus contratado (R$ por ônibus/dia)",
                                                  min_value=0.0,
                                                  value=float(evento.get('custo_onibus', CUSTO_ONIBUS_PADRAO)),
                                                  step=10.0)
                    if st.form_submit_button("💾 Salvar Alterações do Evento", type="primary", use_container_width=True):
                        atualizar_evento(id_sel, valor_passagem=novo_valor, custo_onibus=novo_custo)
                        st.success("Evento atualizado!")
                        st.rerun()

            st.divider()
            st.markdown("**Encerrar Evento**")
            if not pode_editar:
                st.caption("🔒 Somente leitura.")
            else:
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

        if pode_editar:
            st.divider()
            _bloco_importar_planilha()


# =========================================================
# BLOCO: Importar planilha de evento antigo
# =========================================================
def _bloco_importar_planilha():
    with st.expander("📤 Importar Passageiros de Planilha (evento antigo)"):
        st.caption(
            "Aceita o arquivo **.xlsx** exportado pelo próprio sistema (aba 'Exportar Dados' → "
            "'📥 Baixar Excel'), com as colunas: grupo, cpf, nome, valor_pago, embarcou, "
            "valor_total, dias_onibus, rg, pago. Um evento NOVO será criado aqui com todos "
            "os passageiros da planilha já lançados (reserva, pagamento e embarque preservados)."
        )
        arquivo = st.file_uploader("Selecione a planilha (.xlsx)", type=["xlsx"], key="import_upload")
        if not arquivo:
            return

        try:
            df_imp = pd.read_excel(arquivo)
        except Exception as e:
            st.error(f"Não consegui ler o arquivo: {e}")
            return

        colunas_necessarias = {"nome", "dias_onibus"}
        faltando = colunas_necessarias - set(df_imp.columns)
        if faltando:
            st.error("Planilha fora do formato esperado. Faltam colunas: " + ", ".join(sorted(faltando)))
            return

        datas_det, frotas_det, valor_det = detectar_datas_frotas_valor(df_imp)
        linhas_validas = [p for p in (linha_para_passageiro(r) for _, r in df_imp.iterrows()) if p]

        if not linhas_validas:
            st.warning("Nenhum passageiro com nome válido foi encontrado nessa planilha.")
            return

        st.markdown(f"**{len(linhas_validas)}** passageiro(s) válido(s) encontrado(s) "
                    f"(de {len(df_imp)} linha(s) na planilha).")

        nome_imp = st.text_input("Nome do Evento a criar", value="Evento Importado",
                                 key="imp_nome_evento")
        datas_imp = st.multiselect("Dias de Operação (detectados automaticamente)",
                                   ["Sexta", "Sábado", "Domingo"],
                                   default=datas_det, key="imp_dias")
        valor_imp = st.number_input("Valor da Passagem por dia (R$) — detectado automaticamente",
                                    min_value=0.0, value=float(valor_det), step=5.0,
                                    key="imp_valor")
        custo_imp = st.number_input("Custo do Ônibus contratado (R$ por ônibus/dia)",
                                    min_value=0.0, value=CUSTO_ONIBUS_PADRAO, step=10.0,
                                    key="imp_custo")

        with st.expander("👁️ Pré-visualizar dados que serão importados"):
            st.dataframe(pd.DataFrame(linhas_validas), use_container_width=True)

        if st.button("📤 Importar para Novo Evento", type="primary",
                     use_container_width=True, key="btn_importar_planilha"):
            if not nome_imp.strip() or not datas_imp:
                st.error("Informe o nome do evento e pelo menos um dia de operação.")
            else:
                frotas_final = {d: frotas_det.get(d, 1) for d in datas_imp}
                id_novo, qtd = importar_evento_de_planilha(
                    nome_imp.strip(), datas_imp, valor_imp, frotas_final, linhas_validas, custo_imp
                )
                if id_novo:
                    st.success(f"✅ Evento **{nome_imp}** criado com **{qtd}** passageiro(s) "
                               f"importado(s) da planilha!")
                    st.balloons()
                    time.sleep(1.2)
                    st.rerun()
                else:
                    st.error("Não foi possível conectar ao banco de dados para importar.")
