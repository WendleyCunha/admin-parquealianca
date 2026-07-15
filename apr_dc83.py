# =============================================================
# apr_dc83.py
# Geração do PDF da Análise Preliminar de Risco (DC-83), preenchido
# por sobreposição de texto sobre o template DC83T.pdf.
#
# Dependências:
#   pip install pypdf reportlab
#
# SOBRE AS COORDENADAS:
# O DC83T.pdf não tem campos de formulário (AcroForm) — é uma tabela
# desenhada. Por isso o preenchimento é feito desenhando texto por
# cima, em posições estimadas a partir do layout visual do formulário.
# É praticamente certo que alguns campos vão precisar de ajuste fino.
# Use gerar_grade_calibracao() (no fim do arquivo) para conferir e
# corrigir os números abaixo.
# =============================================================
import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

_root = os.path.abspath(os.path.dirname(__file__))
CAMINHO_TEMPLATE_PADRAO = os.path.join(_root, "DC83T.pdf")

FONTE = "Helvetica"
TAM_FONTE_CABECALHO = 9
TAM_FONTE_TABELA = 8
ENTRELINHA_TABELA = 9.5

# --- Cabeçalho: (x_frac_inicio, y_frac_do_topo, largura_frac) ------
CAMPOS_CABECALHO = {
    "nome_projeto":      (0.225, 0.150, 0.365),
    "descricao_servico": (0.225, 0.202, 0.365),
    "local_servico":     (0.225, 0.254, 0.365),
    "data_inicio":       (0.225, 0.310, 0.365),
    "numero_emergencia": (0.225, 0.362, 0.365),
}

# --- Tabela principal: 3 colunas x até 5 linhas --------------------
COLUNAS_TABELA = {
    "etapa":   (0.050, 0.296),
    "riscos":  (0.352, 0.302),
    "medidas": (0.655, 0.296),
}
LINHAS_TABELA_Y = [0.425, 0.505, 0.585, 0.665, 0.745]   # topo de cada linha
ALTURA_LINHA_TABELA = 0.078

# --- Rodapé: preparado por / data / revisado / data / revisado / data
CAMPOS_RODAPE = {
    "preparado_por":    (0.050, 0.833, 0.148),
    "data_preparacao":  (0.203, 0.833, 0.148),
    "revisado_por_1":   (0.356, 0.833, 0.148),
    "data_revisao_1":   (0.509, 0.833, 0.148),
    "revisado_por_2":   (0.662, 0.833, 0.148),
    "data_revisao_2":   (0.815, 0.833, 0.148),
}


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
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas


def _texto_simples(c, largura_pg, altura_pg, texto, campo):
    """Campos do cabeçalho/rodapé: uma linha só, corta com '…' se não couber."""
    x_frac, y_frac, larg_frac = campo
    x = x_frac * largura_pg
    y = altura_pg - (y_frac * altura_pg) - TAM_FONTE_CABECALHO
    largura_pt = larg_frac * largura_pg

    c.setFont(FONTE, TAM_FONTE_CABECALHO)
    linhas = _quebrar_linhas(c, texto, largura_pt, TAM_FONTE_CABECALHO)
    if not linhas:
        return
    primeira = linhas[0]
    if len(linhas) > 1:
        while primeira and c.stringWidth(primeira + "…", FONTE, TAM_FONTE_CABECALHO) > largura_pt:
            primeira = primeira[:-1]
        primeira += "…"
    c.drawString(x, y, primeira)


def _texto_multilinha(c, largura_pg, altura_pg, texto, x_frac, y_topo_frac, largura_frac, altura_frac):
    """Células da tabela: várias linhas, cortando se não couber na altura da célula."""
    x = x_frac * largura_pg
    y_topo = altura_pg - (y_topo_frac * altura_pg)
    largura_pt = largura_frac * largura_pg
    altura_pt = altura_frac * altura_pg

    c.setFont(FONTE, TAM_FONTE_TABELA)
    max_linhas = max(1, int(altura_pt // ENTRELINHA_TABELA))

    if isinstance(texto, (list, tuple)):
        texto_final = "\n".join(f"• {item}" for item in texto if str(item).strip())
    else:
        texto_final = str(texto or "")

    linhas = []
    for paragrafo in texto_final.split("\n"):
        linhas.extend(_quebrar_linhas(c, paragrafo, largura_pt, TAM_FONTE_TABELA) or [""])

    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        if linhas:
            ultima = linhas[-1]
            while ultima and c.stringWidth(ultima + "…", FONTE, TAM_FONTE_TABELA) > largura_pt:
                ultima = ultima[:-1]
            linhas[-1] = ultima + "…"

    y = y_topo - TAM_FONTE_TABELA
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

    for campo, posicao in CAMPOS_CABECALHO.items():
        _texto_simples(c, largura_pg, altura_pg, dados.get(campo, ""), posicao)

    for i, linha_dados in enumerate(dados.get("linhas", [])[:5]):
        y_topo = LINHAS_TABELA_Y[i]
        for coluna, (x_frac, larg_frac) in COLUNAS_TABELA.items():
            valor = linha_dados.get(coluna, "")
            _texto_multilinha(c, largura_pg, altura_pg, valor,
                               x_frac, y_topo, larg_frac, ALTURA_LINHA_TABELA)

    for campo, posicao in CAMPOS_RODAPE.items():
        _texto_simples(c, largura_pg, altura_pg, dados.get(campo, ""), posicao)

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
    Rode manualmente num terminal Python (fora do Streamlit):
        from apr_dc83 import gerar_grade_calibracao
        gerar_grade_calibracao()
    Gera um PDF com uma grade de 0.00 a 1.00 (passo 0.05) sobre o
    template, pra você comparar visualmente e ajustar os números em
    CAMPOS_CABECALHO / COLUNAS_TABELA / LINHAS_TABELA_Y / CAMPOS_RODAPE.
    """
    leitor = PdfReader(caminho_template)
    largura_pg = float(leitor.pages[0].mediabox.width)
    altura_pg = float(leitor.pages[0].mediabox.height)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(largura_pg, altura_pg))
    c.setStrokeColorRGB(1, 0, 0)
    c.setFillColorRGB(1, 0, 0)
    c.setFont("Helvetica", 6)

    frac = 0.0
    while frac <= 1.0:
        x = frac * largura_pg
        y = frac * altura_pg
        c.line(x, 0, x, altura_pg)
        c.line(0, altura_pg - y, largura_pg, altura_pg - y)
        c.drawString(x + 1, altura_pg - 8, f"{frac:.2f}")
        c.drawString(2, altura_pg - y - 6, f"{frac:.2f}")
        frac += 0.05

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
