import streamlit as st
import pandas as pd
import unicodedata
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="🧹 Limpieza y Agrupación de Facturas", layout="wide")
st.title("🧹 Limpieza y Agrupación de Facturas")

correcciones_manual = {
    'Ã±': 'ñ', 'Ã‘': 'Ñ', 'Ã¡': 'á', 'ÃÁ': 'Á', 'Ã©': 'é', 'Ã‰': 'É',
    'Ã­': 'í', 'ÃÍ': 'Í', 'Ã³': 'ó', 'Ã“': 'Ó', 'Ãº': 'ú', 'Ãš': 'Ú',
    'Ã¼': 'ü', 'Ãœ': 'Ü', 'Ã ': 'à', 'Ã¨': 'è', 'Ã': 'Ñ', 'Ã3': 'ó',
    'Ão': 'u', 'Â¿': '¿', 'Â¡': '¡', 'Â´': '´', 'â€“': '-', 'Ã': 'Í',
    'â€œ': '"', 'â€': '"', 'â€˜': "'", 'â€™': "'", 'â€¦': '...'
}

def limpiar_texto(texto):
    if isinstance(texto, str):
        try:
            texto = texto.encode('latin1').decode('utf-8')
        except:
            try:
                texto = texto.encode('utf-8').decode('latin1')
            except:
                pass
        texto = unicodedata.normalize('NFKC', texto)
        for erroneo, correcto in correcciones_manual.items():
            texto = texto.replace(erroneo, correcto)
        texto = texto.replace('\xa0', ' ')
        texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def limpiar_dataframe(df):
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(limpiar_texto)
    return df

def aplicar_filtros(df):
    st.subheader("🎯 Filtros opcionales")
    columnas_filtro = st.multiselect("Selecciona columnas para filtrar:", df.columns.tolist())
    for col in columnas_filtro:
        opciones = df[col].dropna().unique().tolist()
        seleccion = st.multiselect(f"Valores para '{col}':", opciones)
        if seleccion:
            df = df[df[col].isin(seleccion)]
    return df

def agrupar_por_fiscalId(df):
    if 'fiscalId' not in df.columns:
        st.error("❌ La columna 'fiscalId' es obligatoria para agrupar.")
        return pd.DataFrame()

    df['totalPendiente'] = pd.to_numeric(df.get('totalPendiente', 0), errors='coerce').fillna(0)
    agrupado = df.groupby('fiscalId').agg({
        'totalPendiente': 'sum',
        'invoiceNumber': 'count',
        'nombre_empresa': 'first',
        'direccionCliente': 'first',
        'emailFacturacion': 'first'
    }).reset_index()

    agrupado = agrupado.rename(columns={
        'totalPendiente': 'Suma_Pendientes',
        'invoiceNumber': 'Total_Facturas'
    })
    agrupado['Total_Facturas'] = agrupado['Total_Facturas'].astype(str) + ' factura(s) pendiente(s)'
    return agrupado

def descargar_excel(df, nombre_archivo):
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    st.download_button("📥 Descargar archivo Excel", buffer, file_name=f"{nombre_archivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

archivo = st.file_uploader("📤 Sube tu archivo Excel o CSV", type=['xlsx', 'csv'])

if archivo:
    if archivo.name.endswith('.xlsx'):
        df = pd.read_excel(archivo)
    else:
        df = pd.read_csv(archivo, encoding='utf-8', delimiter=';', on_bad_lines='skip', engine='python')

    st.success(f"✅ Archivo cargado con {df.shape[0]} filas y {df.shape[1]} columnas.")

    df = limpiar_dataframe(df)
    st.dataframe(df.head())

    df_filtrado = aplicar_filtros(df)
    st.write(f"🔎 Filtrado: {df_filtrado.shape[0]} filas restantes")

    if st.button("📊 Agrupar por fiscalId"):
        with st.spinner("Agrupando datos..."):
            df_agrupado = agrupar_por_fiscalId(df_filtrado)
            st.dataframe(df_agrupado)
            nombre = st.text_input("📄 Nombre del archivo de salida:", "resultado_agrupado")
            descargar_excel(df_agrupado, nombre)
else:
    st.info("Por favor sube un archivo para comenzar.")
