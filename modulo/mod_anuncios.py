# =============================================================
# modulo/mod_anuncios.py
# Aba "ANÚNCIOS" — postagens de texto, imagem ou agenda de reunião.
#
# ATUALIZAÇÃO: aceita pode_editar=True/False. Sem permissão de
# edição, a sub-aba "Nova Postagem" fica oculta e o botão de
# deletar some em "Gerenciar Postagens".
# =============================================================
import os
import sys
import base64

import streamlit as st

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import carregar_anuncios, salvar_anuncio, deletar_anuncio
import permissoes


def gerar_html_agenda(d):
    C_CANT  = "#1a78b4"
    C_TES   = "#1a3566"
    C_TES_I = "#1a5fa8"
    C_MIN   = "#8a6200"
    C_MIN_I = "#a07800"
    C_NVC   = "#cc0000"
    C_NVC_I = "#1a5fa8"

    def row(num, titulo, duracao, bg, cor_item):
        if not str(titulo).strip():
            return ""
        dur = (f'<br><span style="font-size:12px;color:#888;margin-left:4px;">({duracao})</span>'
               if str(duracao).strip() else "")
        return (f'<div style="padding:6px 14px;background:{bg};border-bottom:1px solid #e8e8e8;">'
                f'<span style="color:{cor_item};font-weight:bold;">{num}. {titulo}</span>{dur}'
                f'</div>')

    def sec_header(texto, bg):
        return (f'<div style="background:{bg};color:white;padding:9px 14px;'
                f'font-weight:bold;font-size:14.5px;letter-spacing:0.3px;">{texto}</div>')

    html = ('<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;'
            'border:1px solid #ccc;border-radius:10px;overflow:hidden;'
            'box-shadow:0 2px 8px rgba(0,0,0,0.12);margin:auto;">')
    html += f'<div style="padding:12px 14px 8px;background:#ffffff;">'
    html += f'<div style="font-size:19px;font-weight:bold;color:#111;">{d.get("data_texto","")}</div>'
    if d.get("escritura"):
        html += f'<div style="color:{C_CANT};font-size:13px;font-weight:bold;margin-top:2px;">{d["escritura"]}</div>'
    html += '</div>'
    html += '<hr style="margin:0;border:0;border-top:1px solid #ddd;">'

    if d.get("cantico_abertura"):
        html += (f'<div style="padding:7px 14px;font-size:13px;background:#fff;">'
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_abertura"]}</span>'
                 f' e oração | <strong>Comentários iniciais</strong> (1 min)</div>')

    html += '<div style="margin-top:8px;">'
    html += sec_header("TESOUROS DA PALAVRA DE DEUS", C_TES)
    for it in d.get("tesouros", []):
        html += row(it["num"], it["titulo"], it.get("duracao", ""), "#f0f4ff", C_TES_I)
    html += '</div>'

    html += '<div style="margin-top:8px;">'
    html += sec_header("FAÇA SEU MELHOR NO MINISTÉRIO", C_MIN)
    for it in d.get("ministerio", []):
        html += row(it["num"], it["titulo"], it.get("duracao", ""), "#fffcf0", C_MIN_I)
    html += '</div>'

    html += '<div style="margin-top:8px;">'
    html += sec_header("NOSSA VIDA CRISTÃ", C_NVC)
    if d.get("cantico_meio"):
        html += (f'<div style="padding:6px 14px;background:#fff5f5;border-bottom:1px solid #e8e8e8;">'
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_meio"]}</span></div>')
    for it in d.get("vida_crista", []):
        html += row(it["num"], it["titulo"], it.get("duracao", ""), "#fff5f5", C_NVC_I)
    html += '</div>'

    if d.get("cantico_final"):
        html += (f'<hr style="margin:0;border:0;border-top:1px solid #ddd;">'
                 f'<div style="padding:9px 14px;font-size:13px;background:#fff;">'
                 f'<strong>Comentários finais</strong> (3 min) | '
                 f'<span style="color:{C_CANT};font-weight:bold;">Cântico {d["cantico_final"]}</span>'
                 f' e oração</div>')

    html += '</div>'
    return html


def aba_anuncios(pode_editar=True):
    if not pode_editar:
        permissoes.aviso_somente_leitura()
        abas_labels = ["🗂️ Postagens"]
    else:
        abas_labels = ["✏️ Nova Postagem", "🗂️ Gerenciar Postagens"]

    sub_an = st.tabs(abas_labels)

    if pode_editar:
        with sub_an[0]:
            tipo = st.radio(
                "Tipo",
                ["📝 Texto / Markdown", "🖼️ Imagem (JPEG/PNG)", "📅 Agenda de Reunião"],
                horizontal=True
            )

            if tipo == "📝 Texto / Markdown":
                titulo_txt  = st.text_input("Título (opcional)")
                conteudo_md = st.text_area("Conteúdo", height=200)
                if conteudo_md:
                    with st.expander("Pré-visualização"):
                        st.markdown(conteudo_md)
                if st.button("📤 Publicar", type="primary", use_container_width=True):
                    if conteudo_md.strip():
                        salvar_anuncio({"tipo": "texto", "titulo": titulo_txt or "Anúncio",
                                        "conteudo_html": conteudo_md, "renderizar_markdown": True})
                        st.success("✅ Publicado!")
                        st.rerun()
                    else:
                        st.error("Conteúdo vazio.")

            elif tipo == "🖼️ Imagem (JPEG/PNG)":
                titulo_img = st.text_input("Legenda (opcional)")
                arquivo    = st.file_uploader("Imagem", type=["jpg","jpeg","png"])
                if arquivo:
                    st.image(arquivo, use_column_width=True)
                    if st.button("📤 Publicar Imagem", type="primary", use_container_width=True):
                        img_bytes = arquivo.read()
                        mime  = "image/png" if arquivo.name.endswith(".png") else "image/jpeg"
                        b64   = base64.b64encode(img_bytes).decode("utf-8")
                        html_img = (f'<div style="text-align:center;padding:10px;">'
                                    f'<img src="data:{mime};base64,{b64}" '
                                    f'style="max-width:100%;border-radius:8px;" />'
                                    + (f'<p style="margin-top:8px;color:#555;">{titulo_img}</p>'
                                       if titulo_img else "") + '</div>')
                        salvar_anuncio({"tipo": "imagem", "titulo": titulo_img or arquivo.name,
                                        "conteudo_html": html_img, "renderizar_markdown": False})
                        st.success("✅ Imagem publicada!")
                        st.rerun()

            elif tipo == "📅 Agenda de Reunião":
                col_a, col_b = st.columns(2)
                data_texto = col_a.text_input("Período", placeholder="18-24 DE MAIO")
                escritura  = col_b.text_input("Escritura", placeholder="ISAÍAS 62-64")

                col_c, col_d, col_e = st.columns(3)
                cant_ab   = col_c.text_input("Cântico Abertura", placeholder="44")
                cant_meio = col_d.text_input("Cântico NVC",      placeholder="115")
                cant_fin  = col_e.text_input("Cântico Final",    placeholder="151")

                st.markdown("---")
                st.markdown('<div style="background:#1a3566;color:white;padding:7px 12px;'
                            'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                            'TESOUROS DA PALAVRA DE DEUS</div>', unsafe_allow_html=True)
                n_tes = st.number_input("Nº itens", 1, 6, 3, key="n_tes")
                tesouros = []
                for i in range(int(n_tes)):
                    c1, c2 = st.columns([4, 1])
                    t     = c1.text_input(f"Item {i+1}", key=f"tes_t_{i}",
                                          label_visibility="collapsed", placeholder=f"Item {i+1}")
                    d_dur = c2.text_input("Dur.", key=f"tes_d_{i}",
                                          label_visibility="collapsed", placeholder="10 min")
                    tesouros.append({"num": i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                st.markdown('<div style="background:#8a6200;color:white;padding:7px 12px;'
                            'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                            'FAÇA SEU MELHOR NO MINISTÉRIO</div>', unsafe_allow_html=True)
                n_min = st.number_input("Nº itens", 1, 6, 3, key="n_min")
                ministerio = []
                base_min = int(n_tes)
                for i in range(int(n_min)):
                    c1, c2 = st.columns([4, 1])
                    t     = c1.text_input(f"Item {base_min+i+1}", key=f"min_t_{i}",
                                          label_visibility="collapsed", placeholder=f"Item {base_min+i+1}")
                    d_dur = c2.text_input("Dur.", key=f"min_d_{i}",
                                          label_visibility="collapsed", placeholder="")
                    ministerio.append({"num": base_min + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                st.markdown('<div style="background:#cc0000;color:white;padding:7px 12px;'
                            'border-radius:5px;font-weight:bold;margin-bottom:6px;">'
                            'NOSSA VIDA CRISTÃ</div>', unsafe_allow_html=True)
                n_nvc = st.number_input("Nº itens", 1, 10, 2, key="n_nvc")
                vida_crista = []
                base_nvc = int(n_tes) + int(n_min)
                for i in range(int(n_nvc)):
                    c1, c2 = st.columns([4, 1])
                    t     = c1.text_input(f"Item {base_nvc+i+1}", key=f"nvc_t_{i}",
                                          label_visibility="collapsed", placeholder=f"Item {base_nvc+i+1}")
                    d_dur = c2.text_input("Dur.", key=f"nvc_d_{i}",
                                          label_visibility="collapsed", placeholder="")
                    vida_crista.append({"num": base_nvc + i + 1, "titulo": t, "duracao": d_dur})

                st.markdown("---")
                agenda_dados = {
                    "data_texto": data_texto, "escritura": escritura,
                    "cantico_abertura": cant_ab, "cantico_meio": cant_meio,
                    "cantico_final":    cant_fin,
                    "tesouros": tesouros, "ministerio": ministerio, "vida_crista": vida_crista,
                }
                col_prev, col_pub = st.columns(2)
                with col_prev:
                    if st.button("👁 Pré-visualizar", use_container_width=True):
                        st.markdown(gerar_html_agenda(agenda_dados), unsafe_allow_html=True)
                with col_pub:
                    if st.button("📤 Publicar Agenda", use_container_width=True, type="primary"):
                        if not data_texto.strip():
                            st.error("Informe o período.")
                        else:
                            salvar_anuncio({
                                "tipo": "agenda", "titulo": data_texto,
                                "conteudo_html": gerar_html_agenda(agenda_dados),
                                "renderizar_markdown": False,
                                "dados_agenda": agenda_dados,
                            })
                            st.success(f"✅ Agenda '{data_texto}' publicada!")
                            st.rerun()

    idx_lista = 1 if pode_editar else 0
    with sub_an[idx_lista]:
        anuncios = carregar_anuncios()
        if not anuncios:
            st.info("Nenhuma postagem encontrada.")
        else:
            st.caption(f"{len(anuncios)} postagem(ns) · mais recente primeiro")
            for a in anuncios:
                tipo_icon = {"texto": "📝", "imagem": "🖼️", "agenda": "📅"}.get(a.get("tipo",""), "📌")
                ts       = a.get("data_postagem")
                data_str = ts.strftime("%d/%m/%Y %H:%M") if hasattr(ts, "strftime") else "–"
                with st.expander(f"{tipo_icon} {a.get('titulo','Sem título')}  ·  {data_str}"):
                    if a.get("renderizar_markdown"):
                        st.markdown(a.get("conteudo_html",""), unsafe_allow_html=False)
                    else:
                        st.markdown(a.get("conteudo_html",""), unsafe_allow_html=True)
                    if pode_editar:
                        st.markdown("---")
                        if st.button("🗑 Deletar", key=f"del_an_{a['id']}", type="secondary"):
                            deletar_anuncio(a["id"])
