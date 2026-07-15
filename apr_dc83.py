# =============================================================
# apr_dc83.py
# Geração do PDF da Análise Preliminar de Risco (DC-83), preenchido
# por sobreposição de texto sobre o template DC83T.pdf.
#
# Dependências:
#   pip install pypdf reportlab
#
# SOBRE AS COORDENADAS:
# Diferente de uma estimativa visual, as posições abaixo foram
# extraídas diretamente da geometria real do DC83T.pdf (retângulos
# dos campos de cabeçalho e linhas/colunas da tabela, lidos com
# pdfplumber). O template é uma página paisagem de 841.9 x 595.2 pt.
# Se o template for substituído por outra versão/diagramação do
# DC-83, as coordenadas abaixo podem precisar de novo ajuste — use
# gerar_grade_calibracao() (no fim do arquivo) para conferir.
# =============================================================
import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

_root = os.path.abspath(os.path.dirname(__file__))
CAMINHO_TEMPLATE_PADRAO = os.path.join(_root, "DC83T.pdf")

FONTE = "Helvetica"
TAM_FONTE_CABECALHO = 8.5
TAM_FONTE_TABELA = 7.8
ENTRELINHA_TABELA = 9.2
TAM_FONTE_RODAPE = 8

# --- Cabeçalho: 5 caixas, todas com a mesma faixa horizontal -------
# (x0, x1, topo, base) — coordenadas em pontos, medidas a partir do
# topo da página (como no pdfplumber), convertidas para o sistema
# bottom-up do reportlab dentro de _caixa_texto_simples().
CAMPOS_CABECALHO = {
    "nome_projeto":      (187.8, 503.5, 78.5, 98.5),
    "descricao_servico": (187.8, 503.5, 108.7, 128.7),
    "local_servico":     (187.8, 503.5, 139.1, 159.1),
    "data_inicio":       (187.8, 503.5, 169.4, 189.4),
    "numero_emergencia": (187.8, 503.5, 199.7, 219.8),
}

# --- Tabela principal: 3 colunas x até 5 linhas --------------------
COLUNAS_TABELA = {
    "etapa":   (36.2, 292.5),
    "riscos":  (292.5, 549.2),
    "medidas": (549.2, 805.5),
}
# (topo, base) de cada linha da tabela
LINHAS_TABELA = [
    (253.9, 301.5),
    (301.5, 348.8),
    (348.8, 396.1),
    (396.1, 444.0),
    (444.0, 490.9),
]

# --- Rodapé: preparado por / data / revisado / data / revisado / data
# (x0, x1, topo, base) — a faixa de escrita fica logo abaixo do rótulo
# impresso (que termina em top=507.6) e antes do texto de rodapé do
# formulário (que começa em top~536).
CAMPOS_RODAPE = {
    "preparado_por":    (41.9, 178.0, 508.0, 519.0),
    "data_preparacao":  (183.6, 295.0, 508.0, 519.0),
    "revisado_por_1":   (299.4, 436.0, 508.0, 519.0),
    "data_revisao_1":   (440.2, 552.0, 508.0, 519.0),
    "revisado_por_2":   (555.9, 693.0, 508.0, 519.0),
    "data_revisao_2":   (696.7, 805.0, 508.0, 519.0),
}

PADDING_X = 3
PADDING_TOPO = 2


def _quebrar_linhas(c, texto, largura_pt, tamanho_fonte):
    """Quebra 'texto' em linhas que cabem em largura_pt, na fonte atual."""
    if not texto:
        return []
    palavras = str(texto).split()
    linhas, linha_atual = [], ""
    for palavra in palavras:
        candidata = f"{linha_atual} {palavra}".strip()
        if c.stringWidth(candidata, FONTE, tamanho_fonte) <= largura_pt:
            linha_atual = candidata
        else:
            if linha_atual:
                linhas.append(linha_atual)
            # palavra sozinha maior que a largura: corta na força
            while c.stringWidth(palavra, FONTE, tamanho_fonte) > largura_pt and len(palavra) > 1:
                palavra = palavra[:-1]
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas


def _caixa_texto_simples(c, altura_pg, texto, caixa, tamanho_fonte=TAM_FONTE_CABECALHO):
    """Cabeçalho/rodapé: uma linha só, corta com '…' se não couber na largura da caixa."""
    x0, x1, topo, base = caixa
    largura_pt = (x1 - x0) - 2 * PADDING_X
    x = x0 + PADDING_X
    y = (altura_pg - topo) - tamanho_fonte - PADDING_TOPO

    c.setFont(FONTE, tamanho_fonte)
    linhas = _quebrar_linhas(c, texto, largura_pt, tamanho_fonte)
    if not linhas:
        return
    primeira = linhas[0]
    if len(linhas) > 1:
        while primeira and c.stringWidth(primeira + "…", FONTE, tamanho_fonte) > largura_pt:
            primeira = primeira[:-1]
        primeira += "…"
    c.drawString(x, y, primeira)


def _celula_texto_multilinha(c, altura_pg, texto, x0, x1, topo, base):
    """Células da tabela: várias linhas, cortando se não couber na altura da célula."""
    largura_pt = (x1 - x0) - 2 * PADDING_X
    altura_pt = (base - topo) - 2 * PADDING_TOPO
    x = x0 + PADDING_X

    c.setFont(FONTE, TAM_FONTE_TABELA)
    max_linhas = max(1, int(altura_pt // ENTRELINHA_TABELA))

    if isinstance(texto, (list, tuple)):
        texto_final = "\n".join(f"• {item}" for item in texto if str(item).strip())
    else:
        texto_final = str(texto or "")

    linhas = []
    for paragrafo in texto_final.split("\n"):
        linhas.extend(_quebrar_linhas(c, paragrafo, largura_pt, TAM_FONTE_TABELA) or [""])

    truncado = False
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        truncado = True

    if truncado and linhas:
        ultima = linhas[-1]
        while ultima and c.stringWidth(ultima + "…", FONTE, TAM_FONTE_TABELA) > largura_pt:
            ultima = ultima[:-1]
        linhas[-1] = ultima + "…"

    y = (altura_pg - topo) - PADDING_TOPO - TAM_FONTE_TABELA
    for linha in linhas:
        c.drawString(x, y, linha)
        y -= ENTRELINHA_TABELA


def gerar_pdf_apr(dados, caminho_template=CAMINHO_TEMPLATE_PADRAO):
    """
    dados = {
        "nome_projeto": str, "descricao_servico": str, "local_servico": str,
        "data_inicio": str, "numero_emergencia": str,
        "linhas": [{"etapa": str, "riscos": str, "medidas": str}, ...]  (até 5),
        "preparado_por": str, "data_preparacao": str,
        "revisado_por_1": str, "data_revisao_1": str,
        "revisado_por_2": str, "data_revisao_2": str,
    }
    Devolve os bytes do PDF preenchido.
    """
    if not os.path.exists(caminho_template):
        raise FileNotFoundError(
            f"Template não encontrado em '{caminho_template}'. Confirme se o "
            f"DC83T.pdf está na mesma pasta do main.py."
        )

    leitor = PdfReader(caminho_template)
    pagina_template = leitor.pages[0]
    largura_pg = float(pagina_template.mediabox.width)
    altura_pg = float(pagina_template.mediabox.height)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(largura_pg, altura_pg))

    for campo, caixa in CAMPOS_CABECALHO.items():
        _caixa_texto_simples(c, altura_pg, dados.get(campo, ""), caixa)

    for i, linha_dados in enumerate(dados.get("linhas", [])[:5]):
        topo, base = LINHAS_TABELA[i]
        for coluna, (x0, x1) in COLUNAS_TABELA.items():
            valor = linha_dados.get(coluna, "")
            _celula_texto_multilinha(c, altura_pg, valor, x0, x1, topo, base)

    for campo, caixa in CAMPOS_RODAPE.items():
        _caixa_texto_simples(c, altura_pg, dados.get(campo, ""), caixa, tamanho_fonte=TAM_FONTE_RODAPE)

    c.save()
    buffer.seek(0)

    overlay = PdfReader(buffer)
    escritor = PdfWriter()
    pagina_base = leitor.pages[0]
    pagina_base.merge_page(overlay.pages[0])
    escritor.add_page(pagina_base)
    for pagina_extra in leitor.pages[1:]:
        escritor.add_page(pagina_extra)

    saida = io.BytesIO()
    escritor.write(saida)
    saida.seek(0)
    return saida.getvalue()


def gerar_grade_calibracao(caminho_template=CAMINHO_TEMPLATE_PADRAO, caminho_saida="DC83T_grade.pdf"):
    """
    Ferramenta de apoio: gera um PDF com uma grade de 50 em 50 pontos
    sobre o template, para conferir/ajustar as coordenadas acima caso
    o template seja substituído por outra versão. Rode manualmente:
        python3 -c "from apr_dc83 import gerar_grade_calibracao as g; g()"
    """
    leitor = PdfReader(caminho_template)
    largura_pg = float(leitor.pages[0].mediabox.width)
    altura_pg = float(leitor.pages[0].mediabox.height)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(largura_pg, altura_pg))
    c.setStrokeColorRGB(1, 0, 0)
    c.setFillColorRGB(1, 0, 0)
    c.setFont("Helvetica", 5)

    passo = 50
    x = 0
    while x <= largura_pg:
        c.line(x, 0, x, altura_pg)
        c.drawString(x + 1, altura_pg - 8, str(int(x)))
        x += passo

    y_topo = 0
    while y_topo <= altura_pg:
        y_pdf = altura_pg - y_topo
        c.line(0, y_pdf, largura_pg, y_pdf)
        c.drawString(2, y_pdf - 6, str(int(y_topo)))
        y_topo += passo

    c.save()
    buffer.seek(0)

    overlay = PdfReader(buffer)
    escritor = PdfWriter()
    pagina = leitor.pages[0]
    pagina.merge_page(overlay.pages[0])
    escritor.add_page(pagina)
    with open(caminho_saida, "wb") as f:
        escritor.write(f)
    return caminho_saida
