# =============================================================
# utilitarios.py
# Funções auxiliares "puras" (sem tocar no Streamlit nem no
# Firestore diretamente) usadas por vários módulos.
#
# Origem: Seção 5 ("FUNÇÕES UTILITÁRIAS") + Seção 10
# ("PROCESSAMENTO DE DADOS") do antigo main.py monolítico.
# Nenhuma lógica original foi alterada — só o arquivo mudou.
#
# ATUALIZAÇÃO (correção — ordenação do seletor de mês):
#   Adicionada `ordenar_lista_meses`, que reaproveita a mesma chave
#   cronológica de `ordenar_df_por_mes` (extraída para
#   `_chave_ordenacao_mes`) para ordenar uma lista simples de
#   strings "MES ANO" — usada pelo seletor de mês em main.py, que
#   antes usava `sorted()` puro (ordem alfabética de texto, não
#   cronológica; ver changelog de main.py/constantes.py).
# =============================================================
import unicodedata
from difflib import SequenceMatcher
from datetime import date

import pandas as pd

from constantes import _MESES_ORDEM, categorias_lista


def normalizar_texto(texto):
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


def obter_mes_vigente_str():
    """
    [ATUALIZADO — convenção "ano de serviço"] O "ano" retornado não é mais
    o ano civil de cada mês — é o ANO DE ENCERRAMENTO do ano de serviço
    (o ano do Agosto daquele ciclo), valendo para os 12 meses inteiros,
    INCLUSIVE o Setembro que abre o ciclo. Ex.: Setembro/2026 (calendário)
    passa a ser rotulado "SETEMBRO 2027", já que ele abre o ano de serviço
    que termina em Agosto/2027. Janeiro–Agosto NÃO mudam de rótulo (já
    usavam o ano seguinte ao Setembro que os precede, que é exatamente o
    ano de encerramento do próprio ciclo deles).
    """
    meses = ["JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
             "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"]
    hoje = date.today()
    if hoje.day >= 20:
        mes_num, ano_civil = hoje.month, hoje.year
    else:
        if hoje.month == 1:
            mes_num, ano_civil = 12, hoje.year - 1
        else:
            mes_num, ano_civil = hoje.month - 1, hoje.year

    nome_mes = meses[mes_num - 1]
    # Setembro(9)–Dezembro(12) pertencem ao ano de serviço que TERMINA no
    # ano civil seguinte (ano_civil + 1). Janeiro–Agosto já pertencem ao
    # ano de serviço que termina no próprio ano civil deles (sem ajuste).
    ano_rotulo = ano_civil + 1 if mes_num in (9, 10, 11, 12) else ano_civil
    return f"{nome_mes} {ano_rotulo}"


def cargos_para_lista(cargo_val):
    if not cargo_val:
        return []
    if isinstance(cargo_val, list):
        return [c for c in cargo_val if c]
    return [cargo_val] if cargo_val else []


def _chave_ordenacao_mes(mes_ref):
    """
    Chave de ordenação cronológica para uma string "MES ANO".

    [ATUALIZADO — convenção "ano de serviço"] Com a mudança para o rótulo
    de ANO DE SERVIÇO (ver `obter_mes_vigente_str` e `constantes.py`), os
    12 meses de um mesmo ciclo (Setembro a Agosto) passam a compartilhar
    o MESMO número de ano no rótulo (ex.: "SETEMBRO 2027" ... "AGOSTO
    2027"). Isso torna a ordenação simples — (ano do rótulo, índice do
    mês em `_MESES_ORDEM`) — correta de novo, sem precisar de nenhum
    ajuste de -1 para Janeiro–Agosto. (Uma versão anterior desta função
    fazia esse ajuste, porque a convenção ANTIGA usava o ano CIVIL de
    cada mês — o que causava uma inversão bem na fronteira Agosto/
    Setembro. Essa correção deixou de ser necessária, e foi revertida,
    assim que a gravação passou a usar ano de serviço uniforme. Só
    funciona corretamente, porém, depois que os dados antigos (gravados
    na convenção de ano civil) forem migrados — ver script de migração.)
    """
    partes = str(mes_ref).upper().split()
    nome_mes = partes[0] if partes else ""
    ano = int(partes[1]) if len(partes) > 1 else 0
    idx = _MESES_ORDEM.index(nome_mes) if nome_mes in _MESES_ORDEM else 99
    return (ano, idx)


def ordenar_df_por_mes(df_input):
    df_sorted = df_input.copy()
    df_sorted["_sort_key"] = df_sorted["mes_referencia"].apply(_chave_ordenacao_mes)
    df_sorted = df_sorted.sort_values("_sort_key").drop(columns=["_sort_key"])
    return df_sorted


def ordenar_lista_meses(lista_meses):
    """
    [NOVO — correção] Ordena uma lista/array de strings "MES ANO" em ordem
    CRONOLÓGICA (ano de serviço, Setembro→Agosto), reaproveitando a mesma
    chave de `ordenar_df_por_mes`. Criada para o seletor de mês em main.py
    (`_renderizar_filtros`), que antes usava `sorted()` puro — ordem
    alfabética de texto, não cronológica. Isso já embaralhava a lista assim
    que havia mais de 1 ano de dados (ex.: "SETEMBRO 2024" ficava ordenado
    depois de "OUTUBRO 2025" em ordem alfabética, mas deveria vir antes em
    ordem cronológica).
    """
    return sorted(lista_meses, key=_chave_ordenacao_mes)


def normalizar_nome_no_banco(nome_recebido, lista_membros):
    entrada_norm = normalizar_texto(nome_recebido)
    if not entrada_norm or len(entrada_norm) < 2:
        return None

    tokens_entrada = set(entrada_norm.split())
    melhor_match, maior_score = None, 0.0

    for nome_oficial in lista_membros:
        oficial_norm = normalizar_texto(nome_oficial)
        tokens_oficial = oficial_norm.split()

        if entrada_norm == oficial_norm:
            return nome_oficial

        if len(tokens_entrada) == 1:
            primeiro = tokens_oficial[0] if tokens_oficial else ""
            segundo  = tokens_oficial[1] if len(tokens_oficial) > 1 else ""
            if entrada_norm in (primeiro, segundo):
                return nome_oficial

        if tokens_entrada and tokens_entrada.issubset(set(tokens_oficial)):
            score = len(tokens_entrada) / max(len(tokens_oficial), 1) + 0.5
            if score > maior_score:
                maior_score, melhor_match = score, nome_oficial
            continue

        primeiro_oficial = tokens_oficial[0] if tokens_oficial else ""
        for tok in tokens_entrada:
            if tok == primeiro_oficial and len(tok) >= 3:
                score = 0.88
                if score > maior_score:
                    maior_score, melhor_match = score, nome_oficial

        score_fuzzy = SequenceMatcher(None, entrada_norm, oficial_norm).ratio()
        if score_fuzzy > maior_score:
            maior_score, melhor_match = score_fuzzy, nome_oficial

    return melhor_match if maior_score >= 0.82 else None


def processar_dataframe(relatorios_brutos, membros_db):
    if not relatorios_brutos:
        return pd.DataFrame()

    df = pd.DataFrame(relatorios_brutos)

    if 'status_validacao' in df.columns:
        df = df[df['status_validacao'] != "EXCLUIDO"].copy()

    if df.empty:
        return pd.DataFrame()

    df['horas']            = pd.to_numeric(df.get('horas', 0), errors='coerce').fillna(0)
    df['estudos_biblicos'] = pd.to_numeric(df.get('estudos_biblicos', 0), errors='coerce').fillna(0)
    df['mes_referencia']   = df['mes_referencia'].str.upper()

    lista_nomes = list(membros_db.keys())

    def validar_envio(row):
        nome_oficial = normalizar_nome_no_banco(row['nome'], lista_nomes)
        if nome_oficial:
            dados_m = membros_db[nome_oficial]
            cat_mes = row.get('categoria_mes')
            if pd.notna(cat_mes) and cat_mes in categorias_lista:
                cat_final = cat_mes
            else:
                cat_final = dados_m.get('categoria', 'PUBLICADOR')
                if cat_final not in categorias_lista:
                    cat_final = 'PUBLICADOR'
            return pd.Series([nome_oficial, cat_final, "IDENTIFICADO"])
        return pd.Series([row['nome'], "DESCONHECIDO", "TRIAGEM"])

    df[['nome_oficial', 'cat_oficial', 'status_validacao']] = df.apply(validar_envio, axis=1)
    return df
