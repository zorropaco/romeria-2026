import streamlit as st
from src.data_manager import guardar_respuesta # ✅ IMPORT ARRIBA

def mostrar_formulario(config):
    st.write("Rellena tus preferencias. Todas las opciones son cerradas para facilitar el cálculo de la compra.")

    # 1. Datos personales
    st.subheader("👤 Datos Personales")
    st.text_input("1er Nombre y 1er Apellido *", key="nombre_input") # ✅ Guardamos directo en session_state
    st.text_input("Correo electrónico * (Para evitar duplicados)", key="correo_input", help="Si lo rellenas dos veces, usaremos este correo para actualizar tus datos.")
    
    st.divider()

    # 2. Asistencia
    st.subheader("📅 ¿Qué días vas a venir?")
    st.write("Selecciona los días que asistirás para ver tus opciones de comida.")
    
    dias_disponibles = list(config["calendario"].keys())
    cols_dias = st.columns(len(dias_disponibles))
    
    dias_asistencia = []
    
    for i, dia in enumerate(dias_disponibles):
        with cols_dias[i]:
            if st.checkbox(f"Ir el {dia}", key=f"asiste_{dia}"):
                dias_asistencia.append(dia)

    st.divider()

    if not dias_asistencia:
        st.info("👆 Por favor, selecciona al menos un día de asistencia para continuar.")
        return  

    # 3. EL FORMULARIO
    st.subheader("🍽️ Opciones de Menú")
    st.write(f"*Calcularemos tus cantidades en base a los **{len(dias_asistencia)} días** de asistencia seleccionados.*")
    
    with st.form("form_romeria", clear_on_submit=False):
        
        # --- BEBIDAS ---
        st.markdown("### 🍹 Bebida")
        col1, col2 = st.columns(2)
        with col1:
            alcohol = st.selectbox("Bebida Alcohólica principal", config["menu_bebida"]["alcohol"])
            refresco_alcohol = st.selectbox("Refresco para el alcohol", config["menu_bebida"]["refrescos"])
        with col2:
            refresco1 = st.selectbox("Refresco comida (Opción 1)", config["menu_bebida"]["refrescos"])
            refresco2 = st.selectbox("Refresco comida (Opción 2)", config["menu_bebida"]["refrescos"])

        st.write("**Otras bebidas:**")
        cols = st.columns(len(config["menu_bebida"]["extras"]))
        for i, extra in enumerate(config["menu_bebida"]["extras"]):
            with cols[i]:
                st.radio(f"¿{extra}?", ["SÍ", "NO"], horizontal=True, key=f"extra_{extra}")

        # Chupitos
        st.write("**Chupitos:**")
        toma_chupito = st.radio("¿Le pegas al chupiteo?", ["SÍ", "NO"], horizontal=True, key="toma_chupito")
        if toma_chupito == "SÍ":
            chupito_elegido = st.selectbox(
                "Elige tu favorito (Compraremos el más votado)", 
                config["menu_bebida"]["chupitos_opciones"],
                key="chupito_elegido_ui"
            )
        else:
            chupito_elegido = "NO"

        st.divider()

        # --- COMIDA ---
        st.markdown("### 🍔 Comida")
        opciones_comida = list(config["menu_comida"].keys())

        # ✅ TU LÓGICA ORIGINAL: Diccionario anidado limpio
        comidas_elegidas = {}

        for dia in dias_asistencia:
            comidas_del_dia = config["calendario"][dia]
            st.markdown(f"**📅 {dia}**")
            
            comidas_elegidas[dia] = {}
            for tipo_comida, tipo_menu in comidas_del_dia.items():
                
                if tipo_menu == "eleccion":
                    comidas_elegidas[dia][tipo_comida] = st.multiselect(
                        f"Elige qué quieres para la {tipo_comida}",
                        options=opciones_comida,
                        key=f"comida_{dia}_{tipo_comida}"
                    )
                
                elif tipo_menu == "fijo":
                    come_fijo = st.checkbox(
                        f"🍛 ¿Comes al {tipo_comida}? (Menú fijo para todos)", 
                        value=True, 
                        key=f"comida_{dia}_{tipo_comida}"
                    )
                    comidas_elegidas[dia][tipo_comida] = ["Menú Fijo"] if come_fijo else ["No asiste"]
            
            st.write("") 

        st.divider()
        enviado = st.form_submit_button("Guardar Mis Respuestas", type="primary")

        if enviado:
            # ✅ LEER EL NOMBRE DESDE SESSION STATE POR SEGURIDAD
            nombre_actual = st.session_state.get("nombre_input", "").strip()
            correo_actual = st.session_state.get("correo_input", "").strip().lower() # Lo pasamos a minúsculas por seguridad
            
            if not nombre_actual:
                st.error("❌ Por favor, escribe tu nombre arriba del todo.")
            elif "@" not in correo_actual or "." not in correo_actual:
                # Validación básica de email a prueba de tontos
                st.error("❌ Por favor, escribe un correo electrónico válido.")
            else:
                respuestas_extras = {}
                for extra in config["menu_bebida"]["extras"]:
                    respuestas_extras[extra] = st.session_state[f"extra_{extra}"]

                # Añadimos el correo al Payload
                payload = {
                    "Nombre": nombre_actual,
                    "Correo": correo_actual,  # <--- NUEVO
                    "Dias_Asistencia": ", ".join(dias_asistencia),
                    "Num_Dias": len(dias_asistencia),
                    "Bebida_Alcohol": alcohol,
                    "Refresco_Alcohol": refresco_alcohol,
                    "Refresco_Comida1": refresco1,
                    "Refresco_Comida2": refresco2,
                    "Extras": respuestas_extras,
                    "Comida": comidas_elegidas,       
                    "Chupito_Elegido": chupito_elegido
                }

                if guardar_respuesta(payload):
                    st.success(f"✅ ¡Opciones guardadas, {nombre_actual}! Vas a asistir {len(dias_asistencia)} días.")
                    st.balloons()
                else:
                    st.error("Hubo un problema al guardar los datos.")
