# =============================================================
# tema.py  (NOVO)
# ÚNICA FONTE DA VERDADE para cores e tipografia do app inteiro.
#
# Qualquer lugar do código que precisar de uma cor deve fazer:
#     from tema import CORES, FONTE
#     ... CORES["primaria"] ...
# em vez de escrever o valor hexadecimal direto.
#
# Por quê isso importa: `estilo.py` (o CSS que roda na página) e os
# módulos que montam HTML "solto" — Passagens (usa components.html,
# que roda num iframe isolado e não enxerga o CSS da página),
# Triagem, Manutenção e Assistência — agora leem a cor do MESMO
# lugar. Trocar a paleta do app inteiro (inclusive dentro dos
# iframes) é editar só o dicionário CORES abaixo.
#
# O que ainda NÃO muda trocando este arquivo:
#  - Cores de status com significado próprio (vermelho = pendência/
#    erro, verde = sucesso/concluído, âmbar = atenção) continuam
#    fixas de propósito — trocar a cor "de marca" não deveria virar
#    o vermelho de "erro" em azul, por exemplo.
#  - Fonte, cabeçalho e rodapé têm outra causa-raiz: ver o
#    comentário no fim deste arquivo.
# =============================================================

CORES = {
    # Marca / identidade — mude aqui para trocar a paleta inteira
    "primaria":         "#2E6DA4",   # azul principal (botões, bordas de destaque, links)
    "primaria_escura":  "#1F4E86",   # texto/títulos sobre fundo claro
    "primaria_clara":   "#E7F0FA",   # fundo claro de badges/cards
    "primaria_borda":   "#D7E6F4",   # borda padrão dos cards
    "primaria_borda_forte": "#BBD3EC",

    "texto_principal":  "#1A1A1A",
    "texto_muted":      "#5B7BA6",   # rótulos em caixa alta (labels)
    "texto_muted2":     "#2F547E",   # texto secundário mais escuro

    "fundo_pagina_1":   "#EFF5FC",   # topo do gradiente de fundo da página
    "fundo_pagina_2":   "#E4EEFA",   # base do gradiente de fundo da página
    "fundo_card_1":     "#FFFFFF",
    "fundo_card_2":     "#F3F8FE",

    # Semânticas — NÃO ligadas à marca, mantidas por significado
    "sucesso":          "#2f8f52",
    "sucesso_bg":       "#EEF9F0",
    "sucesso_borda":    "#BFE8C8",

    "erro":             "#c14b4b",
    "erro_bg":          "#FDECEC",
    "erro_borda":       "#F3B8B8",

    "atencao":          "#8A6D14",   # texto do aviso âmbar
    "atencao_bg":       "#FFF6E5",
    "atencao_borda":    "#F0D48E",

    "neutro":           "#55606B",
    "neutro_bg":        "#F2F4F7",
    "neutro_borda":     "#DDE3EA",
}

# Gradiente do avatar do usuário logado (canto superior direito)
GRADIENTE_AVATAR = f"linear-gradient(135deg,{CORES['primaria_escura']},#5B9BD9)"

FONTE = "'Inter', sans-serif"
FONTE_GOOGLE_IMPORT = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"

# -----------------------------------------------------------------
# Sobre cabeçalho e rodapé:
# Esses dois já são de arquivo único — não é um problema de cor,
# é estrutural e já está resolvido: quem desenha o cabeçalho é a
# função `_renderizar_cabecalho()` dentro de main.py, e o rodapé é
# o bloco de `st.markdown` no fim de `main()`, também em main.py.
# Ou seja: para mudar o cabeçalho ou o rodapé do sistema inteiro,
# o único arquivo que você abre é main.py — nenhum módulo de aba
# desenha cabeçalho/rodapé por conta própria.
# -----------------------------------------------------------------
