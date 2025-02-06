import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    return pd.read_json("dados/base_iniciativas_consolidada.json")

df = load_data()

st.title("Consulta de Iniciativas Estruturantes")
st.dataframe(df)
