# utils/bootstrap.py
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

COMPANIES = {
    "ISOFT":   {"name": "iSOFT",         "logo": "https://b3660930.smushcdn.com/3660930/wp-content/uploads/2024/03/iSOFT-Logo-Tag-New-e1721176700423.png?lossy=2&strip=1&webp=1"},
    "NOSTINOS": {"name": "Nostinos Food", "logo": "https://nostinos.coxtech.com/wp-content/uploads/2025/06/nostinos-logo.png"},
    "COXTECH": {"name": "Coxtech",       "logo": "https://coxtech.com/wp-content/uploads/2022/05/Logo-Light-COXTECH-1.svg"},
}

TZ_CHOICES = {
    "Australia/Sydney":   "Australia/Sydney (AEST/AEDT)",
    "Australia/Melbourne":"Australia/Melbourne",
    "Australia/Brisbane": "Australia/Brisbane",
    "Australia/Perth":    "Australia/Perth",
    "Australia/Adelaide": "Australia/Adelaide",
    "Australia/Darwin":   "Australia/Darwin",
    "Australia/Hobart":   "Australia/Hobart",
    "Asia/Kolkata":       "India (IST)",
    "UTC":                "UTC",
}

def ensure_bootstrap(page_title: str, page_icon: str = "📊"):
    """Shared setup for all pages: page_config, brand/tz bootstrap form, sidebar, greeting."""
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # First-run setup form
    if "brand_key" not in st.session_state or "tz_key" not in st.session_state:

        # --- Developer branding at the top ---
        st.markdown(
            """
            <div style="text-align:center; margin-bottom:1rem;">
                <small style="color:grey; font-size:0.9rem;">Developed by</small><br>
                <img src="https://b3660930.smushcdn.com/3660930/wp-content/uploads/2024/03/iSOFT-Logo-Tag-New-e1721176700423.png?lossy=2&strip=1&webp=1"
                    alt="iSOFT ANZ" width="180">
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.form("bootstrap_form", border=True):
            st.subheader("🔧 Setup")
            brand_key = st.selectbox(
                "Which company are we using the app for?",
                list(COMPANIES.keys()),
                format_func=lambda k: COMPANIES[k]["name"],
                index=0,
            )
            tz_key = st.selectbox(
                "Which timezone?",
                list(TZ_CHOICES.keys()),
                index=0,
                format_func=lambda k: TZ_CHOICES[k],
            )
            if st.form_submit_button("Start"):
                st.session_state["brand_key"] = brand_key
                st.session_state["tz_key"] = tz_key
                st.rerun()

        st.stop()


    # Safe to read
    brand_key = st.session_state["brand_key"]
    tz_key    = st.session_state["tz_key"]
    brand     = COMPANIES[brand_key]


    # Sidebar branding + quick settings
    st.sidebar.image(brand["logo"], width=200)
    with st.sidebar.expander("Settings"):
    
        new_brand = st.selectbox(
            "Company", list(COMPANIES.keys()),
            index=list(COMPANIES.keys()).index(brand_key),
            format_func=lambda k: COMPANIES[k]["name"]
        )
        new_tz = st.selectbox(
            "Timezone", list(TZ_CHOICES.keys()),
            index=list(TZ_CHOICES.keys()).index(tz_key),
            format_func=lambda k: TZ_CHOICES[k]
        )
        if new_brand != brand_key or new_tz != tz_key:
            st.session_state["brand_key"] = new_brand
            st.session_state["tz_key"] = new_tz
            st.rerun()

    # Greeting (timezone-aware)
    now = datetime.now(ZoneInfo(tz_key))
    hour = now.hour
    if 0 <= hour < 5:
        greeting = "Night Owl"
    elif 5 <= hour < 12:
        greeting = "Good Morning"
    elif 12 <= hour < 17:
        greeting = "Good Afternoon"
    elif 17 <= hour < 21:
        greeting = "Good Evening"
    else:
        greeting = "Good Night"

    st.markdown(
        f"<h4 style='text-align: center; color: grey;'>Hello, {greeting}! "
        f"({now.strftime('%a %d %b %Y, %I:%M %p')} — {tz_key}) 👋</h4>",
        unsafe_allow_html=True
    )

    return {
        "brand_key": brand_key,
        "tz_key": tz_key,
        "brand": brand,
        "now": now,
        "greeting": greeting,
    }
