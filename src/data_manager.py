import pandas as pd
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

DATA_FILE = "datos_romeria.csv"  # Solo como fallback local, no se usa en producción


# ---------------------------------------------------------------
# CONEXIÓN
# ---------------------------------------------------------------
def get_google_sheet(nombre_pestana):
    print("[get_google_sheet] Iniciando conexión...")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    print("[get_google_sheet] Cargando credenciales...")
    credenciales = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=scopes
    )
    print("[get_google_sheet] Credenciales OK, autorizando cliente...")
    client = gspread.authorize(credenciales)
    print("[get_google_sheet] Cliente autorizado, abriendo sheet...")
    sheet = client.open("BD_Romeria").worksheet(nombre_pestana)
    print(f"[get_google_sheet] Sheet '{nombre_pestana}' abierto OK")
    return sheet

# ---------------------------------------------------------------
# FUNCIÓN INTERNA: Sube un DataFrame a una hoja limpiamente
# ---------------------------------------------------------------
def _subir_dataframe(sheet, df):
    df = df.copy()
    df = df.fillna("")
    df = df.astype(str)
    df = df.replace("nan", "").replace("True", "TRUE").replace("False", "FALSE")
    cabeceras = df.columns.tolist()
    filas = df.values.tolist()
    sheet.clear()
    sheet.update(range_name="A1", values=[cabeceras] + filas)


# ---------------------------------------------------------------
# LEER todos los asistentes
# ---------------------------------------------------------------
def leer_datos():
    try:
        sheet = get_google_sheet("Asistentes")
        datos = sheet.get_all_values()  # get_all_values en lugar de get_all_records
        
        if not datos or len(datos) < 2:
            # Sin datos o solo cabeceras, devolvemos DataFrame vacío
            return pd.DataFrame()
        
        cabeceras = datos[0]
        filas = datos[1:]
        df = pd.DataFrame(filas, columns=cabeceras)
        return df.fillna("")
        
    except Exception as e:
        if "200" in str(e):
            return pd.DataFrame()
        print(f"[leer_datos] Error: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------
# APLANAR el payload del formulario a fila plana
# ---------------------------------------------------------------
def aplanar_payload(payload):
    fila_plana = {
        "Nombre":          payload["Nombre"],
        "Correo":          payload["Correo"],
        "Dias_Asistencia": payload["Dias_Asistencia"],
        "Num_Dias":        payload["Num_Dias"],
        "Bebida_Alcohol":  payload["Bebida_Alcohol"],
        "Refresco_Alcohol":  payload["Refresco_Alcohol"],
        "Refresco_Comida1":  payload["Refresco_Comida1"],
        "Refresco_Comida2":  payload["Refresco_Comida2"],
        "Extra_Chupito":   payload["Chupito_Elegido"],
    }
    for extra, respuesta in payload["Extras"].items():
        fila_plana[f"Extra_{extra}"] = respuesta
    for dia, comidas_dia in payload["Comida"].items():
        for tipo_comida, opciones in comidas_dia.items():
            fila_plana[f"Comida_{dia}_{tipo_comida}"] = ", ".join(opciones)
    return fila_plana


# ---------------------------------------------------------------
# GUARDAR respuesta del formulario (anti-duplicados por correo)
# ---------------------------------------------------------------
def guardar_respuesta(payload):
    try:
        print("[guardar_respuesta] Iniciando...")
        fila = aplanar_payload(payload)
        print(f"[guardar_respuesta] Payload aplanado OK: {list(fila.keys())}")
        
        df_nuevo = pd.DataFrame([fila])
        print(f"[guardar_respuesta] DataFrame creado OK, shape: {df_nuevo.shape}")

        sheet = get_google_sheet("Asistentes")
        print("[guardar_respuesta] Conexión a Sheet OK")
        
        datos_actuales = sheet.get_all_values()
        print(f"[guardar_respuesta] Datos actuales leídos: {len(datos_actuales)} filas")

        if not datos_actuales or len(datos_actuales) < 2:
            df_final = df_nuevo
            print("[guardar_respuesta] Sheet vacío, creando desde cero")
        else:
            cabeceras = datos_actuales[0]
            filas = datos_actuales[1:]
            df_existente = pd.DataFrame(filas, columns=cabeceras)

            if "Correo" not in df_existente.columns:
                df_existente["Correo"] = ""

            correo_buscar = fila["Correo"]

            if correo_buscar in df_existente["Correo"].values:
                idx = df_existente[df_existente["Correo"] == correo_buscar].index[0]
                if "Pagado" in df_existente.columns:
                    df_nuevo.loc[0, "Pagado"] = df_existente.loc[idx, "Pagado"]
                df_existente.loc[idx] = df_nuevo.iloc[0]
                df_final = df_existente
                print(f"[guardar_respuesta] Correo existente, actualizando fila {idx}")
            else:
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
                print("[guardar_respuesta] Correo nuevo, añadiendo fila")

        print(f"[guardar_respuesta] df_final shape: {df_final.shape}")
        print("[guardar_respuesta] Llamando a _subir_dataframe...")
        _subir_dataframe(sheet, df_final)
        print("[guardar_respuesta] _subir_dataframe completado OK")
        return True

    except Exception as e:
        if "200" in str(e):
            print("[guardar_respuesta] Response 200 capturado como excepción, pero es OK")
            return True
        print(f"[guardar_respuesta] Error REAL: {e}")
        import traceback
        traceback.print_exc()
        return False


# ---------------------------------------------------------------
# GUARDAR estado de pagos (cuando el admin hace check en Pestaña 1)
# ---------------------------------------------------------------
def guardar_estado_pagos(df_actualizado):
    try:
        sheet = get_google_sheet("Asistentes")
        _subir_dataframe(sheet, df_actualizado)
        return True
    except Exception as e:
        if "200" in str(e):
            return True
        print(f"[guardar_estado_pagos] Error: {e}")
        return False


# ---------------------------------------------------------------
# GUARDAR ticket en la pestaña Facturas
# ---------------------------------------------------------------
def guardar_ticket(nombre_archivo, categoria, importe):
    try:
        sheet = get_google_sheet("Facturas")
        datos_actuales = sheet.get_all_records()

        nuevo = pd.DataFrame([{
            "Archivo":     nombre_archivo,
            "Categoria":   categoria,
            "Importe (€)": float(importe)
        }])

        if not datos_actuales:
            df_final = nuevo
        else:
            df_final = pd.concat([pd.DataFrame(datos_actuales), nuevo], ignore_index=True)

        _subir_dataframe(sheet, df_final)
        return True

    except Exception as e:
        if "200" in str(e):
            return True
        print(f"[guardar_ticket] Error: {e}")
        return False


# ---------------------------------------------------------------
# LEER tickets de la pestaña Facturas
# ---------------------------------------------------------------
def leer_tickets():
    try:
        sheet = get_google_sheet("Facturas")
        datos = sheet.get_all_records()
        if not datos:
            return pd.DataFrame()
        df = pd.DataFrame(datos)
        df["Importe (€)"] = pd.to_numeric(df["Importe (€)"], errors="coerce").fillna(0)
        return df
    except Exception as e:
        print(f"[leer_tickets] Error: {e}")
        return pd.DataFrame()