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
# =============================================================
categorias_lista = ["PUBLICADOR", "PIONEIRO AUXILIAR", "PIONEIRO REGULAR"]

meses_referencia_ordem = [
    "SETEMBRO 2024", "OUTUBRO 2024", "NOVEMBRO 2024", "DEZEMBRO 2024",
    "JANEIRO 2025", "FEVEREIRO 2025", "MARÇO 2025", "ABRIL 2025", "MAIO 2025",
    "JUNHO 2025", "JULHO 2025", "AGOSTO 2025",
    "SETEMBRO 2025", "OUTUBRO 2025", "NOVEMBRO 2025", "DEZEMBRO 2025",
    "JANEIRO 2026", "FEVEREIRO 2026", "MARÇO 2026", "ABRIL 2026", "MAIO 2026",
    "JUNHO 2026", "JULHO 2026", "AGOSTO 2026",
]

# Usado por utilitarios.ordenar_df_por_mes() para ordenar cronologicamente
# (ano de serviço começa em Setembro) e também referenciado por pdf_s21.py
# ao montar o mapa de posições Y de cada mês no cartão S-21.
_MESES_ORDEM = [
    "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL",
    "MAIO", "JUNHO", "JULHO", "AGOSTO"
]

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
ABAS_SISTEMA = [
    {"id": "relatorios",   "label": "Relatórios",   "icone": "📋"},
    {"id": "triagem",      "label": "Triagem",      "icone": "⚠️"},
    {"id": "consolidado",  "label": "Consolidado",  "icone": "📈"},
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
