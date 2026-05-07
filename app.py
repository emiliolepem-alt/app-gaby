import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import pandas as pd
import json

# Configuración de alcance para acceso a APIs de Google
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

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
with col2:
    st.title("🤕")
with col3:
    ruta_imagen = os.path.join(os.path.dirname(__file__), "gatito.png")
    if os.path.exists(ruta_imagen):
        st.image(ruta_imagen, width=50)

# División de la interfaz en pestañas operativas
tab_registro, tab_graficos = st.tabs(["Añadir Registro", "Dashboard de Análisis"])

with tab_registro:
    with st.form("formulario_gaby", clear_on_submit=True):
        fecha = st.date_input("Fecha", datetime.now())
        tipo_dolor = st.selectbox("Tipo de Dolor", ["Mandibula", "Estomacal", "Cabeza", "Otro"])
        escala = st.slider("Escala de intensidad", 1, 10, 5)
        comentario = st.text_area("Comentario / Notas")
        sospecha = st.text_input("Sospecha (¿Qué lo gatilló?)")
        ubicacion = st.text_input("Ubicación específica")
        medicamento = st.text_input("Medicamento tomado")

        enviado = st.form_submit_button("Guardar en mi Bitácora")

        if enviado:
            try:
                hoja = conectar_sheets()
                datos = [
                    fecha.strftime("%d/%m/%Y"), 
                    tipo_dolor, 
                    escala, 
                    comentario, 
                    sospecha, 
                    ubicacion, 
                    medicamento
                ]
                hoja.append_row(datos)
                st.success("Registro ingresado a la base de datos.")
            except Exception as e:
                st.error(f"Fallo de escritura en base de datos: {e}")

with tab_graficos:
    st.header("Análisis de Datos")
    
    # Renderizado condicional de gráficos tras la solicitud del usuario
    if st.button("Cargar datos actualizados"):
        try:
            hoja = conectar_sheets()
            registros = hoja.get_all_records()
            
            if registros:
                df = pd.DataFrame(registros)
                cols_esperadas = ['Fecha', 'Tipo de Dolor', 'Escala', 'Sospecha', 'Ubicación', 'Medicamento']
                
                # Verificación de esquema de datos
                if all(col in df.columns for col in cols_esperadas):
                    # Formateo de fechas para asegurar un orden cronológico correcto
                    df['Fecha'] = pd.to_datetime(df['Fecha'], format="%d/%m/%Y", errors='coerce')
                    df = df.dropna(subset=['Fecha']).sort_values('Fecha')
                    
                    # Implementación de filtro global por categoría
                    opciones_filtro = ["General"] + list(df["Tipo de Dolor"].unique())
                    filtro_seleccionado = st.selectbox("Filtrar por Tipo de Dolor:", opciones_filtro)
                    
                    if filtro_seleccionado != "General":
                        df_filtrado = df[df["Tipo de Dolor"] == filtro_seleccionado]
                    else:
                        df_filtrado = df
                    
                    # Renderizado de KPIs métricos
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Registros Totales", len(df_filtrado))
                    col2.metric("Intensidad Promedio", round(df_filtrado["Escala"].mean(), 1))
                    
                    # Cálculo de la moda para determinar el medicamento de mayor uso
                    moda_meds = df_filtrado[df_filtrado["Medicamento"].str.strip() != '']["Medicamento"].mode()
                    medicamento_frecuente = moda_meds[0] if not moda_meds.empty else "N/A"
                    col3.metric("Medicamento más usado", medicamento_frecuente)
                    
                    st.divider()
                    
                    # Renderizado de gráficos distribuidos en columnas
                    col_g1, col_g2 = st.columns(2)
                    
                    with col_g1:
                        st.subheader("Frecuencia de Sospechas")
                        df_sospechas = df_filtrado[df_filtrado['Sospecha'].str.strip() != '']
                        if not df_sospechas.empty:
                            st.bar_chart(df_sospechas['Sospecha'].value_counts())
                            
                        st.subheader("Ubicaciones")
                        df_ubicacion = df_filtrado[df_filtrado['Ubicación'].str.strip() != '']
                        if not df_ubicacion.empty:
                            st.bar_chart(df_ubicacion['Ubicación'].value_counts())

                    with col_g2:
                        st.subheader("Ranking de Medicamentos")
                        df_meds = df_filtrado[df_filtrado['Medicamento'].str.strip() != '']
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