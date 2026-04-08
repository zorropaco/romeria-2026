import streamlit as st
import pandas as pd
import os
from src.procesador import calcular_lista_compra, contar_menus_fijos
from src.procesador import calcular_bebidas
from src.procesador import calcular_coste_comida




def mostrar_admin(config):
    st.header("⚙️ Panel de Control - Romería")
        
    from src.data_manager import leer_datos, guardar_estado_pagos
    with st.spinner("Cargando datos desde Google Sheets..."):
        df_raw = leer_datos()
    if df_raw.empty:
        st.warning("⏳ Aún no hay respuestas en Google Sheets.")
        return
        
    # Rellenar los valores nulos (NaN)
    df_raw = df_raw.fillna("")
    
    # Crear pestañas para organizar la vista
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "👥 Gente y Asistencia", 
        "🍹 Bebidas", 
        "🍔 Resumen Comida", 
        "💰 Tesorería", 
        "🧾 Subir Tickets", 
        "📈 Gastos Reales"
    ])
    
    # ----- PESTAÑA 1: GENTE Y ASISTENCIA -----
    with tab1:
        st.subheader("Control de Asistencia y Pagos")
        import math
        
        # 1. Asegurarnos de que existe la columna 'Pagado'
        if "Pagado" not in df_raw.columns:
            df_raw["Pagado"] = False
        else:
            df_raw["Pagado"] = df_raw["Pagado"].map(
                lambda x: True if str(x).upper() in ["TRUE", "1", "SÍ", "SI"] else False
            )

        # 2. Calcular cuotas personalizadas
        total_dias_evento = len(config.get("calendario", {}))
        if total_dias_evento == 0: total_dias_evento = 3 # Por seguridad
        
        cuotas_config = config.get("cuotas", {})
        cuota_normal = cuotas_config.get("normal", 0.0)
        cuota_sin_alcohol = cuotas_config.get("sin_alcohol", 0.0)
        
        # Precio por día suelto (siempre basado en la cuota normal y redondeado arriba)
        precio_por_dia = math.ceil(cuota_normal / total_dias_evento) if total_dias_evento > 0 else 0

        def calcular_a_pagar(row):
            try:
                dias_asiste = int(row["Num_Dias"])
            except:
                dias_asiste = 0
                
            bebe = str(row["Bebida_Alcohol"]).upper() != "NADA"
            
            if dias_asiste >= total_dias_evento:
                # Romería completa
                return float(cuota_normal if bebe else cuota_sin_alcohol)
            else:
                # Romería por días (paga el precio del día independientemente del alcohol)
                return float(dias_asiste * precio_por_dia)

        columnas_gente = ["Nombre", "Num_Dias", "Dias_Asistencia", "Bebida_Alcohol", "Pagado"]
        df_gente = df_raw[columnas_gente].copy()
        
        # Aplicamos la fórmula para crear la nueva columna
        df_gente["A Pagar (€)"] = df_gente.apply(calcular_a_pagar, axis=1)
        
        # Reordenamos columnas para que se vea bien
        df_gente = df_gente[["Nombre", "Num_Dias", "Dias_Asistencia", "Bebida_Alcohol", "A Pagar (€)", "Pagado"]]

        st.info(f"ℹ️ **Regla de cobro:** Romería completa ({total_dias_evento} días) a **{cuota_normal}€** (o **{cuota_sin_alcohol}€** sin alcohol). Días sueltos a **{precio_por_dia}€/día**.")
        
        # 3. Mostrar tabla editable
        edited_df = st.data_editor(
            df_gente,
            column_config={
                "Pagado": st.column_config.CheckboxColumn("¿Ha pagado?", help="Marca si ya ha abonado su cuota", default=False),
                "A Pagar (€)": st.column_config.NumberColumn("A Pagar (€)", format="%.2f €", disabled=True),
                "Nombre": st.column_config.TextColumn(disabled=True),
                "Num_Dias": st.column_config.NumberColumn(disabled=True),
                "Dias_Asistencia": st.column_config.TextColumn(disabled=True),
                "Bebida_Alcohol": st.column_config.TextColumn(disabled=True),
            },
            disabled=["Nombre", "Num_Dias", "Dias_Asistencia", "Bebida_Alcohol", "A Pagar (€)"],
            hide_index=True,
            width="stretch"
        )
        
        # 4. Guardar cambios si el usuario hizo algún check
        # REEMPLAZAR POR:
        cambios_detectados = not edited_df["Pagado"].equals(df_gente["Pagado"])

        if cambios_detectados:
            if st.button("💾 Guardar cambios de pagos", type="primary"):
                df_raw["Pagado"] = edited_df["Pagado"]
                if guardar_estado_pagos(df_raw):
                    st.success("✅ ¡Estado de pagos actualizado!")
                    st.rerun()
                else:
                    st.error("❌ Error al guardar. Inténtalo de nuevo.")
        else:
            st.caption("✅ Sin cambios pendientes.")
            
        # Métrica visual
        total_personas = len(edited_df)
        pagados = edited_df["Pagado"].sum()
        st.metric(label="Progreso de Pagos", value=f"{pagados} / {total_personas} han pagado")


    # ----- PESTAÑA 2: BEBIDAS Y TESORERÍA -----
    with tab2:
        st.subheader("🛒 Lista de la Compra y Tesorería: BEBIDAS")
        df_bebidas_compra = calcular_bebidas(df_raw, config)
        
        # --- SECCIÓN DE MÉTRICAS (Igual que en tu Excel) ---
        if not df_bebidas_compra.empty:
            # Agrupar por categoría
            resumen_gastos = df_bebidas_compra.groupby("Categoría")["Coste Total (€)"].sum()
            total_alcohol_euros = resumen_gastos.get("ALCOHOL", 0)
            total_cerveza_euros = resumen_gastos.get("CERVEZA", 0)
            total_vino_euros = resumen_gastos.get("VINO/MANZANILLA", 0)
            total_refresco_euros = resumen_gastos.get("REFRESCO", 0)
            gran_total_euros = resumen_gastos.sum()

            # Calcular botellas físicas para el ratio
            botellas_alcohol = df_bebidas_compra[df_bebidas_compra["Categoría"] == "ALCOHOL"]["Comprar (Botellas/Cajas)"].sum()
            botellas_refresco = df_bebidas_compra[df_bebidas_compra["Categoría"] == "REFRESCO"]["Comprar (Botellas/Cajas)"].sum()
            ratio_refresco = botellas_refresco / botellas_alcohol if botellas_alcohol > 0 else 0

            # Pintar las métricas de gasto
            st.markdown("### 💰 Resumen de Gastos")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("ALCOHOL", f"{total_alcohol_euros:.2f} €")
            col2.metric("CERVEZA", f"{total_cerveza_euros:.2f} €")
            col3.metric("VINO/MANZAN.", f"{total_vino_euros:.2f} €")
            col4.metric("REFRESCO", f"{total_refresco_euros:.2f} €")
            col5.metric("TOTAL BEBIDA", f"{gran_total_euros:.2f} €")

            # Pintar las métricas de botellas y ratio (como en tu foto)
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("🍾 Botellas Alcohol", int(botellas_alcohol))
            col_b.metric("🥤 Botellas Refresco", int(botellas_refresco))
            col_c.metric("⚖️ Ratio (Refrescos por Alcohol)", f"{ratio_refresco:.2f}")
            
            st.divider()
        
        # --- TABLA DETALLADA ---
        st.markdown("### 📋 Desglose por Bebida")
        # Ocultamos la columna 'Categoría' porque es solo para cálculos internos
        columnas_mostrar = ["Bebida", "Cantidad a Comprar", "Comprar (Botellas/Cajas)", "Precio Unidad (€)", "Coste Total (€)"]
        
        st.dataframe(
            df_bebidas_compra[columnas_mostrar].style.format({
                "Cantidad a Comprar": "{:.2f}",
                "Precio Unidad (€)": "{:.2f} €",
                "Coste Total (€)": "{:.2f} €"
            }).highlight_max(subset=['Coste Total (€)'], color='lightcoral'),
            width="stretch",
            hide_index=True
        )

    # ----- PESTAÑA 3: PROCESADOR DE COMIDA -----
    with tab3:
        st.subheader("🛒 Lista de la Compra Definitiva")

        # 1. Mostrar la lista de barbacoa (calculada con multiplicadores)
        st.markdown("#### 🥩 Carne / Barbacoa (A la carta)")
        df_compra = calcular_lista_compra(df_raw, config)
        df_compra.columns = [c.strip() for c in df_compra.columns]
        if not df_compra.empty:
            st.dataframe(
                df_compra.style.format("{:.2f}").highlight_max(subset=['Total'], color='lightgreen'),
                width="stretch"
            )
        else:
            st.info("Nadie ha seleccionado carne aún.")

        st.divider()

        # 2. Mostrar la lista de los menús fijos (Paella, etc)
        st.markdown("#### 🥘 Menús Fijos (Mediodía)")
        df_fijos = contar_menus_fijos(df_raw, config)
        if not df_fijos.empty:
            st.dataframe(df_fijos, hide_index=True)
        else:
            st.info("Nadie se ha apuntado a los menús de mediodía aún.")

        st.divider()

        # 3. Coste de comida (plancha + paella)
        st.markdown("#### 💰 Resumen Coste de Comida")

        resultado_comida = calcular_coste_comida(df_compra, df_raw, config)
        df_plancha = resultado_comida["df_plancha"]
        df_paella = resultado_comida["df_paella"]
        df_panaderia = resultado_comida.get("df_panaderia", pd.DataFrame())
        df_pescado = resultado_comida.get("df_pescado", pd.DataFrame())

        if not df_panaderia.empty:
            st.markdown("##### 🥖 Pan y Dulces")
            st.dataframe(df_panaderia, width="stretch", hide_index=True)

        if not df_pescado.empty:
            st.markdown("##### 🦐 Pescado y Marisco")
            st.dataframe(df_pescado, width="stretch", hide_index=True)


        resumen_comida = resultado_comida["resumen"]

        # Métricas de coste
        col1, col2, col3 = st.columns(3)
        col1.metric("Plancha (€)", f'{resumen_comida["Carne Plancha (€)"]:.2f} €')
        col2.metric("Paella (€)", f'{resumen_comida["Carne Paella (€)"]:.2f} €')
        col3.metric("Total Comida (€)", f'{resumen_comida["TOTAL COMIDA (€)"]:.2f} €')

        st.markdown("##### Detalle carne de plancha")
        df_plancha_show = df_plancha.copy()
        for col in ["Precio unitario (€)", "Coste total (€)"]:
            if col in df_plancha_show.columns:
                df_plancha_show[col] = df_plancha_show[col].map(lambda x: f"{x:.2f} €")

        st.dataframe(
            df_plancha_show,
            width="stretch",
            hide_index=True
        )
        st.caption("Las unidades se redondean según cada producto (pinchos en tarrinas, solomillo 1 cada 2 personas, etc.).")

        st.markdown("##### Detalle carne para paella")
        num_comensales_paella = len(df_raw) if df_raw is not None else 0
        st.info(
            f"Calculado para {num_comensales_paella} comensales — ratio base: 1.5 kg / 28 personas por tipo de carne."
        )

        df_paella_show = df_paella.copy()
        for col in ["Kg exactos", "Kg a comprar", "Precio €/kg", "Coste total (€)"]:
            if col in df_paella_show.columns:
                if "Precio" in col or "Coste" in col:
                    df_paella_show[col] = df_paella_show[col].map(lambda x: f"{x:.2f} €")
                else:
                    df_paella_show[col] = df_paella_show[col].map(lambda x: f"{x:.2f}")
                    
        st.dataframe(
            df_paella_show,
            width="stretch",
            hide_index=True
        )

    # ----- PESTAÑA 4: TESORERÍA -----
    with tab4:
        st.subheader("💰 Resumen de Tesorería")
        
        # 1. Recuperamos datos de comida y bebida de forma segura
        # REEMPLAZAR POR ESTO (Tab 4 se calcula sola):
        df_bebidas_tesoreria = calcular_bebidas(df_raw, config)

        if not df_bebidas_tesoreria.empty:
            resumen_beb = df_bebidas_tesoreria.groupby("Categoría")["Coste Total (€)"].sum()
            total_alcohol = resumen_beb.get("ALCOHOL", 0)
            total_cerveza = resumen_beb.get("CERVEZA", 0)
            total_vino    = resumen_beb.get("VINO/MANZANILLA", 0)
            total_refrescos = resumen_beb.get("REFRESCO", 0)
            total_bebida  = resumen_beb.sum()
        else:
            total_alcohol = total_cerveza = total_vino = total_refrescos = total_bebida = 0

        gasto_alcohol_puro   = total_alcohol + total_cerveza + total_vino
        gasto_solo_refrescos = total_refrescos
        
        gasto_alcohol_puro = total_alcohol + total_cerveza + total_vino
        gasto_solo_refrescos = total_refrescos
        
        # REEMPLAZAR POR ESTO:
        df_compra_tab4  = calcular_lista_compra(df_raw, config)
        resultado_tab4  = calcular_coste_comida(df_compra_tab4, df_raw, config)
        resumen_comida_tab4 = resultado_tab4["resumen"]

        total_comida    = resumen_comida_tab4.get("TOTAL COMIDA (€)", 0)
        detalle_plancha = resumen_comida_tab4.get("Carne Plancha (€)", 0)
        detalle_paella  = resumen_comida_tab4.get("Carne Paella (€)", 0)
        detalle_pan     = resumen_comida_tab4.get("Panadería (€)", 0)
        detalle_pescado = resumen_comida_tab4.get("Pescado/Marisco (€)", 0)
            
        # 1.2 Recuperamos gastos fijos desde el config.yaml
        fijos = config.get("gastos_fijos", {})
        coste_furgon = fijos.get("alquiler_furgon", 0.0)
        fianza_furgon = fijos.get("fianza_furgon", 0.0)
        coste_musica = fijos.get("equipo_musica", 0.0)
        coste_luz = fijos.get("licencia_luz", 0.0)
        coste_hielo = fijos.get("estimacion_hielo", 0.0)
        
        total_fijos = coste_furgon + fianza_furgon + coste_musica + coste_luz + coste_hielo

        # Gasto total sumando absolutamente todo
        total_gastos = total_bebida + total_comida + total_fijos
        
        # 2. DESGLOSE DE PRESUPUESTO
        st.markdown("### 🗂️ Desglose del Presupuesto")
        
        st.markdown("##### Comida")
        col1, col2, col3 = st.columns(3)
        col1.metric("🥩 Carne (Plancha + Paella)", f"{(detalle_plancha + detalle_paella):.2f} €")
        col2.metric("🥖 Panadería y Dulces", f"{detalle_pan:.2f} €")
        col3.metric("🦐 Pescado y Marisco", f"{detalle_pescado:.2f} €")
        
        st.markdown("##### Bebida y Gastos Fijos")
        col4, col5, col6, col7 = st.columns(4)
        col4.metric("🍹 Bebidas Total", f"{total_bebida:.2f} €")
        col5.metric("🧊 Hielo", f"{coste_hielo:.2f} €")
        col6.metric("💡 Punto de Luz", f"{coste_luz:.2f} €")
        col7.metric("🎵 Equipo de Música", f"{coste_musica:.2f} €")
        
        col8, col9, col10 = st.columns(3)
        col8.metric("🚐 Furgo + Fianza", f"{(coste_furgon + fianza_furgon):.2f} €")
        col9.metric("🔴 GASTO TOTAL", f"{total_gastos:.2f} €")
        
        st.divider()

        # 3. COMPARATIVA DE CUOTAS: CONFIGURADA vs SUGERIDA
        st.markdown("### 🧮 Análisis de Cuotas")
        
        cuotas_config = config.get("cuotas", {})
        cuota_oficial_normal = cuotas_config.get("normal", 0.0)
        cuota_oficial_sin_alcohol = cuotas_config.get("sin_alcohol", 0.0)

        num_totales = len(df_raw) if not df_raw.empty else 1
        num_bebedores = len(df_raw[df_raw["Bebida_Alcohol"] != "NADA"]) if not df_raw.empty else 1
        if num_bebedores == 0: num_bebedores = 1 
        
        # NUEVA LÓGICA EXACTA DE REPARTO
        # 1. La comida, los gastos fijos y LOS REFRESCOS se dividen entre TODOS por igual
        cuota_base_compartida = (total_comida + total_fijos + gasto_solo_refrescos) / num_totales
        
        # 2. El ALCOHOL (Copas, Cerveza y Vino) se divide SOLO entre los bebedores
        cuota_alcohol_exclusiva = gasto_alcohol_puro / num_bebedores
        
        
        import math
        cuota_sugerida_sin_alcohol = math.ceil(cuota_base_compartida)
        cuota_sugerida_normal = math.ceil(cuota_base_compartida + cuota_alcohol_exclusiva)

        # Mostrar las dos cajas para comparar
        c_sug1, c_sug2 = st.columns(2)
        c_sug1.info(f"**Cuota FIJADA (Lo que cobras):**\n- Con Alcohol: **{cuota_oficial_normal} €**\n- Sin Alcohol: **{cuota_oficial_sin_alcohol} €**\n- Por día: **{math.ceil(cuota_oficial_normal/3)} €**")
        c_sug2.warning(f"**Cuota SUGERIDA (Gasto real):**\n- Con Alcohol: **{cuota_sugerida_normal} €**\n- Sin Alcohol: **{cuota_sugerida_sin_alcohol} €**\n- Por día: **{math.ceil(cuota_sugerida_normal/3)} €**")
        
        if cuota_oficial_normal < cuota_sugerida_normal:
            st.error(f"⚠️ Ojo: La cuota que estás cobrando ({cuota_oficial_normal}€) no cubre el gasto total de ({cuota_sugerida_normal}€). Vais a acabar poniendo bote extra.")
        elif cuota_oficial_normal >= cuota_sugerida_normal:
            st.success("✅ La cuota cubre los gastos (incluyendo fianza y fijos). Todo en orden.")

        st.divider()

        # 4. BALANCE Y RECAUDACIÓN REAL
        st.markdown("### 🏦 Estado de la Caja")
        st.caption("Calculado sumando la cuota exacta de cada persona que tiene el check de 'Pagado'.")
        
        if "Pagado" in df_raw.columns:
            total_dias_evento = len(config.get("calendario", {}))
            precio_por_dia = math.ceil(cuota_oficial_normal / total_dias_evento) if total_dias_evento > 0 else 0
            
            total_recaudado = 0
            # Iteramos solo sobre los que han pagado
            for idx, row in df_raw[df_raw["Pagado"] == True].iterrows():
                try:
                    dias = int(row["Num_Dias"])
                except:
                    dias = 0
                    
                bebe = str(row["Bebida_Alcohol"]).upper() != "NADA"
                
                if dias >= total_dias_evento:
                    total_recaudado += cuota_oficial_normal if bebe else cuota_oficial_sin_alcohol
                else:
                    total_recaudado += dias * precio_por_dia
        else:
            total_recaudado = 0
            
        saldo_actual = total_recaudado - total_gastos
        
        col_rec, col_bal = st.columns(2)
        col_rec.metric("Dinero Real Recaudado", f"{total_recaudado:.2f} €")
        
        if saldo_actual >= 0:
            col_bal.metric("Fondo de maniobra (Sobrante)", f"+{saldo_actual:.2f} €", delta_color="normal")
        else:
            col_bal.metric("Falta por recaudar / Agujero", f"{saldo_actual:.2f} €", delta_color="inverse")
            
            
        # ----- PESTAÑA 5: SUBIR TICKETS -----
    with tab5:
        st.subheader("🧾 Subida de Facturas y Tickets")
        st.write("Sube aquí las fotos o PDFs de los tickets. El sistema calculará el gasto real automáticamente.")
        
        FACTURAS_DIR = "FACTURAS"
        REGISTRO_CSV = os.path.join(FACTURAS_DIR, "registro_gastos.csv")
        
        # Crear la carpeta automáticamente si no existe (vital para cuando levantes el Docker la primera vez)
        os.makedirs(FACTURAS_DIR, exist_ok=True)
        
        # Categorías de gasto predefinidas
        categorias_gastos = ["Carne", "Panadería", "Pescadería", "Supermercado General", "Bebida", "Hielo", "Furgón+Fianza", "Equipo", "Punto de Luz", "Chinos", "Otros"]

        with st.form("form_tickets", clear_on_submit=True):
            archivo = st.file_uploader("📂 Sube el ticket (Imagen o PDF)", type=["png", "jpg", "jpeg", "pdf"])
            categoria = st.selectbox("🏷️ Categoría del gasto", categorias_gastos)
            importe = st.number_input("💶 Importe exacto del ticket (€)", min_value=0.0, step=0.01, format="%.2f")
            
            enviado = st.form_submit_button("💾 Guardar Ticket", type="primary")
            
            # REEMPLAZAR POR ESTO:
            if enviado:
                if archivo is None:
                    st.error("❌ Tienes que subir un archivo.")
                elif importe <= 0:
                    st.error("❌ El importe debe ser mayor que 0.")
                else:
                    from src.data_manager import guardar_ticket, leer_tickets
                    
                    # Calculamos índice para el nombre del archivo
                    df_existentes = leer_tickets()
                    if not df_existentes.empty and "Categoria" in df_existentes.columns:
                        conteo = len(df_existentes[df_existentes["Categoria"] == categoria]) + 1
                    else:
                        conteo = 1
                    
                    ext = archivo.name.split(".")[-1]
                    cat_limpia = categoria.split(" ")[0].replace("/", "")
                    nombre_archivo = f"{cat_limpia}{conteo}_{importe}€.{ext}"
                    
                    # Guardamos en Google Sheets (persistente)
                    if guardar_ticket(nombre_archivo, categoria, importe):
                        st.success(f"✅ Ticket **{nombre_archivo}** guardado en Google Sheets.")
                    else:
                        st.error("❌ Error al guardar el ticket.")

    # ----- PESTAÑA 6: GASTOS REALES -----
    with tab6:
        st.subheader("📈 Control de Gastos Reales")

        from src.data_manager import leer_tickets
        df_gastos = leer_tickets()

        if df_gastos.empty:
            st.info("Aún no hay tickets registrados. Sube el primero en la pestaña anterior.")
        else:
            df_gastos["Importe (€)"] = pd.to_numeric(df_gastos["Importe (€)"], errors="coerce").fillna(0)
            gasto_total_real = df_gastos["Importe (€)"].sum()

            # Gasto estimado: lo recalculamos aquí de forma autónoma (igual que Tab 4)
            df_beb_tab6 = calcular_bebidas(df_raw, config)
            if not df_beb_tab6.empty:
                total_beb_tab6 = df_beb_tab6["Coste Total (€)"].sum()
            else:
                total_beb_tab6 = 0

            df_compra_tab6   = calcular_lista_compra(df_raw, config)
            resultado_tab6   = calcular_coste_comida(df_compra_tab6, df_raw, config)
            total_comida_tab6 = resultado_tab6["resumen"].get("TOTAL COMIDA (€)", 0)

            fijos_tab6 = config.get("gastos_fijos", {})
            total_fijos_tab6 = sum(fijos_tab6.values())

            gasto_estimado = total_beb_tab6 + total_comida_tab6 + total_fijos_tab6

            # --- Métricas principales ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Gasto Total ESTIMADO", f"{gasto_estimado:.2f} €")
            col2.metric("Gasto Total REAL", f"{gasto_total_real:.2f} €")

            desviacion = gasto_estimado - gasto_total_real
            if desviacion >= 0:
                col3.metric("Desviación (Sobrando)", f"+{desviacion:.2f} €", delta_color="normal")
            else:
                col3.metric("Desviación (Pasados de presupuesto)", f"{desviacion:.2f} €", delta_color="inverse")

            st.divider()

            col_izq, col_der = st.columns(2)

            with col_izq:
                st.markdown("#### 📊 Agrupado por Categoría")
                resumen_real = df_gastos.groupby("Categoria")["Importe (€)"].sum().reset_index()
                resumen_real = resumen_real.sort_values(by="Importe (€)", ascending=False)
                st.dataframe(
                    resumen_real.style.format({"Importe (€)": "{:.2f} €"}),
                    hide_index=True,
                    use_container_width=True
                )

            with col_der:
                st.markdown("#### 🧾 Historial de Tickets")
                st.dataframe(
                    df_gastos.style.format({"Importe (€)": "{:.2f} €"}),
                    hide_index=True,
                    use_container_width=True
                )