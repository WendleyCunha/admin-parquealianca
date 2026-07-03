# =============================================================
# pdf_s21.py
# Tudo relacionado à geração do cartão S-21 em PDF: as coordenadas
# de posicionamento (ajustadas manualmente com base nas fotos do
# cartão físico) e as funções que desenham por cima do s21.pdf.
#
# Origem: coordenadas PDF_* da Seção 3 ("CONSTANTES") + Seção 8
# ("GERAÇÃO DE PDF (S-21)") do antigo main.py monolítico.
# Nada foi recalibrado — só movido de lugar.
# =============================================================
import io
import os
import zipfile

import pandas as pd
import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from utilitarios import cargos_para_lista, ordenar_df_por_mes

# -------------------------------------------------------------
# COORDENADAS DO CARTÃO S-21 (em mm, origem no canto inferior
# esquerdo da página A4 — padrão do ReportLab)
#
# AJUSTADO com base nas fotos enviadas (cartão do Wendley e o
# consolidado). Os X's e números estavam caindo fora dos
# quadradinhos/colunas certas. Ver observações em cada bloco.
# -------------------------------------------------------------
PDF_Y_OFFSET    = 0.0
PDF_NOME_Y      = 272.0
PDF_NOME_X      = 24.0
PDF_NASCI_Y     = 265.0
PDF_NASCI_X     = 48.0
PDF_BATISM_Y    = 258.0
PDF_BATISM_X    = 48.0
PDF_CARGO_Y     = 252.0

# Checkboxes "Masculino/Feminino" e "Outras ovelhas/Ungido":
# na 1ª rodada o X ainda caiu um pouco à direita do quadradinho
# (Masculino e Outras ovelhas) — recuado mais ~8mm agora.
# Feminino/Ungido já estavam bons, não foram tocados.
PDF_MASC_X      = 135.0   # era 143.0 (ainda pra direita)
PDF_FEM_X       = 165.0   # sem alteração — já estava bom
PDF_OVELHAS_X   = 135.0   # era 143.0 (ainda pra direita)
PDF_UNGIDO_X    = 165.0   # sem alteração — já estava bom

# Checkboxes de cargo (Ancião / Servo / Pioneiro reg. / Pioneiro
# esp. / Missionário): pequeno ajuste para centralizar o X no
# quadradinho — estava nascendo meio pixel à direita, tocando
# o começo do rótulo.
PDF_ANCIAO_X    = 7.0      # era 9.5
PDF_SERVO_X     = 33.5     # era 35.0
PDF_PREG_X      = 63.5     # era 65.0
PDF_PESP_X      = 98.5     # era 100.0
PDF_MISS_X      = 138.5    # era 140.0

# Telefone de emergência: NÃO fica mais dentro da tabela.
# Na foto ele sobrepunha o texto "(Se for pioneiro ou
# missionário em campo)" do cabeçalho da coluna Horas.
# Movido para o espaço em branco à direita da linha de cargos.
PDF_TEL_X       = 150.0
PDF_TEL_Y       = 238.5

_Y_MAP_BASE = {
    "SETEMBRO":  228.5, "OUTUBRO":   220.5, "NOVEMBRO":  212.5, "DEZEMBRO":  204.5,
    "JANEIRO":   196.5, "FEVEREIRO": 188.5, "MARÇO":     180.5, "ABRIL":     172.5,
    "MAIO":      164.5, "JUNHO":     156.5, "JULHO":     148.5, "AGOSTO":    140.5,
}

PDF_TOTAL_Y        = 134.5  # era 131.5 — subiu ~3mm, estava caindo longe demais da linha "Total"

# Colunas da tabela mensal:
# - PARTICIP: o X do "participou no ministério" estava saindo
#   do quadradinho e quase tocando a coluna "Estudos" (visto na
#   linha de Abril e nos meses do consolidado). Trazido ~5.5mm
#   para a esquerda.
# - HORAS: pequeno ajuste para centralizar melhor o número.
# - OBS: um pouco mais à direita para dar respiro em relação à
#   coluna de Horas (na foto "15" e "Pioneiro Auxiliar"/"63
#   relat." ficavam quase colados).
PDF_COL_PARTICIP_X = 48.0   # era 53.5
PDF_COL_ESTUDOS_X  = 80.5
PDF_COL_PIAUX_X    = 97.5
PDF_COL_HORAS_X    = 117.5  # era 116.5
PDF_COL_OBS_X      = 136.0  # era 133.0

_CARGO_X_MAP = {
    "Ancião":               PDF_ANCIAO_X,
    "Servo ministerial":    PDF_SERVO_X,
    "Pioneiro regular":     PDF_PREG_X,
    "Pioneiro especial":    PDF_PESP_X,
    "Missionário em campo": PDF_MISS_X,
}


def gerar_pdf_padrao_s21(nome_cabecalho, categoria_label, dados_rows, membro_info=None):
    path_original = os.path.join(os.path.dirname(__file__), "s21.pdf")
    if not os.path.exists(path_original):
        st.error("Arquivo 's21.pdf' não encontrado na pasta do app.")
        return None

    mi = membro_info or {}
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)

    can.setFont("Helvetica-Bold", 10)
    can.drawString(PDF_NOME_X * mm, PDF_NOME_Y * mm, str(nome_cabecalho).upper())

    data_nasc = str(mi.get("data_nascimento", "")).strip()
    if data_nasc:
        can.setFont("Helvetica", 9)
        can.drawString(PDF_NASCI_X * mm, PDF_NASCI_Y * mm, data_nasc)

    data_bat = str(mi.get("data_batismo", "")).strip()
    if data_bat:
        can.setFont("Helvetica", 9)
        can.drawString(PDF_BATISM_X * mm, PDF_BATISM_Y * mm, data_bat)

    genero = mi.get("genero", "")
    can.setFont("Helvetica-Bold", 10)
    if genero == "Masculino":
        can.drawString(PDF_MASC_X * mm, PDF_NASCI_Y * mm, "X")
    elif genero == "Feminino":
        can.drawString(PDF_FEM_X * mm, PDF_NASCI_Y * mm, "X")

    classe = mi.get("classe", "")
    if classe == "Outras ovelhas":
        can.drawString(PDF_OVELHAS_X * mm, PDF_BATISM_Y * mm, "X")
    elif classe == "Ungido":
        can.drawString(PDF_UNGIDO_X * mm, PDF_BATISM_Y * mm, "X")

    cargos = cargos_para_lista(mi.get("cargo", ""))
    can.setFont("Helvetica-Bold", 10)
    for cargo in cargos:
        if cargo in _CARGO_X_MAP:
            can.drawString(_CARGO_X_MAP[cargo] * mm, PDF_CARGO_Y * mm, "X")

    tel_emerg = str(mi.get("telefone_emergencia", "")).strip()
    if tel_emerg:
        can.setFont("Helvetica-Bold", 8)
        can.drawString(PDF_TEL_X * mm, PDF_TEL_Y * mm, f"Tel: {tel_emerg}"[:32])

    total_horas = 0
    total_estud = 0

    for _, row in dados_rows.iterrows():
        mes_key = str(row.get('mes_referencia', '')).split()[0].upper()
        y_base  = _Y_MAP_BASE.get(mes_key)
        if y_base is None:
            continue
        y_pos = (y_base + PDF_Y_OFFSET) * mm

        horas = int(row.get('horas', 0))
        estud = int(row.get('estudos_biblicos', 0))
        total_horas += horas
        total_estud += estud

        if horas > 0 or estud > 0:
            can.setFont("Helvetica-Bold", 10)
            can.drawCentredString(PDF_COL_PARTICIP_X * mm, y_pos, "X")

        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_ESTUDOS_X * mm, y_pos, str(estud))

        categoria_do_mes = str(row.get('cat_oficial', '')).upper()
        if categoria_do_mes == "PIONEIRO AUXILIAR":
            can.drawCentredString(PDF_COL_PIAUX_X * mm, y_pos, "X")

        can.drawCentredString(PDF_COL_HORAS_X * mm, y_pos, str(horas))

        obs_normal = str(row.get('observacoes', ''))
        obs_normal = obs_normal if obs_normal.lower() not in ('nan', '', 'none') else ''

        if categoria_do_mes == "PIONEIRO AUXILIAR":
            obs_final = f"Pion. Auxiliar | {obs_normal}" if obs_normal else "Pioneiro Auxiliar"
        else:
            obs_final = obs_normal

        if obs_final:
            can.setFont("Helvetica", 8)
            can.drawString(PDF_COL_OBS_X * mm, y_pos, obs_final[:32])

        can.setFont("Helvetica-Bold", 10)

    if total_horas > 0:
        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_HORAS_X * mm, PDF_TOTAL_Y * mm, str(total_horas))
    if total_estud > 0:
        can.setFont("Helvetica-Bold", 10)
        can.drawCentredString(PDF_COL_ESTUDOS_X * mm, PDF_TOTAL_Y * mm, str(total_estud))

    can.save()
    packet.seek(0)

    reader_original = PdfReader(open(path_original, "rb"))
    writer = PdfWriter()
    pagina_base = reader_original.pages[0]
    pagina_base.merge_page(PdfReader(packet).pages[0])
    writer.add_page(pagina_base)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def gerar_zip_pendentes(pendentes, mes, membros_db, df_todos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for nome in pendentes:
            mi = membros_db.get(nome, {})
            df_hist = df_todos[
                (df_todos['nome_oficial'] == nome) &
                (df_todos['status_validacao'] == "IDENTIFICADO")
            ]
            df_hist = ordenar_df_por_mes(df_hist) if not df_hist.empty else pd.DataFrame()
            pdf = gerar_pdf_padrao_s21(nome, mi.get('categoria', 'PUBLICADOR'),
                                       df_hist, membro_info=mi)
            if pdf:
                nome_arq = "".join(c for c in nome if c.isalnum() or c in (' ', '_', '-')
                                   ).strip().replace(' ', '_')
                zf.writestr(f"Pendente_{nome_arq}.pdf", pdf)
    return buf.getvalue()
