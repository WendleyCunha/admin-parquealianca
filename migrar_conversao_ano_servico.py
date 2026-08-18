# =============================================================
# migrar_convencao_ano_servico.py
#
# Script de migração ÚNICA — converte os registros já gravados no
# Firestore (relatorios_parque_alianca.mes_referencia e
# membros_v2.mes_inicio) da convenção ANTIGA (ano civil de cada mês)
# para a NOVA convenção (ano de encerramento do ano de serviço).
#
# O QUE MUDA:
#   Setembro / Outubro / Novembro / Dezembro → ganham +1 no ano.
#     Ex.: "SETEMBRO 2024" vira "SETEMBRO 2025"
#          "OUTUBRO 2025"  vira "OUTUBRO 2026"
#   Janeiro..Agosto → NÃO mudam (o ano deles já é o de encerramento).
#
# COMO USAR:
#   1) Rode primeiro em MODO SIMULAÇÃO (padrão) — nada é gravado, só
#      mostra o que SERIA alterado. Confira a lista com atenção.
#   2) Só depois de conferir, marque "Aplicar de verdade" e rode de
#      novo para gravar as mudanças no Firestore.
#
#   streamlit run migrar_convencao_ano_servico.py
#
# SEGURANÇA:
#   - Roda uma vez só. Depois de aplicado, pode apagar este arquivo.
#   - Não apaga nenhum documento — só reescreve o campo mes_referencia
#     (em relatorios_parque_alianca) e mes_inicio (em membros_v2) dos
#     registros que caem em Setembro/Outubro/Novembro/Dezembro.
#   - Documentos que já estiverem no formato novo (ou fora do padrão
#     "MES ANO" esperado) são listados à parte e NUNCA alterados.
# =============================================================
import json

import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account

MESES_QUE_MUDAM = {"SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"}


def _conectar():
    key_dict = json.loads(st.secrets["textkey"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    return firestore.Client(credentials=creds, project="wendleydesenvolvimento")


def _novo_rotulo(mes_ref_atual: str):
    """
    Retorna o novo rótulo se `mes_ref_atual` precisar mudar, ou None se
    não precisar (Janeiro–Agosto, ou string fora do padrão esperado).
    """
    partes = str(mes_ref_atual).strip().upper().split()
    if len(partes) != 2:
        return None
    nome_mes, ano_str = partes
    if nome_mes not in MESES_QUE_MUDAM:
        return None
    try:
        ano = int(ano_str)
    except ValueError:
        return None
    return f"{nome_mes} {ano + 1}"


def main():
    st.set_page_config(page_title="Migração — Ano de Serviço", page_icon="🔁")
    st.title("🔁 Migração de convenção: ano civil → ano de serviço")
    st.caption(
        "Setembro/Outubro/Novembro/Dezembro passam a usar o ano de "
        "encerramento do ano de serviço (ex.: SETEMBRO 2024 → SETEMBRO 2025). "
        "Janeiro–Agosto não mudam."
    )

    modo_simulacao = st.checkbox("🔒 Modo simulação (não grava nada)", value=True)
    if not modo_simulacao:
        st.error(
            "⚠️ ATENÇÃO: modo simulação DESLIGADO. Ao clicar em "
            "'Executar migração' abaixo, os dados serão alterados de verdade "
            "no Firestore. Confirme que já rodou em modo simulação antes."
        )

    if not st.button("🔎 Analisar / Executar migração", type="primary"):
        st.stop()

    db = _conectar()

    # ---- Relatórios ----
    st.markdown("### 📋 Relatórios (`relatorios_parque_alianca`)")
    docs_rel = list(db.collection("relatorios_parque_alianca").stream())
    mudancas_rel = []
    for doc in docs_rel:
        dados = doc.to_dict() or {}
        atual = dados.get("mes_referencia", "")
        novo = _novo_rotulo(atual)
        if novo and novo != atual:
            mudancas_rel.append((doc.id, atual, novo))

    if not mudancas_rel:
        st.success("Nenhum relatório precisa de alteração.")
    else:
        st.warning(f"{len(mudancas_rel)} relatório(s) serão alterados:")
        st.dataframe(
            [{"id": i[:8], "de": a, "para": n} for i, a, n in mudancas_rel],
            use_container_width=True, hide_index=True,
        )
        if not modo_simulacao:
            batch = db.batch()
            for doc_id, _, novo in mudancas_rel:
                ref = db.collection("relatorios_parque_alianca").document(doc_id)
                batch.update(ref, {"mes_referencia": novo})
            batch.commit()
            st.success(f"✅ {len(mudancas_rel)} relatório(s) atualizados no Firestore.")

    # ---- Membros (mes_inicio) ----
    st.markdown("### 👤 Membros (`membros_v2` — campo `mes_inicio`)")
    docs_mem = list(db.collection("membros_v2").stream())
    mudancas_mem = []
    for doc in docs_mem:
        dados = doc.to_dict() or {}
        atual = dados.get("mes_inicio", "")
        if not atual:
            continue
        novo = _novo_rotulo(atual)
        if novo and novo != atual:
            mudancas_mem.append((doc.id, atual, novo))

    if not mudancas_mem:
        st.success("Nenhum membro precisa de alteração em mes_inicio.")
    else:
        st.warning(f"{len(mudancas_mem)} membro(s) serão alterados:")
        st.dataframe(
            [{"membro": i, "de": a, "para": n} for i, a, n in mudancas_mem],
            use_container_width=True, hide_index=True,
        )
        if not modo_simulacao:
            batch = db.batch()
            for doc_id, _, novo in mudancas_mem:
                ref = db.collection("membros_v2").document(doc_id)
                batch.update(ref, {"mes_inicio": novo})
            batch.commit()
            st.success(f"✅ {len(mudancas_mem)} membro(s) atualizados no Firestore.")

    if modo_simulacao:
        st.info(
            "Isso foi só uma simulação — nada foi gravado. Confira as tabelas "
            "acima, desmarque 'Modo simulação' e rode de novo para aplicar de verdade."
        )


if __name__ == "__main__":
    main()
