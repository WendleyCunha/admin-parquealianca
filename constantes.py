# =============================================================
# constantes.py
# Listas e valores fixos usados por MAIS DE UM módulo do sistema.
#
# Origem: Seção 3 ("CONSTANTES E LISTAS GLOBAIS") do antigo main.py
# monolítico. Só ficou aqui o que é compartilhado por 2+ arquivos —
# constantes usadas em um único módulo (ex: coordenadas do PDF S-21)
# continuam perto de quem as usa, em pdf_s21.py.
#
# ATUALIZAÇÃO (controle de acesso por usuário):
#   ABAS_SISTEMA              → catálogo de abas para permissões e
#                                 para montar os tabs dinamicamente
#                                 em main.py (substitui a lista fixa
#                                 que existia dentro de st.tabs()).
#   NIVEIS_PERMISSAO           → os 3 níveis possíveis por aba.
#   NIVEIS_PERMISSAO_LABELS    → rótulo amigável de cada nível.
#   PERMISSOES_PADRAO_ADMIN    → atalho: admin sempre enxerga/edita
#                                 tudo, sem precisar gravar permissão
#                                 aba a aba no Firestore.
#
# ATUALIZAÇÃO (virada de ano de serviço — CORREÇÃO):
#   `meses_referencia_ordem` ERA uma lista fixa, escrita à mão, que
#   terminava em "AGOSTO 2026". Isso exigia que alguém lembrasse de
#   editar este arquivo TODA virada de ano de serviço (setembro),
#   acrescentando os 12 meses seguintes manualmente. Se isso fosse
#   esquecido, qualquer membro com `mes_inicio` num mês fora da
#   lista tinha seu índice de ordenação calculado incorretamente
#   como 0 (ver `mod_relatorios.aba_relatorios`, aba Pendências) —
#   fazendo-o aparecer como pendente até em meses anteriores à
#   entrada dele no sistema, um bug silencioso e difícil de notar.
#
#   Agora a lista é GERADA por código a partir de `_MESES_ORDEM`
#   (os 12 nomes cíclicos do ano de serviço, Setembro→Agosto), para
#   um número grande de anos à frente — nenhuma virada de ano de
#   serviço, daqui em diante, precisa de edição manual neste arquivo.
# =============================================================
categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]

# Usado por utilitarios.ordenar_df_por_mes() para ordenar cronologicamente
# (ano de serviço começa em Setembro) e também referenciado por pdf_s21.py
# ao montar o mapa de posições Y de cada mês no cartão S-21.
_MESES_ORDEM = [
    "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL",
    "MAIO", "JUNHO", "JULHO", "AGOSTO"
]


def _gerar_meses_referencia_ordem(ano_inicio_servico: int = 2024, anos_a_gerar: int = 20) -> list:
    """
    Gera a lista linear "MES ANO" cobrindo `anos_a_gerar` anos de serviço
    completos (Setembro→Agosto) a partir do ano de serviço que COMEÇA em
    setembro de `ano_inicio_servico`.

    [ATUALIZADO — convenção "ano de serviço"] O rótulo do ano usado para
    TODOS os 12 meses de um ciclo é o ANO DE ENCERRAMENTO daquele ciclo
    (o ano do Agosto) — não mais o ano civil de cada mês individualmente.
    Ex.: o ciclo que começa em setembro de 2026 e termina em agosto de
    2027 gera "SETEMBRO 2027", "OUTUBRO 2027", ..., "AGOSTO 2027" — o
    próprio Setembro que abre o ano já usa o número do ano seguinte.

    Isso é uma mudança de convenção em relação aos dados já gravados
    antes desta correção (que usavam o ano civil: "SETEMBRO 2024" para o
    Setembro que abre o ciclo 2024-2025). Registros antigos de Setembro/
    Outubro/Novembro/Dezembro precisam ser migrados (ver script de
    migração) para ficarem consistentes com os novos.
    """
    lista = []
    for i in range(anos_a_gerar):
        ano_servico_inicio = ano_inicio_servico + i
        ano_rotulo = ano_servico_inicio + 1
        for nome_mes in _MESES_ORDEM:
            lista.append(f"{nome_mes} {ano_rotulo}")
    return lista


meses_referencia_ordem = _gerar_meses_referencia_ordem(ano_inicio_servico=2024, anos_a_gerar=20)

# Meses por ano de serviço (Set–Ago) — mantido por compatibilidade,
# mesmo não sendo referenciado ativamente em nenhum módulo no momento
# da divisão do arquivo.
_MESES_ANO_SERVICO = [
    "Setembro", "Outubro", "Novembro", "Dezembro",
    "Janeiro", "Fevereiro", "Março", "Abril",
    "Maio", "Junho", "Julho", "Agosto"
]

_CARGOS_LISTA = [
    "Ancião", "Servo ministerial", "Pioneiro regular",
    "Pioneiro especial", "Missionário em campo"
]
_GENEROS       = ["", "Masculino", "Feminino"]
_CLASSES       = ["", "Outras ovelhas", "Ungido"]
_STATUS_OPCOES = ["Ativo", "Inativo"]


# ── Controle de acesso por usuário ──────────────────────────────
# "id" é a chave usada em todo lugar (permissões, roteamento das
# abas em main.py). "label" e "icone" são só exibição.
#
# Triagem e Consolidado NÃO aparecem mais aqui — viraram sub-abas
# dentro de "Relatórios" (mesmo sistema, mesmos dados). A permissão
# de "relatorios" agora vale para as três juntas. Ver mod_relatorios.py.
ABAS_SISTEMA = [
    {"id": "relatorios",   "label": "Relatórios",   "icone": "📋"},
    {"id": "anuncios",     "label": "Anúncios",     "icone": "📢"},
    {"id": "passagens",    "label": "Passagens",    "icone": "🚌"},
    {"id": "manutencao",   "label": "Manutenção",   "icone": "🔧"},
    {"id": "configuracao", "label": "Configuração", "icone": "⚙️"},
]

NIVEIS_PERMISSAO = ["sem_acesso", "visualizar", "editar"]

NIVEIS_PERMISSAO_LABELS = {
    "sem_acesso": "Sem acesso",
    "visualizar": "Somente visualizar",
    "editar":     "Visualizar e editar",
}

# Um usuário marcado como admin=True não precisa ter cada aba gravada
# no Firestore — ele sempre recebe "editar" em todas.
PERMISSOES_PADRAO_ADMIN = {aba["id"]: "editar" for aba in ABAS_SISTEMA}
