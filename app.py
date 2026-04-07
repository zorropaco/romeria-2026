import streamlit as st
import yaml
from src.ui_formulario import mostrar_formulario
from src.ui_admin import mostrar_admin

st.set_page_config(page_title="App Romería", page_icon="🍖", layout="wide")


def cargar_config():
    with open("config.yaml", "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


config = cargar_config()

st.title(f"🍖 {config['evento']['nombre']}")

with st.sidebar:
    st.write("🔒 Acceso Admin")
    admin_pwd = st.text_input("Contraseña", type="password")

if admin_pwd == "admin":
    st.success("✅ Modo Admin Activado")
    mostrar_admin(config)
else:
    mostrar_formulario(config)