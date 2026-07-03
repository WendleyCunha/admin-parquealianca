# =============================================================
# sidebar.py
# Barra lateral: marca/logo, seletor de mês de análise, KPIs
# rápidos e informações do usuário logado.
#
# Origem: Seção 12 ("SIDEBAR") do antigo main.py monolítico.
# Único ajuste: o brasão 🕊️ fixo virou o logo personalizado
# (estilo.get_logo_base64) quando existe um arquivo de logo na
# raiz do projeto — se não houver, mantém o emoji original.
# =============================================================
import streamlit as st

from estilo import get_logo_base64


def renderizar_sidebar(df, mes_vigente):
    with st.sidebar:
        logo_b64, logo_mime = get_logo_base64()
        if logo_b64:
            marca_html = (
                f'<img src="data:{logo_mime};base64,{logo_b64}" '
                f'style="width:44px;height:44px;object-fit:contain;margin-bottom:2px;" />'
            )
        else:
            marca_html = '<div style="font-size:2rem;margin-bottom:4px;">🕊️</div>'

        st.markdown(f"""
        <div class="sidebar-brand">
            {marca_html}
            <div class="sidebar-brand-title">Parque Aliança</div>
            <div class="sidebar-brand-sub">Gestão · v5.2</div>
        </div>
        <hr class="sidebar-divider">
        """, unsafe_allow_html=True)

        st.markdown(
            '<p style="color:#6b7280;font-size:0.7rem;text-transform:uppercase;'
            'letter-spacing:0.1em;font-weight:700;margin-bottom:4px;">Mês de Análise</p>',
            unsafe_allow_html=True
        )

        meses_disponiveis = sorted(df['mes_referencia'].unique()) if not df.empty else [mes_vigente]
        idx_default = len(meses_disponiveis) - 1
        if mes_vigente in meses_disponiveis:
            idx_default = meses_disponiveis.index(mes_vigente)

        mes_sel = st.selectbox(
            "Mês", meses_disponiveis, index=idx_default, label_visibility="collapsed"
        )

        eh_vigente = (mes_sel == mes_vigente)
        if eh_vigente:
            st.markdown("""
            <div class="mes-badge">
                <span class="mes-dot"></span>MÊS VIGENTE
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="display:inline-flex;align-items:center;gap:6px;
                background:#1f2937;border:1px solid #374151;border-radius:999px;
                padding:5px 14px;font-size:0.75rem;font-weight:700;color:#6b7280;">
                📅 HISTÓRICO</div>""", unsafe_allow_html=True)

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        if not df.empty:
            df_mes_side = df[df['mes_referencia'] == mes_sel]
            df_id_side  = df_mes_side[df_mes_side['status_validacao'] == "IDENTIFICADO"]
            df_tri_side = df_mes_side[df_mes_side['status_validacao'] == "TRIAGEM"]

            st.markdown(f"""
            <div style="display:grid;gap:6px;">
              <div class="pa-metric">
                <div class="pa-metric-value">{len(df_id_side)}</div>
                <div class="pa-metric-label">Identificados</div>
              </div>
              <div class="pa-metric">
                <div class="pa-metric-value" style="color:#ef4444">{len(df_tri_side)}</div>
                <div class="pa-metric-label">Em triagem</div>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

        usuario = st.session_state.get("usuario_logado", "Admin")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
          <div style="width:32px;height:32px;border-radius:50%;
            background:linear-gradient(135deg,#d97706,#f59e0b);
            display:flex;align-items:center;justify-content:center;
            font-weight:800;font-size:0.85rem;color:#000;">{usuario[0].upper()}</div>
          <div>
            <div style="font-weight:700;font-size:0.82rem;color:#f9fafb;">{usuario}</div>
            <div style="font-size:0.68rem;color:#6b7280;text-transform:uppercase;
                letter-spacing:0.05em;">Administrador</div>
          </div>
        </div>""", unsafe_allow_html=True)

        if st.button("Sair", use_container_width=True):
            for k in ["autenticado", "usuario_logado"]:
                st.session_state.pop(k, None)
            st.rerun()

    return mes_sel
