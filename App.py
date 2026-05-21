import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import datetime

# ── 1. CONFIGURACIÓN DE LA PÁGINA Y ESTILOS ─────────────────────────────────
st.set_page_config(
    page_title="Suite de Pronósticos de Ventas",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos visuales personalizados para el entorno
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0a1628; }
    [data-testid="stSidebar"] * { color: #e8edf5 !important; }
    .metric-card {
        background: linear-gradient(135deg, #1a2744 0%, #0d1b33 100%);
        border: 1px solid #2a3f6f;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
        color: white;
    }
    .metric-card .metric-label { font-size: 12px; color: #8fa3c8; margin-bottom: 4px; }
    .metric-card .metric-value { font-size: 22px; font-weight: 700; color: #4fc3f7; }
    .metric-card .metric-sub   { font-size: 11px; color: #5a7ab0; margin-top: 2px; }
    .section-header {
        font-size: 14px; font-weight: 600; color: #4fc3f7;
        text-transform: uppercase; letter-spacing: 0.08em;
        border-bottom: 1px solid #1e3155; padding-bottom: 6px; margin-bottom: 12px;
    }
    div[data-testid="stDownloadButton"] button {
        background: #1565c0; color: white; border-radius: 8px;
        font-weight: 600; width: 100%; font-size: 14px;
        border: none; padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ── 2. FUNCIÓN DE LIMPIEZA DE MONEDAS ────────────────────────────────────────
def limpiar_valores_moneda(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace('$', '').replace(' ', '')
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        partes = s.split(',')
        if len(partes) == 2 and len(partes[1]) == 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    try:
        return float(s)
    except ValueError:
        return 0.0

# ── 3. CONTROLES DE LA BARRA LATERAL ─────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="section-header">📂 Ingesta de Datos</p>', unsafe_allow_html=True)
    archivo_cargado = st.file_uploader("Sube el reporte de ventas actual (Excel o CSV):", type=["xlsx", "csv"])
    
    st.markdown('<p class="section-header">🚀 Escenarios del Modelo</p>', unsafe_allow_html=True)
    escenario = st.radio(
        "Selecciona la variación del mercado:",
        ("Pesimista (-10%)", "Base (100%)", "Optimista (+10%)", "Alto Crecimiento (+20%)"),
        index=1
    )
    
    st.markdown('<p class="section-header">🎲 Configuración Estadística</p>', unsafe_allow_html=True)
    volatilidad = st.slider("Volatilidad del mercado (%)", min_value=5, max_value=40, value=15, step=5) / 100.0

# Mapeo de factores económicos del escenario
factores = {"Pesimista (-10%)": 0.90, "Base (100%)": 1.00, "Optimista (+10%)": 1.10, "Alto Crecimiento (+20%)": 1.20}
factor_sel = factores[escenario]

# ── 4. PROCESAMIENTO CENTRAL DE LA APLICACIÓN ────────────────────────────────
if archivo_cargado is not None:
    try:
        # Lectura de datos según extensión
        if archivo_cargado.name.endswith('.xlsx'):
            df = pd.read_excel(archivo_cargado)
        else:
            df = pd.read_csv(archivo_cargado)
        
        # Limpieza inicial de espacios invisibles en los encabezados
        df.columns = [c.strip() for c in df.columns]
        
        # ── DETECCIÓN INTELIGENTE Y FLEXIBLE DE COLUMNAS ──
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        col_valor = next((c for c in df.columns if 'valor' in c.lower() or 'monto' in c.lower() or 'total' in c.lower()), None)
        col_banco = next((c for c in df.columns if 'banco' in c.lower() or 'televendedor' in c.lower() or 'canal' in c.lower()), None)
        col_nombres = next((c for c in df.columns if 'nombre' in c.lower() or 'cliente' in c.lower()), None)
        
        # Si falta alguna, detenemos la app y le mostramos al usuario qué columnas tiene su archivo
        if not (col_fecha and col_valor and col_banco and col_nombres):
            st.error("⚠️ No se pudieron mapear automáticamente las columnas necesarias en tu archivo.")
            st.markdown("### 🔍 Estructura encontrada en tu documento:")
            st.write("Las columnas detectadas son las siguientes. Asegúrate de que existan equivalentes para Fecha, Valor, Banco/Televendedor y Nombres:")
            st.code(list(df.columns))
            st.stop()
            
        # Renombrar internamente de manera dinámica para mantener la estabilidad del script
        df = df.rename(columns={
            col_fecha: 'Fecha',
            col_valor: 'Valor',
            col_banco: 'Banco / televendedor',
            col_nombres: 'Nombres'
        })
            
        # Sanitizar columna monetaria
        df['Valor'] = df['Valor'].apply(limpiar_valores_moneda)
        
        # Variables fijas de control de tiempo (Corte: 20 de Mayo)
        fecha_corte = 20
        dias_totales_mayo = 31
        dias_restantes = dias_totales_mayo - fecha_corte
        
        # Métricas Reales Actuales
        venta_mayo_real = df['Valor'].sum()
        promedio_diario_real = venta_mayo_real / fecha_corte
        
        st.sidebar.success("¡Datos procesados exitosamente!")

        # ── 5. SELECCIÓN DE HORIZONTES DE PROYECCIÓN ─────────────────────────────
        st.markdown("### 🔮 Elige el Horizonte de la Proyección")
        col_b1, col_b2, col_b3 = st.columns(3)
        
        if 'horizonte' not in st.session_state:
            st.session_state.horizonte = "Mes Actual"
            
        if col_b1.button("📅 Cierre Mes Actual (Mayo)", use_container_width=True):
            st.session_state.horizonte = "Mes Actual"
        if col_b2.button("📊 Próximos 3 Meses (Trimestre)", use_container_width=True):
            st.session_state.horizonte = "Trimestre"
        if col_b3.button("🦅 Cierre de Periodo (Año 2026 Completo)", use_container_width=True):
            st.session_state.horizonte = "Año Completo"

        # ── 6. ALGORITMO PREDICTIVO Y SIMULACIÓN ESTOCÁSTICA ─────────────────────
        np.random.seed(42)
        simulaciones = 1000
        media_diaria_ajustada = promedio_diario_real * factor_sel
        
        if st.session_state.horizonte == "Mes Actual":
            sim_remanente = np.random.normal(loc=media_diaria_ajustada, scale=media_diaria_ajustada * volatilidad,
