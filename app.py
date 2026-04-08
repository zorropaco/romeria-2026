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

# ---------------------------------------------------------------
# SIDEBAR — Admin
# ---------------------------------------------------------------
with st.sidebar:
    st.write("🔒 Acceso Admin")
    admin_pwd = st.text_input("Contraseña admin", type="password", key="admin_pwd")

# ---------------------------------------------------------------
# FLUJO PRINCIPAL
# ---------------------------------------------------------------
if admin_pwd == st.secrets["general"]["admin_password"]:
    st.success("✅ Modo Admin Activado")
    mostrar_admin(config)

else:
    # Inicializamos el flag de sesión si no existe
    if "acceso_ok" not in st.session_state:
        st.session_state["acceso_ok"] = False

    # Si aún no ha entrado → pantalla de acceso
    if not st.session_state["acceso_ok"]:
        st.markdown("---")
        col_izq, col_centro, col_der = st.columns([1, 2, 1])
        with col_centro:
            st.markdown("### 🔐 Acceso Restringido")
            st.write("Esta app es solo para los asistentes a la Romería. Introduce el código que te han enviado por WhatsApp.")
            codigo = st.text_input("Código de acceso", type="password", key="codigo_invitado")
            if st.button("Entrar 🚀", type="primary"):
                if codigo == st.secrets["general"]["codigo_invitados"]:
                    st.session_state["acceso_ok"] = True
                    st.rerun()
                else:
                    st.error("❌ Código incorrecto. Pídelo a los organizadores.")

    # Si ya ha entrado → formulario normal
    else:
        mostrar_formulario(config)