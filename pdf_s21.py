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
# RECALIBRADO medindo, char a char, um PDF real gerado pelo
# sistema (com pdfplumber) contra a posição exata dos glifos de
# checkbox do próprio template (fonte "Ornament" do formulário).
# Isso substitui os ajustes anteriores feitos "no olho" — agora
# cada valor abaixo foi validado a <0.5mm de erro.
#
# Duas causas principais dos desalinhamentos reportados:
#   1) Os checkboxes de CARGO (Servo/Pioneiro regular/Pioneiro
#      especial/Missionário) estavam com X muito longe da coluna
#      certa — em alguns casos > 20mm de erro (só não aparecia
#      porque os testes anteriores só marcavam "Ancião").
#   2) A tabela mensal assumia 8mm entre um mês e outro, mas o
#      formulário real usa ~7mm. Por isso o erro ia crescendo:
#      quase imperceptível em Janeiro/Fevereiro (meio da tabela)
#      e de +5 a +6mm em Setembro/Agosto (pontas da tabela) — e
#      o "Total" também herdava esse erro acumulado.
# -------------------------------------------------------------
PDF_Y_OFFSET    = 0.0
PDF_NOME_Y      = 272.0
PDF_NOME_X      = 24.0
PDF_NASCI_Y     = 265.0
PDF_NASCI_X     = 48.0
PDF_BATISM_Y    = 258.0
PDF_BATISM_X    = 48.0
PDF_CARGO_Y     = 253.6    # era 252.0

# Checkboxes "Masculino/Feminino": Masculino já estava certo na
# vertical (PDF_NASCI_Y), só precisou de ajuste fino horizontal.
# Feminino estava MUITO errado (a coluna real fica ~171.9, não
# 165) — só não aparecia porque nenhum teste anterior marcou
# "Feminino".
PDF_MASC_X      = 136.1    # era 135.0
PDF_FEM_X       = 171.9    # era 165.0 — bem fora da coluna real

# Checkboxes "Outras ovelhas/Ungido": usam a própria linha Y
# (PDF_CLASSE_Y), agora DESACOPLADA de PDF_BATISM_Y — antes as
# duas coisas compartilhavam a mesma variável, então qualquer
# ajuste na data de batismo bagunçava o checkbox (e vice-versa).
PDF_CLASSE_Y    = 259.3    # NOVO — não confundir com PDF_BATISM_Y (data)
PDF_OVELHAS_X   = 136.1    # era 135.0
PDF_UNGIDO_X    = 171.9    # era 165.0 — mesmo problema do Feminino

# Checkboxes de cargo: a vertical (PDF_CARGO_Y) estava ~1.5mm
# baixa demais para todos. Na horizontal, Ancião e Servo tinham
# erro pequeno — mas Pioneiro regular, Pioneiro especial e
# Missionário estavam GRAVEMENTE errados (a coluna real de cada
# um fica bem mais à direita do que estava configurado).
PDF_ANCIAO_X    = 6.6      # era 7.0
PDF_SERVO_X     = 30.0     # era 33.5
PDF_PREG_X      = 74.8     # era 63.5  — erro de +11mm
PDF_PESP_X      = 117.2    # era 98.5  — erro de +18.7mm
PDF_MISS_X      = 161.0    # era 138.5 — erro de +22.5mm

# Telefone de emergência: posição não mudou (não fazia parte do
# problema relatado).
PDF_TEL_X       = 150.0
PDF_TEL_Y       = 238.5

# Mapa de posição Y de cada mês na tabela. O espaçamento real do
# formulário é de 7.0mm entre linhas (medido diretamente nos
# checkboxes do template) — o valor antigo usava 8.0mm, por isso
# o erro crescia mês a mês.
_Y_MAP_BASE = {
    "SETEMBRO":  223.0, "OUTUBRO":   216.0, "NOVEMBRO":  209.0, "DEZEMBRO":  202.0,
    "JANEIRO":   195.0, "FEVEREIRO": 188.0, "MARÇO":     181.0, "ABRIL":     174.0,
    "MAIO":      167.0, "JUNHO":     160.0, "JULHO":     153.0, "AGOSTO":    146.0,
}

PDF_TOTAL_Y        = 137.3  # era 134.5 — herdava o erro acumulado da tabela mensal

# Colunas da tabela mensal: posições horizontais já estavam boas
# (confirmadas por medição, erro <0.5mm) — só a coluna de
# Pioneiro Auxiliar recebeu um ajuste fino de precisão.
PDF_COL_PARTICIP_X = 48.2   # era 48.0 (ajuste fino <0.5mm)
PDF_COL_ESTUDOS_X  = 80.5
PDF_COL_PIAUX_X    = 98.0   # era 97.5 (ajuste fino <0.5mm)
PDF_COL_HORAS_X    = 117.5
PDF_COL_OBS_X      = 136.0

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
        can.drawString(PDF_OVELHAS_X * mm, PDF_CLASSE_Y * mm, "X")
    elif classe == "Ungido":
        can.drawString(PDF_UNGIDO_X * mm, PDF_CLASSE_Y * mm, "X")

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
