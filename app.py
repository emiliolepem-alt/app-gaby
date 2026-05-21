import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import pandas as pd
import json
import time

# Configuración de alcance para acceso a APIs de Google
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def conectar_sheets():
    """
    Gestiona la conexión a Google Sheets.
    En la nube lee los secretos de Streamlit; en local lee el archivo físico.
    """
    if "GCP_CREDENTIALS" in st.secrets:
        # Modo Producción (Nube)
        creds_dict = json.loads(st.secrets["GCP_CREDENTIALS"])
        credenciales = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # Modo Desarrollo (Local)
        ruta_credenciales = os.path.join(os.path.dirname(__file__), "credenciales.json")
        credenciales = Credentials.from_service_account_file(ruta_credenciales, scopes=SCOPES)
        
    cliente = gspread.authorize(credenciales)
    return cliente.open("Registros_Salud").sheet1

# Configuración principal de la aplicación web
st.set_page_config(page_title="Salud Gaby", page_icon="🐱", layout="wide")

col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    st.title("Registro de dolor Gaby ahumada")

# División de la interfaz en pestañas operativas
tab_registro, tab_graficos, tab_gestionar = st.tabs(["Añadir Registro", "Dashboard de Análisis", "Gestionar Registros"])

@st.cache_data(show_spinner=False)
def obtener_registros():
    """Obtiene y cachea los registros para listas dinámicas y gráficos."""
    hoja = conectar_sheets()
    return hoja.get_all_records()

try:
    registros_actuales = obtener_registros()
    df_historico = pd.DataFrame(registros_actuales) if registros_actuales else pd.DataFrame()
except Exception:
    df_historico = pd.DataFrame()

def obtener_unicos(columna, default_list):
    """Extrae valores únicos de la base de datos para autocompletar listas en el futuro."""
    if not df_historico.empty and columna in df_historico.columns:
        unicos = df_historico[columna].dropna().astype(str).str.strip().unique()
        for u in unicos:
            if u and u.lower() != 'nan' and u not in default_list and u.lower() != 'otro':
                default_list.append(u)
    return default_list

# Listas actualizables con el historial guardado
tipos_dolor_opciones = obtener_unicos("Tipo de Dolor", ["Mandibula", "Estomacal", "Cabeza"])
sospechas_opciones = obtener_unicos("Sospecha", ["Deshidratación", "Luz", "Estrés", "Comida", "Falta de comida", "Lavado de pelo"])
medicamento_opciones = obtener_unicos("Medicamento", ["Ninguno", "Aspirina"])

with tab_registro:
    # Creamos una variable de estado para reiniciar los campos
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0
        
    fk = st.session_state.form_key

    fecha = st.date_input("Fecha", datetime.now(), key=f"fecha_{fk}")
    
    tipo_dolor = st.selectbox("Tipo de Dolor", tipos_dolor_opciones + ["Otro"], key=f"tipo_{fk}")
    if tipo_dolor == "Otro":
        tipo_dolor_final = st.text_input("Especificar Tipo de Dolor", key=f"tipo_otro_{fk}")
    else:
        tipo_dolor_final = tipo_dolor
        
    # Dependencia dinámica para la ubicación
    if tipo_dolor_final in ["Cabeza", "Estomacal", "Mandibula"]:
        if tipo_dolor_final == "Cabeza":
            ubicacion_ops = ["Lado izquierdo", "Lado derecho", "General"]
        elif tipo_dolor_final == "Estomacal":
            ubicacion_ops = ["Hinchazón", "Indigestión"]
        elif tipo_dolor_final == "Mandibula":
            ubicacion_ops = ["Localizado", "Cara general"]
            
        ubicacion = st.selectbox("Ubicación específica", ubicacion_ops + ["Otro"], key=f"ubi_{fk}")
        if ubicacion == "Otro":
            ubicacion_final = st.text_input("Especificar Ubicación", key=f"ubi_otro_{fk}")
        else:
            ubicacion_final = ubicacion
    else:
        ubicacion_final = st.text_input("Ubicación específica", key=f"ubi_libre_{fk}")
        
    escala = st.slider("Escala de intensidad", 1, 10, 5, key=f"escala_{fk}")
    comentario = st.text_area("Comentario / Notas", key=f"coment_{fk}")
    
    sospecha = st.selectbox("Sospecha (¿Qué lo gatilló?)", sospechas_opciones + ["Otro"], key=f"sosp_{fk}")
    if sospecha == "Otro":
        sospecha_final = st.text_input("Especificar Sospecha", key=f"sosp_otro_{fk}")
    else:
        sospecha_final = sospecha
        
    medicamento = st.selectbox("Medicamento tomado", medicamento_opciones + ["Otro"], key=f"med_{fk}")
    if medicamento == "Otro":
        medicamento_final = st.text_input("Especificar Medicamento", key=f"med_otro_{fk}")
    else:
        medicamento_final = medicamento

    if st.button("Guardar en mi Bitácora"):
        try:
            hoja = conectar_sheets()
            datos = [
                fecha.strftime("%d/%m/%Y"), 
                tipo_dolor_final, 
                escala, 
                comentario, 
                sospecha_final, 
                ubicacion_final, 
                medicamento_final
            ]
            hoja.append_row(datos)
            st.success("Registro ingresado a la base de datos.")
            obtener_registros.clear() # Limpia la caché para actualizar los gráficos y listas futuras
            # Al sumar 1 y reiniciar, vacía todos los campos automáticamente
            st.session_state.form_key += 1
            time.sleep(1.5) # Pausa para que alcances a leer el mensaje de éxito
            st.rerun()
        except Exception as e:
            st.error(f"Fallo de escritura en base de datos: {e}")

with tab_graficos:
    st.header("Análisis de Datos")
    
    if st.button("Actualizar y Cargar Datos"):
        obtener_registros.clear()
        
    try:
        registros = obtener_registros()
        
        if registros:
            df = pd.DataFrame(registros)
            cols_esperadas = ['Fecha', 'Tipo de Dolor', 'Escala', 'Sospecha', 'Ubicación', 'Medicamento']
            
            if all(col in df.columns for col in cols_esperadas):
                df['Fecha'] = pd.to_datetime(df['Fecha'], format="%d/%m/%Y", errors='coerce')
                df = df.dropna(subset=['Fecha']).sort_values('Fecha')
                
                # Transformar datos para evitar que los gráficos fallen por tipos incorrectos (ej. si hay texto en Escala o int en Sospecha)
                df['Escala'] = pd.to_numeric(df['Escala'], errors='coerce').fillna(5)
                for col in ['Tipo de Dolor', 'Sospecha', 'Ubicación', 'Medicamento']:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.strip()
                
                opciones_filtro = ["General"] + list(df[df["Tipo de Dolor"] != ""]["Tipo de Dolor"].unique())
                filtro_seleccionado = st.selectbox("Filtrar por Tipo de Dolor:", opciones_filtro)
                
                if filtro_seleccionado != "General":
                    df_filtrado = df[df["Tipo de Dolor"] == filtro_seleccionado]
                else:
                    df_filtrado = df
                
                if df_filtrado.empty:
                    st.info("No hay datos que coincidan con este filtro.")
                else:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Registros Totales", len(df_filtrado))
                    col2.metric("Intensidad Promedio", round(df_filtrado["Escala"].mean(), 1))
                    
                    moda_meds = df_filtrado[df_filtrado["Medicamento"] != '']["Medicamento"].mode()
                    medicamento_frecuente = moda_meds[0] if not moda_meds.empty else "N/A"
                    col3.metric("Medicamento más usado", medicamento_frecuente)
                    
                    st.divider()
                    
                    col_g1, col_g2 = st.columns(2)
                    
                    with col_g1:
                        st.subheader("Frecuencia de Sospechas")
                        df_sospechas = df_filtrado[df_filtrado['Sospecha'] != '']
                        if not df_sospechas.empty:
                            st.bar_chart(df_sospechas['Sospecha'].value_counts())
                            
                        st.subheader("Ubicaciones")
                        df_ubicacion = df_filtrado[df_filtrado['Ubicación'] != '']
                        if not df_ubicacion.empty:
                            st.bar_chart(df_ubicacion['Ubicación'].value_counts())

                    with col_g2:
                        st.subheader("Ranking de Medicamentos")
                        df_meds = df_filtrado[df_filtrado['Medicamento'] != '']
                        if not df_meds.empty:
                            st.bar_chart(df_meds['Medicamento'].value_counts())
                            
                        st.subheader("Distribución de Escala (1-10)")
                        st.bar_chart(df_filtrado['Escala'].value_counts())
                        
                    st.subheader("Evolución de Intensidad en el Tiempo")
                    df_tiempo = df_filtrado.set_index('Fecha')
                    st.line_chart(df_tiempo['Escala'])
                    
            else:
                st.warning("Estructura de columnas inválida respecto a la configuración esperada.")
        else:
            st.info("No existen registros en la hoja de cálculo.")
    except Exception as e:
        st.error(f"Fallo de lectura en base de datos: {e}")

with tab_gestionar:
    st.header("Eliminar un Registro")
    try:
        registros_gestion = obtener_registros()
        if registros_gestion:
            df_gestion = pd.DataFrame(registros_gestion)
            
            opciones_borrado = []
            for idx, row in df_gestion.iterrows():
                # La fila 1 en Sheets son los encabezados, por lo que los datos empiezan en la fila 2
                fila_sheet = idx + 2
                fecha_reg = row.get('Fecha', 'Sin fecha')
                tipo_reg = row.get('Tipo de Dolor', 'Desconocido')
                escala_reg = row.get('Escala', '-')
                texto_opcion = f"Fila {fila_sheet}: {fecha_reg} | {tipo_reg} | Intensidad: {escala_reg}"
                opciones_borrado.append((fila_sheet, texto_opcion))
            
            mapa_opciones = {texto: fila for fila, texto in opciones_borrado}
            seleccion = st.selectbox("Selecciona el registro que deseas eliminar:", list(mapa_opciones.keys()))
            
            if st.button("Eliminar Registro Seleccionado"):
                fila_a_borrar = mapa_opciones[seleccion]
                hoja = conectar_sheets()
                hoja.delete_rows(fila_a_borrar)
                obtener_registros.clear() # Limpia caché para reflejar el borrado
                st.success(f"Registro eliminado correctamente. La tabla se ha actualizado.")
                st.rerun() # Recarga la app para que desaparezca de la lista
        else:
            st.info("No hay registros disponibles para eliminar.")
    except Exception as e:
        st.error(f"Error al cargar o eliminar el registro: {e}")