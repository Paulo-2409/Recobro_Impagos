import streamlit as st
import pandas as pd
import unicodedata
import re
from datetime import datetime

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
        return df
    estados = df['Estado_deuda'].dropna().unique()
    seleccionados = st.multiselect("Filtrar por Estado_deuda:", options=estados)
    if seleccionados:
        return df[df['Estado_deuda'].isin(seleccionados)]
    return df

def filtrar_por_fecha(df):
    if 'fechaDevolucion' not in df.columns:
        return df
    opciones = {
        "No aplicar filtro": 4,
        "Antigüedad entre 9 y 30 días": 1,
        "Antigüedad entre 9 y 60 días": 2,
        "Fecha mínima específica": 3,
    }
    opcion = st.selectbox("Filtrar por fecha de devolución:", list(opciones.keys()))
    hoy = datetime.now()
    df['fechaDevolucion'] = pd.to_datetime(df['fechaDevolucion'], errors='coerce', dayfirst=True)

    if opciones[opcion] == 1:
        desde = hoy - pd.Timedelta(days=30)
        hasta = hoy - pd.Timedelta(days=9)
        return df[(df['fechaDevolucion'] >= desde) & (df['fechaDevolucion'] <= hasta)]

    elif opciones[opcion] == 2:
        desde = hoy - pd.Timedelta(days=60)
        hasta = hoy - pd.Timedelta(days=9)
        return df[(df['fechaDevolucion'] >= desde) & (df['fechaDevolucion'] <= hasta)]

    elif opciones[opcion] == 3:
        fecha = st.date_input("Selecciona la fecha mínima:")
        return df[df['fechaDevolucion'] >= pd.to_datetime(fecha)]

    return df

def formatear_columnas_fecha(df, columnas):
    for col in columnas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')
    return df

def agrupar_por_fiscalId(df):
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

# Interfaz Streamlit
st.title("🧹 Limpieza y Agrupación de Facturas")

archivo = st.file_uploader("Sube un archivo Excel o CSV", type=['xlsx', 'csv'])

if archivo:
    if archivo.name.endswith('.xlsx'):
        df = pd.read_excel(archivo)
    else:
        df = pd.read_csv(archivo, encoding='utf-8', delimiter=';', on_bad_lines='skip', engine='python')

    st.success("Archivo cargado correctamente.")
    df = limpiar_dataframe(df)
    df = filtrar_por_estado(df)
    df = filtrar_por_fecha(df)
    columnas_fecha = ['fechaDevolucion', 'fechaEmisionFactura', 'fecha_pago', 'fechaInicioFactura', 'fechaFinFactura']
    df = formatear_columnas_fecha(df, columnas_fecha)
    df_final = agrupar_por_fiscalId(df)

    st.subheader("📊 Resultado Final")
    st.dataframe(df_final)

    nombre_archivo = st.text_input("📥 Nombre para guardar el archivo Excel (sin .xlsx)", "resultado")

    if st.button("💾 Generar Excel"):
        from io import BytesIO
        output = BytesIO()
        df_final.to_excel(output, index=False, engine='openpyxl')
        st.download_button(label="📥 Descargar archivo Excel",
                           data=output.getvalue(),
                           file_name=f"{nombre_archivo}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")