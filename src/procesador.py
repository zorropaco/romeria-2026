import pandas as pd
import math

def calcular_lista_compra(df_raw, config):
    multiplicadores = config["menu_comida"]
    comidas_posibles = list(multiplicadores.keys())
    
    # NUEVA LÓGICA: Preguntamos al config qué eventos son a la carta
    eventos_eleccion = []
    for dia, comidas in config["calendario"].items():
        for tipo_comida, tipo_menu in comidas.items():
            if tipo_menu == "eleccion":
                eventos_eleccion.append(f"{dia}_{tipo_comida}")
                
    # Creamos la lista de columnas exactas que debemos leer del CSV
    columnas_comida = [f"Comida_{evento}" for evento in eventos_eleccion]
    
    inventario = {}
    for comida in comidas_posibles:
        inventario[comida] = {evento: 0.0 for evento in eventos_eleccion}
        inventario[comida]["Total"] = 0.0
        
    for index, fila in df_raw.iterrows():
        for col in columnas_comida:
            # Si la columna no existe en el CSV antiguo, la ignoramos
            if col not in df_raw.columns:
                continue
                
            evento = col.replace("Comida_", "")
            celda = str(fila[col])
            
            if celda and celda != "nan" and celda != "No asiste" and celda != "Menú Fijo":
                opciones_elegidas = [item.strip() for item in celda.split(",")]
                cantidad_opciones = len(opciones_elegidas)
                
                for opcion in opciones_elegidas:
                    if opcion in multiplicadores:
                        indice_multiplicador = 0 if cantidad_opciones == 1 else 1
                        cantidad_a_sumar = multiplicadores[opcion][indice_multiplicador]
                        
                        inventario[opcion][evento] += cantidad_a_sumar
                        inventario[opcion]["Total"] += cantidad_a_sumar
                        
    df_resultado = pd.DataFrame.from_dict(inventario, orient="index")
    df_resultado = df_resultado[df_resultado["Total"] > 0]
    
    return df_resultado

def contar_menus_fijos(df_raw, config):
    
    conteo = {}
    
    # Leemos el config para saber qué eventos son fijos
    for dia, comidas in config["calendario"].items():
        for tipo_comida, tipo_menu in comidas.items():
            if tipo_menu == "fijo":
                col_name = f"Comida_{dia}_{tipo_comida}"
                if col_name in df_raw.columns:
                    # Contamos los que dijeron Menú Fijo
                    total_fijos = (df_raw[col_name] == "Menú Fijo").sum()
                    evento_bonito = f"{dia} ({tipo_comida})"
                    conteo[evento_bonito] = total_fijos
                    
    df_fijos = pd.DataFrame(list(conteo.items()), columns=["Evento", "Comensales Confirmados"])
    return df_fijos[df_fijos["Comensales Confirmados"] > 0]

def calcular_bebidas(df_raw, config):
    """
    Calcula la lista de la compra de bebidas aplicando todas las reglas de la Romería.
    """
    ratios = config["ratios_bebida"]
    lista_compra_bebidas = {}
    
    # Aseguramos que las columnas de números sean numéricas (por si vienen como texto)
    df_raw = df_raw.copy()
    df_raw["Num_Dias"] = pd.to_numeric(df_raw["Num_Dias"], errors="coerce").fillna(0)
    
    total_dias_evento = len(config["calendario"].keys()) # Ej: 3 días (Viernes, Sábado, Domingo)

    # ---------------------------------------------------------
    # 1. ALCOHOL PRINCIPAL (x1.25 por persona que lo beba)
    # ---------------------------------------------------------
    df_bebedores = df_raw[df_raw["Bebida_Alcohol"] != "NADA"]
    conteo_alcohol = df_bebedores["Bebida_Alcohol"].value_counts()
    
    for bebida, cantidad_personas in conteo_alcohol.items():
        botellas = cantidad_personas * ratios["alcohol_por_persona"]
        lista_compra_bebidas[bebida] = botellas

    # ---------------------------------------------------------
    # 2. REBUJITO, MANZANILLA Y EL EXTRA DE DYC
    # ---------------------------------------------------------
    if "Extra_Rebujito" in df_raw.columns:
        # Contamos cuántos días "de fiesta real" hay (Días totales - 1)
        dias_rebujito = max(1, total_dias_evento - 1) 
        cubos_totales = dias_rebujito * ratios["cubos_rebujito_diarios"]
        botellas_manzanilla = cubos_totales * ratios["botellas_manzanilla_por_cubo"]
        
        lista_compra_bebidas["MANZANILLA"] = botellas_manzanilla
        
        # Al DYC hay que sumarle (botellas_manzanilla * 0.25)
        extra_dyc = botellas_manzanilla * ratios["dyc_extra_por_manzanilla"]
        if "DYC 8" in lista_compra_bebidas:
            lista_compra_bebidas["DYC 8"] += extra_dyc
        else:
            lista_compra_bebidas["DYC 8"] = extra_dyc

    # ---------------------------------------------------------
    # 3. CERVEZA (Cajas de 24)
    # Fórmula: (7 cervezas * num_dias_de_la_persona) / 24
    # ---------------------------------------------------------
    if "Extra_Cerveza" in df_raw.columns:
        df_cerveceros = df_raw[df_raw["Extra_Cerveza"] == "SÍ"]
        # Sumamos los días totales que van a estar todos los cerveceros
        dias_totales_cerveceros = df_cerveceros["Num_Dias"].sum()
        total_latas = dias_totales_cerveceros * ratios["cerveza_diaria"]
        pack_cerveza = ratios["pack_cerveza"]
        cajas_cerveza = total_latas / pack_cerveza
        lista_compra_bebidas["CAJAS CERVEZA (24 uds)"] = cajas_cerveza

    # ---------------------------------------------------------
    # 4. TINTO / CALIMOCHO (x1.25 por persona)
    # ---------------------------------------------------------
    if "Extra_Tinto/Calimocho" in df_raw.columns:
        personas_tinto = (df_raw["Extra_Tinto/Calimocho"] == "SÍ").sum()
        botellas_tinto = personas_tinto * ratios["tinto_por_persona"]
        if botellas_tinto > 0:
            lista_compra_bebidas["TINTO"] = botellas_tinto

    # ---------------------------------------------------------
    # 5. MARTINI BLANCO (x0.25 por persona, independiente de días)
    # ---------------------------------------------------------
    if "Extra_Martini Blanco" in df_raw.columns:
        personas_martini = (df_raw["Extra_Martini Blanco"] == "SÍ").sum()
        botellas_martini = personas_martini * ratios["martini_por_persona"]
        if botellas_martini > 0:
            lista_compra_bebidas["MARTINI BLANCO"] = botellas_martini

    # ---------------------------------------------------------
    # 6. REFRESCOS (x1.75 por cada día por persona)
    # ---------------------------------------------------------
    refrescos_pedidos = {}
    columnas_refrescos = ["Refresco_Alcohol", "Refresco_Comida1", "Refresco_Comida2"]
    
    for index, fila in df_raw.iterrows():
        dias_persona = fila["Num_Dias"]
        # Multiplicador para esta persona concreta
        factor_refresco = dias_persona * ratios["refresco_por_dia"]
        
        for col in columnas_refrescos:
            if col in df_raw.columns:
                refresco = str(fila[col])
                if refresco and refresco != "nan" and refresco != "NADA":
                    if refresco in refrescos_pedidos:
                        refrescos_pedidos[refresco] += factor_refresco
                    else:
                        refrescos_pedidos[refresco] = factor_refresco
                        
    # Añadimos los refrescos a la lista final
    for ref, cantidad in refrescos_pedidos.items():
        lista_compra_bebidas[ref] = cantidad

    # ---------------------------------------------------------
    # 7. CHUPITOS (Votación)
    # ---------------------------------------------------------
    if "Extra_Chupito" in df_raw.columns:
        df_chupitos = df_raw[df_raw["Extra_Chupito"] != "NO"]
        if not df_chupitos.empty:
            # Encontramos el chupito más repetido (la moda)
            modas = df_chupitos["Extra_Chupito"].mode()
            if not modas.empty:
                chupito_ganador = modas[0]
                votos = (df_chupitos["Extra_Chupito"] == chupito_ganador).sum()
            
                # Calculamos y lo añadimos a la lista de la compra SOLO si hubo un ganador válido
                botellas_chupito = len(df_chupitos) * 0.25
                lista_compra_bebidas[f"CHUPITO GANADOR: {chupito_ganador} ({votos} votos)"] = botellas_chupito


    # ---------------------------------------------------------
    # FORMATEAR EL DATAFRAME FINAL Y AÑADIR PRECIOS
    # ---------------------------------------------------------
    df_resultado = pd.DataFrame(list(lista_compra_bebidas.items()), columns=["Bebida", "Cantidad a Comprar"])
    # Redondeamos al alza para saber las botellas reales que compramos
    df_resultado["Comprar (Botellas/Cajas)"] = round(df_resultado["Cantidad a Comprar"])
    
    # Añadimos la columna de PRECIOS
    precios = config.get("precios_bebida", {})
    
    def obtener_precio(nombre_bebida):
        # Si es un chupito, extraemos el nombre real (ej: de "CHUPITO GANADOR: JAGGER..." sacamos "JAGGER")
        if "CHUPITO GANADOR" in nombre_bebida:
            for opcion in config["menu_bebida"]["chupitos_opciones"]:
                if opcion in nombre_bebida:
                    return precios.get(opcion, 0.0)
        # Si es una bebida normal, la buscamos directamente
        return precios.get(nombre_bebida, 0.0)
        
    # Calculamos el precio unitario y el coste total
    df_resultado["Precio Unidad (€)"] = df_resultado["Bebida"].apply(obtener_precio)
    df_resultado["Coste Total (€)"] = df_resultado["Comprar (Botellas/Cajas)"] * df_resultado["Precio Unidad (€)"]
    
    # Categorizamos las bebidas para las métricas (Alcohol, Refresco, Cerveza, Vino)
    def categorizar(bebida):
        if "CERVEZA" in bebida: return "CERVEZA"
        elif bebida in ["TINTO", "MANZANILLA"]: return "VINO/MANZANILLA"
        elif bebida in config["menu_bebida"]["refrescos"]: return "REFRESCO"
        else: return "ALCOHOL"
        
    df_resultado["Categoría"] = df_resultado["Bebida"].apply(categorizar)
    
    # Ordenamos
    df_resultado = df_resultado.sort_values(by=["Categoría", "Bebida"]).reset_index(drop=True)
    
    return df_resultado

def calcular_coste_comida(df_compra_carnes: pd.DataFrame, df_raw: pd.DataFrame, config: dict) -> dict:
    precios = config.get("precios_comida", {})
    ratios_paella = config.get("ratios_paella", {})

    def redondear_medio_kilo_superior(kg: float) -> float:
        return math.ceil(kg * 2) / 2

    filas_plancha = []

    # Aquí los nombres de comida vienen en el índice de df_compra_carnes
    for plato, row in df_compra_carnes.iterrows():
        viernes_mediodia = row.get("Viernes_Mediodía", 0)
        viernes_cena = row.get("Viernes_Cena", 0)
        sabado_cena = row.get("Sábado_Cena", 0)
        total_calculado = row.get("Total", 0)

        unidad = "Unidades"
        a_comprar = total_calculado

        if plato == "Pinchos de pollo":
            unidad = "Tarrinas 0.5 kg"
            a_comprar = round(total_calculado)
        elif plato == "Solomillos":
            unidad = "Unidades"
            a_comprar = math.ceil(total_calculado / 2)
        else:
            unidad = "Unidades"
            a_comprar = math.ceil(total_calculado)

        precio_unit = precios.get(plato, 0.0)
        coste_total = a_comprar * precio_unit

        filas_plancha.append({
            "Comida": plato,
            "Viernes_Mediodía": viernes_mediodia,
            "Viernes_Cena": viernes_cena,
            "Sábado_Cena": sabado_cena,
            "Total calculado": total_calculado,
            "A comprar": a_comprar,
            "Unidad": unidad,
            "Precio unitario (€)": precio_unit,
            "Coste total (€)": coste_total
        })

    cols_eventos = [
    f"{dia}_{tipo}"
    for dia, comidas in config["calendario"].items()
    for tipo, menu in comidas.items()
    if menu == "eleccion"
    ]
    columnas_plancha = ["Comida"] + cols_eventos + [
    "Total calculado", "A comprar", "Unidad",
    "Precio unitario (€)", "Coste total (€)"
    ]
    df_plancha = pd.DataFrame(filas_plancha) if filas_plancha else pd.DataFrame(columns=columnas_plancha)

    # --- Paella ---
    num_comensales = len(df_raw) if df_raw is not None else 0

    kg_por_persona_pollo = ratios_paella.get("kg_por_persona_pollo", 1.5 / 28)
    kg_por_persona_magro = ratios_paella.get("kg_por_persona_magro", 1.5 / 28)

    kg_pollo_exacto = num_comensales * kg_por_persona_pollo
    kg_magro_exacto = num_comensales * kg_por_persona_magro

    kg_pollo_comprar = redondear_medio_kilo_superior(kg_pollo_exacto)
    kg_magro_comprar = redondear_medio_kilo_superior(kg_magro_exacto)

    # Soporta tanto nombres de tu Excel nuevo como los genéricos (fallback)
    precio_pollo = precios.get("Pollo troceado paella", precios.get("Pollo paella (kg)", 0.0))
    precio_magro = precios.get("Magro troceado paella", precios.get("Magro paella (kg)", 0.0))

    df_paella = pd.DataFrame([
        {
            "Ingrediente": "Pollo troceado paella",
            "Comensales": num_comensales,
            "Kg exactos": kg_pollo_exacto,
            "Kg a comprar": kg_pollo_comprar,
            "Precio €/kg": precio_pollo,
            "Coste total (€)": kg_pollo_comprar * precio_pollo
        },
        {
            "Ingrediente": "Magro troceado paella",
            "Comensales": num_comensales,
            "Kg exactos": kg_magro_exacto,
            "Kg a comprar": kg_magro_comprar,
            "Precio €/kg": precio_magro,
            "Coste total (€)": kg_magro_comprar * precio_magro
        }
    ])

    # ------------------
    # PANADERÍA
    # ------------------
    dias_romeria = len(config.get("calendario", {})) if "calendario" in config else 3
    
    # DIAS * GENTE / BARRA (a 2.5 pers/barra)
    barras_pan_exacto = (dias_romeria * num_comensales) / 2.5
    barras_pan = math.ceil(barras_pan_exacto) 
    
    bandejas_dulces = round(num_comensales / 2)
    
    medio_pan_exacto = num_comensales / 3
    medio_pan = math.ceil(medio_pan_exacto)

    df_panaderia = pd.DataFrame([
        {"Producto": "Barras de pan", "Unidades": barras_pan, "Precio unit. (€)": precios.get("Barras de pan", 0), "Coste total (€)": barras_pan * precios.get("Barras de pan", 0)},
        {"Producto": "Bandeja dulces pequeña", "Unidades": bandejas_dulces, "Precio unit. (€)": precios.get("Bandeja dulces pequeña", 0), "Coste total (€)": bandejas_dulces * precios.get("Bandeja dulces pequeña", 0)},
        {"Producto": "Medio pan", "Unidades": medio_pan, "Precio unit. (€)": precios.get("Medio pan", 0), "Coste total (€)": medio_pan * precios.get("Medio pan", 0)},
    ])

    # ------------------
    # PESCADO / MARISCO
    # ------------------
    ratios_pescado = config.get("ratios_pescado", {})
    
    kg_gambas = redondear_medio_kilo_superior(num_comensales * ratios_pescado.get("kg_por_persona_gambas", 0))
    kg_gambones = redondear_medio_kilo_superior(num_comensales * ratios_pescado.get("ud_por_persona_gambones", 0))
    kg_langostinos = redondear_medio_kilo_superior(num_comensales * ratios_pescado.get("kg_por_persona_langostinos", 0))
    kg_menestra_marisco = redondear_medio_kilo_superior(num_comensales * ratios_pescado.get("kg_por_persona_menestra_marisco", 0))
    

    df_pescado = pd.DataFrame([
        {
            "Producto": "Gambas",
            "Kg a comprar": kg_gambas,
            "Precio €/kg": precios.get("Gambas (kg)", 0),
            "Coste total (€)": kg_gambas * precios.get("Gambas (kg)", 0)
        },
        {
            "Producto": "Gambones",
            "Kg a comprar": kg_gambones,
            "Precio €/kg": precios.get("Gambones (€/ud)", 0),
            "Coste total (€)": kg_gambones * precios.get("Gambones (€/ud)", 0)
        },
        {
            "Producto": "Langostinos",
            "Kg a comprar": kg_langostinos,
            "Precio €/kg": precios.get("Langostinos (kg)", 0),
            "Coste total (€)": kg_langostinos * precios.get("Langostinos (kg)", 0)
        },
        {
            "Producto": "Menestra de Marisco",
            "Kg a comprar": kg_menestra_marisco,
            "Precio €/kg": precios.get("Menestra marisco (kg)", 0),
            "Coste total (€)": kg_menestra_marisco * precios.get("Menestra marisco (kg)", 0)
        },
    ])

    # ------------------
    # NUEVO RESUMEN
    # ------------------
    coste_plancha = df_plancha["Coste total (€)"].sum()
    coste_paella = df_paella["Coste total (€)"].sum()
    coste_panaderia = df_panaderia["Coste total (€)"].sum()
    coste_pescado = df_pescado["Coste total (€)"].sum()

    resumen = {
        "Carne Plancha (€)": coste_plancha,
        "Carne Paella (€)": coste_paella,
        "Panadería (€)": coste_panaderia,
        "Pescado/Marisco (€)": coste_pescado,
        "TOTAL COMIDA (€)": coste_plancha + coste_paella + coste_panaderia + coste_pescado
    }

    return {
        "df_plancha": df_plancha,
        "df_paella": df_paella,
        "df_panaderia": df_panaderia,
        "df_pescado": df_pescado,
        "resumen": resumen
        
    }     