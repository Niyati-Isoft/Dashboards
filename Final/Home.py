# streamlitapp.py — Home (circles + links underneath)
import streamlit as st
from utils.bootstrap import ensure_bootstrap

ctx = ensure_bootstrap(page_title="Home — iSOFT Dashboards", page_icon="🏠")
# ----------------- Header -----------------
st.markdown("""
<style>
:root {
  --glow-blue: rgba(0, 140, 255, 0.45);
  --glow-blue-strong: rgba(0, 140, 255, 0.75);
}

.circle-card {
  width: 320px; height: 320px; border-radius: 50%;
  position: relative; display: grid; place-items: center;
  background: #ffffff;               /* pure white inside */
  box-shadow:
    0 0 0 6px #ffffff inset,        /* inner white rim to block bleed */
    0 10px 25px rgba(0,0,0,0.12),
    0 0 30px var(--glow-blue);      /* outer blue glow */
  transition: transform 220ms ease, box-shadow 220ms ease;
  overflow: hidden; margin: 1.5rem auto 0 auto;
}

.circle-card::before {
  content: ""; position: absolute; inset: -30px; border-radius: 50%;
  background: radial-gradient(circle, var(--glow-blue) 20%, transparent 70%);
  filter: blur(40px); z-index: -1;   /* behind the white circle */
}

.circle-card:hover {
  transform: translateY(-10px) scale(1.05);
  box-shadow:
    0 0 0 6px #ffffff inset,
    0 15px 35px rgba(0,0,0,0.25),
    0 0 55px var(--glow-blue-strong);
}

/* content inside */
.circle-content { z-index: 1; text-align: center; }
.circle-emoji   { font-size: 3rem; margin-bottom: .4rem; display: block; }
.circle-title   { font-weight: 700; font-size: 1.3rem; color: #2b2f36; margin: 0; }
.circle-subtitle{ color: #616b76; font-size: 1rem; margin-top: .3rem; }
</style>
""", unsafe_allow_html=True)


# ----------------- Layout -----------------
c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown(
        f"""
        <div class="circle-card">
          <div class="circle-content">
            <span class="circle-emoji"></span>
            <h3 class="circle-title">Financial Dashboard</h3>
            <div class="circle-subtitle">{ctx['brand']['name']}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # visible, reliable navigation link under the circle
    st.markdown('<div class="circle-link-wrap">', unsafe_allow_html=True)
    st.page_link("pages/1_Financial_Dashboard.py", label="➡️ Open Financial Dashboard")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown(
        f"""
        <div class="circle-card">
          <div class="circle-content">
            <span class="circle-emoji"></span>
            <h3 class="circle-title">Subscription Dashboard</h3>
            <div class="circle-subtitle">{ctx['brand']['name']}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="circle-link-wrap">', unsafe_allow_html=True)
    st.page_link("pages/2_Subscription_Dashboard.py", label="➡️ Open Subscription Dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
