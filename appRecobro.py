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

def filtrar_por_estado(df):
    if 'Estado_deuda' not in df.columns:
        st.warning("⚠️ La columna 'Estado_deuda' no está presente en el archivo.")
        return df

    estados = df['Estado_deuda'].dropna().unique().tolist()
    if not estados:
        st.warning("⚠️ No hay estados disponibles para filtrar.")
        return df

    seleccionados = st.multiselect("📌 Filtrar por Estado_deuda:", estados)
    if seleccionados:
        return df[df['Estado_deuda'].isin(seleccionados)]
    return df

def filtrar_por_fecha(df):
    if 'fechaDevolucion' not in df.columns:
        return df

    try:
        df['fechaDevolucion'] = pd.to_datetime(df['fechaDevolucion'], errors='coerce', dayfirst=True)
    except Exception as e:
        st.error(f"❌ Error convirtiendo fechas: {e}")
        return df

    opciones = {
        "No aplicar filtro": 4,
        "Antigüedad entre 9 y 30 días": 1,
        "Antigüedad entre 9 y 60 días": 2,
        "Fecha mínima específica": 3
    }
    seleccion = st.selectbox("📅 Filtro por fecha de devolución:", list(opciones.keys()))
    hoy = datetime.now()

    if opciones[seleccion] == 1:
        desde, hasta = hoy - pd.Timedelta(days=30), hoy - pd.Timedelta(days=9)
        return df[(df['fechaDevolucion'] >= desde) & (df['fechaDevolucion'] <= hasta)]

    elif opciones[seleccion] == 2:
        desde, hasta = hoy - pd.Timedelta(days=60), hoy - pd.Timedelta(days=9)
        return df[(df['fechaDevolucion'] >= desde) & (df['fechaDevolucion'] <= hasta)]

    elif opciones[seleccion] == 3:
        fecha_input = st.date_input("📅 Selecciona la fecha mínima:")
        return df[df['fechaDevolucion'] >= pd.to_datetime(fecha_input)]

    return df

def formatear_columnas_fecha(df, columnas):
    for col in columnas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')
    return df

def agrupar_por_fiscalId(df):
    if 'fiscalId' not in df.columns:
        st.error("❌ La columna 'fiscalId' es obligatoria para agrupar.")
        return pd.DataFrame()

    columnas_factura = ['fechaDevolucion', 'totalPendiente', 'Estado_deuda', 'invoiceNumber']
    telefonos = ['telefonoContacto', 'telefonoCabecera', 'telefono3']
    datos_base = ['fiscalId', 'nombre_empresa', 'direccionCliente', 'emailFacturacion']
    columnas_existentes = [col for col in columnas_factura + telefonos + datos_base if col in df.columns]
    df = df[columnas_existentes].copy()

    if 'totalPendiente' in df.columns:
        df['totalPendiente'] = pd.to_numeric(df['totalPendiente'], errors='coerce').fillna(0)

    agrupado = []
    for fiscalId, subdf in df.groupby('fiscalId'):
        fila = {'fiscalId': fiscalId}
        base = subdf.iloc[0]
        for campo in ['nombre_empresa', 'direccionCliente', 'emailFacturacion']:
            fila[campo] = base.get(campo, '')
        fila['Suma_Pendientes'] = round(subdf['totalPendiente'].sum(), 2)
        fila['Total_Facturas'] = f"{len(subdf)} factura{'s' if len(subdf) != 1 else ''} pendiente{'s' if len(subdf) != 1 else ''}"

        telefonos_validos = [col for col in telefonos if col in subdf.columns]
        telefonos_unicos = pd.unique(subdf[telefonos_validos].values.ravel())
        telefonos_unicos = [t for t in telefonos_unicos if pd.notna(t)]
        for i, tel in enumerate(telefonos_unicos):
            fila[f'telefono_{i+1}'] = tel

        for i, (_, row) in enumerate(subdf.iterrows(), 1):
            fila[f'fechaDevolucion_{i}'] = row.get('fechaDevolucion', '')
            fila[f'totalPendiente_{i}'] = row.get('totalPendiente', '')
            fila[f'Estado_deuda_{i}'] = row.get('Estado_deuda', '')
            fila[f'invoiceNumber_{i}'] = row.get('invoiceNumber', '')

        agrupado.append(fila)

    return pd.DataFrame(agrupado)

# === APP ===
archivo = st.file_uploader("📤 Sube tu archivo Excel o CSV", type=['xlsx', 'csv'])

if archivo:
    try:
        with st.spinner("📂 Cargando archivo..."):
            if archivo.name.endswith('.xlsx'):
                df = pd.read_excel(archivo)
            else:
                df = pd.read_csv(archivo, encoding='utf-8', delimiter=';', on_bad_lines='skip', engine='python')

        st.success(f"✅ Archivo cargado con {df.shape[0]} filas y {df.shape[1]} columnas.")

        df = limpiar_dataframe(df)

        st.subheader("🔍 Vista previa del archivo limpio")
        st.dataframe(df.head())

        df = filtrar_por_estado(df)
        df = filtrar_por_fecha(df)

        if df.empty:
            st.error("❌ El filtro aplicado no devolvió resultados.")
            st.stop()

        columnas_fecha = ['fechaDevolucion', 'fechaEmisionFactura', 'fecha_pago', 'fechaInicioFactura', 'fechaFinFactura']
        df = formatear_columnas_fecha(df, columnas_fecha)

        with st.spinner("⏳ Agrupando datos..."):
            df_final = agrupar_por_fiscalId(df)

        if df_final.empty:
            st.error("❌ No se pudo agrupar. Verifica que exista la columna 'fiscalId'.")
            st.stop()

        st.subheader("📊 Resultado final")
        st.dataframe(df_final)

        nombre_archivo = st.text_input("💾 Nombre del archivo de salida:", "facturas_limpias")
        if st.button("📥 Descargar Excel"):
            output = BytesIO()
            df_final.to_excel(output, index=False, engine='openpyxl')
            st.download_button(label="⬇️ Descargar archivo Excel",
                               data=output.getvalue(),
                               file_name=f"{nombre_archivo}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
else:
    st.info("Por favor sube un archivo para comenzar.")
