import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="BetGuard Dashboard", layout="wide")

st.title("🎯 BetGuard - Risk Monitor Dashboard")

# Pobierz dane z GoBackend
try:
    response = requests.get("http://go-backend:8080/recommendations")
    recommendations = response.json()
except Exception as e:
    st.error(f"Problem z połączeniem do backendu: {e}")
    recommendations = []

if recommendations:
    df = pd.DataFrame(recommendations)

    # Pokaż wszystkie
    st.subheader("Wszystkie mecze:")
    st.dataframe(df)

    # Filtrowanie - tylko alerty
    st.subheader("⚡ Mecze z przestrzelonym kursem:")
    alert_df = df[df["alert"] == True]

    if not alert_df.empty:
        st.dataframe(alert_df)
    else:
        st.info("Brak alertów - kursy wyglądają dobrze!")

else:
    st.warning("Brak danych z backendu.")
