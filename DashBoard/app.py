import streamlit as st
import requests
import pandas as pd

# ------------------------
# Konfiguracja strony
# ------------------------
st.set_page_config(
    page_title="BetGuard Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.title("🎯 BetGuard – ValueBet Detector")

# ------------------------
# Sidebar: filtry
# ------------------------
st.sidebar.header("Filtry")
BET_TYPES = ["Home Win", "Draw", "Away Win"]
selected_types = st.sidebar.multiselect(
    "Typ zakładu",
    options=BET_TYPES,
    default=BET_TYPES
)

# ------------------------
# Fetch danych
# ------------------------
@st.cache_data(ttl=60)
def fetch_recommendations():
    try:
        r = requests.get("http://go-backend:8080/recommendations", timeout=5)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except Exception as e:
        st.sidebar.error(f"❌ Błąd ładowania danych: {e}")
        return pd.DataFrame()

with st.spinner("⏳ Pobieram rekomendacje…"):
    df = fetch_recommendations()

if df.empty:
    st.warning("Brak danych do wyświetlenia.")
    st.stop()

# ------------------------
# Przygotowanie DataFrame
# ------------------------
# Usuń date jeżeli jest
if "date" in df.columns:
    df = df.drop(columns=["date"])
# Rozbij po typach zakładów i zaokrąglij
df = df[df["bet_type"].isin(selected_types)]
for col in ["model_probability", "implied_probability", "delta"]:
    df[col] = df[col].round(2)

# ------------------------
# Zakładki
# ------------------------
tab1, tab2 = st.tabs(["📋 Wszystkie mecze", "⚡ ValueBety"])

with tab1:
    st.subheader("Wszystkie mecze")
    display = df[["match","bet_type","model_probability","implied_probability","delta"]].copy()
    display.columns = ["Mecz","Typ zakładu","Model [%]","Implied [%]","Delta [%]"]
    st.dataframe(display, use_container_width=True, height=600)

with tab2:
    st.subheader("⚡ ValueBety")
    vb = df[df["alert"] == True]
    if vb.empty:
        st.info("Brak valuebetów w aktualnych meczach.")
    else:
        # dla każdego value bet – expander
        for _, row in vb.iterrows():
            with st.expander(f"{row['match']}  –  {row['bet_type']}"):
                cols = st.columns(3, gap="small")
                cols[0].metric("Model [%]", f"{row['model_probability']:.2f}")
                cols[1].metric("Implied [%]", f"{row['implied_probability']:.2f}")
                delta_str = f"{row['delta']:+.2f}"
                cols[2].metric("Delta [%]", delta_str)
