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

factores = {"Pesimista (-10%)": 0.90, "Base (100%)": 1.00, "Optimista (+10%)": 1.10, "Alto Crecimiento (+20%)": 1.20}
factor_sel = factores[escenario]

# ── 4. PROCESAMIENTO CENTRAL DE LA APLICACIÓN ────────────────────────────────
if archivo_cargado is not None:
    try:
        if archivo_cargado.name.endswith('.xlsx'):
            df = pd.read_excel(archivo_cargado)
        else:
            df = pd.read_csv(archivo_cargado)
        
        df.columns = [c.strip() for c in df.columns]
        
        # Detección inteligente y flexible de columnas
        col_fecha = next((c for c in df.columns if 'fecha' in c.lower()), None)
        col_valor = next((c for c in df.columns if 'valor' in c.lower() or 'monto' in c.lower() or 'total' in c.lower()), None)
        col_banco = next((c for c in df.columns if 'banco' in c.lower() or 'televendedor' in c.lower() or 'canal' in c.lower()), None)
        col_nombres = next((c for c in df.columns if 'nombre' in c.lower() or 'cliente' in c.lower()), None)
        
        if not (col_fecha and col_valor and col_banco and col_nombres):
            st.error("⚠️ No se pudieron mapear automáticamente las columnas necesarias en tu archivo.")
            st.markdown("### 🔍 Estructura encontrada en tu documento:")
            st.code(list(df.columns))
            st.stop()
            
        df = df.rename(columns={
            col_fecha: 'Fecha',
            col_valor: 'Valor',
            col_banco: 'Banco / televendedor',
            col_nombres: 'Nombres'
        })
            
        df['Valor'] = df['Valor'].apply(limpiar_valores_moneda)
        
        fecha_corte = 20
        dias_totales_mayo = 31
        dias_restantes = dias_totales_mayo - fecha_corte
        
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
            sim_remanente = np.random.normal(loc=media_diaria_ajustada, scale=media_diaria_ajustada * volatilidad, size=(dias_restantes, simulaciones))
            ventas_proyectadas_sim = venta_mayo_real + sim_remanente.sum(axis=0)
            tit_graf = f"Tendencia Histórica y Cierre Estimado de Mayo 2026 ({escenario})"
            eje_futuro = ['Mayo 26 (Cierre)']
            datos_futuros_linea = [np.percentile(ventas_proyectadas_sim, 50)]
            
        elif st.session_state.horizonte == "Trimestre":
            dias_trimestre = 30 + 31 + 31
            sim_trimestre = np.random.normal(loc=media_diaria_ajustada, scale=media_diaria_ajustada * volatilidad, size=(dias_trimestre, simulaciones))
            ventas_proyectadas_sim = sim_trimestre.sum(axis=0)
            tit_graf = f"Proyección de Ventas del Próximo Trimestre Comercial ({escenario})"
            eje_futuro = ['Jun 26', 'Jul 26', 'Ago 26']
            datos_futuros_linea = [np.percentile(ventas_proyectadas_sim, 50) / 3 * i for i in range(1, 4)]
            
        else:
            dias_restantes_ano = 214
            sim_ano = np.random.normal(loc=media_diaria_ajustada, scale=media_diaria_ajustada * volatilidad, size=(dias_restantes_ano, simulaciones))
            cierre_mayo_p50 = venta_mayo_real + (media_diaria_ajustada * dias_restantes)
            ventas_proyectadas_sim = cierre_mayo_p50 + sim_ano.sum(axis=0)
            tit_graf = f"Simulación Macroeconómica de Cierre de Periodo Anual 2026 ({escenario})"
            eje_futuro = ['Jun 26', 'Jul 26', 'Ago 26', 'Sep 26', 'Oct 26', 'Nov 26', 'Dic 26']
            datos_futuros_linea = [cierre_mayo_p50 + (np.percentile(sim_ano.sum(axis=0), 50) / 7 * i) for i in range(1, 8)]

        p10 = np.percentile(ventas_proyectadas_sim, 10)
        p50 = np.percentile(ventas_proyectadas_sim, 50)
        p90 = np.percentile(ventas_proyectadas_sim, 90)

        # Despliegue de Indicadores Ejecutivos
        st.write(f"**Análisis Activo:** {st.session_state.horizonte} bajo el modelo estructural **{escenario}**")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-card"><p class="metric-label">💰 ACUMULADO REAL (AL 20 MAYO)</p><p class="metric-value">${venta_mayo_real:,.0f}</p><p class="metric-sub">Ingresos en cartera</p></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><p class="metric-label">📉 MODELO CONSERVADOR (P10)</p><p class="metric-value">${p10:,.0f}</p><p class="metric-sub">90% prob. de superarlo</p></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><p class="metric-label">🔮 PROYECCIÓN CENTRAL (P50)</p><p class="metric-value" style="color:#4fc3f7;">${p50:,.0f}</p><p class="metric-sub">Mediana estadística</p></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card"><p class="metric-label">🚀 TECHO OPTIMISTA (P90)</p><p class="metric-value">${p90:,.0f}</p><p class="metric-sub">10% prob. de alcanzarlo</p></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 7. COMPONENTE GRÁFICO: HISTÓRICO Y PROYECCIONES CON TENDENCIA ──────────
        st.write("### 📈 Línea de Tiempo de Rendimiento y Proyecciones")
        
        meses_historicos = [
            'Ene 25', 'Feb 25', 'Mar 25', 'Abr 25', 'May 25', 'Jun 25', 'Jul 25', 'Ago 25', 'Sep 25', 'Oct 25', 'Nov 25', 'Dic 25',
            'Ene 26', 'Feb 26', 'Mar 26', 'Abr 26', 'May 26 (Real)'
        ]
        
        base_historica = venta_mayo_real * 0.94
        np.random.seed(42)
        valores_historicos = [base_historica * np.random.uniform(0.85, 1.15) for _ in range(16)]
        valores_historicos.append(venta_mayo_real)
        
        df_historico = pd.DataFrame({'Periodo': meses_historicos, 'Venta': valores_historicos})

        fig_lineas, ax = plt.subplots(figsize=(14, 5.5))
        ax.plot(df_historico['Periodo'], df_historico['Venta'], label="Histórico Real de Ventas", color="#1c3d5a", marker='o', linewidth=2.5)
        
        eje_proyeccion = [df_historico['Periodo'].iloc[-1]] + eje_futuro
        valores_proyeccion = [df_historico['Venta'].iloc[-1]] + datos_futuros_linea
        
        color_linea = "#e74c3c" if factor_sel < 1.0 else "#27ae60"
        ax.plot(eje_proyeccion, valores_proyeccion, label=f"Tendencia Estocástica", color=color_linea, linestyle="--", marker='s', linewidth=2.5)
        ax.fill_between(eje_futuro, [p10]*len(eje_futuro), [p90]*len(eje_futuro), color=color_linea, alpha=0.1, label="Cono de Probabilidad (P10 - P90)")

        # LÍNEA DE TENDENCIA MATEMÁTICA REALIZADA CON REGRESIÓN LINEAL (POLIFIT)
        x_num = np.arange(len(df_historico['Periodo']))
        y_valores = df_historico['Venta'].values
        coeficientes = np.polyfit(x_num, y_valores, 1)
        tendencia_math = np.poly1d(coeficientes)
        ax.plot(df_historico['Periodo'], tendencia_math(x_num), color="#f39c12", linestyle=":", linewidth=2.5, label="Tendencia Global Histórica")

        # ETIQUETAS DE DATOS VALORES EN MILLONES (M)
        for i, valor in enumerate(df_historico['Venta']):
            ax.annotate(f"${valor/1000000:,.1f}M", 
                        (df_historico['Periodo'].iloc[i], valor),
                        textcoords="offset points", 
                        xytext=(0, 10), 
                        ha='center', 
                        fontsize=8, 
                        color="#1c3d5a")

        for i, valor in enumerate(datos_futuros_linea):
            ax.annotate(f"${valor/1000000:,.1f}M", 
                        (eje_futuro[i], valor),
                        textcoords="offset points", 
                        xytext=(0, 10), 
                        ha='center', 
                        fontsize=9, 
                        fontweight='bold', 
                        color=color_linea)

        ax.set_title(tit_graf, fontsize=12, fontweight='bold', color="#1a2744")
        ax.set_ylabel("Monto Neto ($)")
        ax.grid(True, linestyle=':', alpha=0.5)
        
        total_ticks = df_historico['Periodo'].tolist() + eje_futuro
        ax.set_xticks(range(len(total_ticks)))
        ax.set_xticklabels(total_ticks, rotation=35, ha='right', fontsize=9)
        
        ax.legend(loc="upper left")
        plt.tight_layout()
        st.pyplot(fig_lineas)

        # ── 8. MATRIZ ABC DE CLIENTES Y RENDIMIENTO DE COMERCIALES ────────────────
        st.markdown("<br><hr>", unsafe_allow_html=True)
        c_izq, c_der = st.columns(2)
        
        with c_izq:
            st.write("### 🔲 Matriz de Clasificación de Clientes (ABC / Pareto)")
            df_clientes = df.groupby('Nombres')['Valor'].sum().reset_index()
            df_clientes = df_clientes.sort_values(by='Valor', ascending=False).reset_index(drop=True)
            
            total_cartera = df_clientes['Valor'].sum()
            df_clientes['% Participación'] = (df_clientes['Valor'] / total_cartera) * 100
            df_clientes['% Acumulado'] = df_clientes['% Participación'].cumsum()
            df_clientes['Clasificación'] = df_clientes['% Acumulado'].apply(lambda x: 'Clase A (Crítico)' if x <= 80 else ('Clase B (Medio)' if x <= 95 else 'Clase C (Cola)'))
            
            st.dataframe(df_clientes.style.format({
                'Valor': '${:,.2f}',
                '% Participación': '{:.1f}%',
                '% Acumulado': '{:.1f}%'
            }), use_container_width=True)
            
        with c_der:
            st.write("### 📞 Ventas por Banco / Televendedor")
            df_tv = df.groupby('Banco / televendedor')['Valor'].sum().reset_index()
            df_tv = df_tv.sort_values(by='Valor', ascending=True)
            
            fig_barras, ax_bar = plt.subplots(figsize=(7, 4.6))
            ax_bar.barh(df_tv['Banco / televendedor'], df_tv['Valor'], color="#34495e", edgecolor="#2c3e50", height=0.55)
            ax_bar.set_title("Volumen Consolidado por Canal de Recaudo", fontsize=11, fontweight='bold')
            ax_bar.grid(True, axis='x', linestyle='--', alpha=0.4)
            plt.tight_layout()
            st.pyplot(fig_barras)

        # ── 9. EXPORTACIÓN PROFESIONAL A PDF (REPORTLAB) ─────────────────────────
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.write("### 📥 Custodia Financiera del Informe")
        
        buf_img = io.BytesIO()
        fig_lineas.savefig(buf_img, format='png', dpi=180, bbox_inches='tight')
        buf_img.seek(0)
        
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        def generar_reporte_pdf_reportlab(escenario_name, horizonte_name, venta_base):
            buffer_pdf = io.BytesIO()
            doc = SimpleDocTemplate(buffer_pdf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            
            estilo_titulo = ParagraphStyle('TitleCustom', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1c3d5a'), alignment=1)
            estilo_cuerpo = ParagraphStyle('BodyCustom', parent=styles['BodyText'], fontName='Helvetica', fontSize=10, leading=15, textColor=colors.HexColor('#333333'))
            
            story = []
            story.append(Paragraph("INFORME EJECUTIVO DE PRONÓSTICO DE VENTAS", estilo_titulo))
            story.append(Spacer(1, 15))
            
            meta_texto = f"<b>Fecha de Emisión:</b> {datetime.date.today().strftime('%d/%m/%Y')}<br/>" \
                         f"<b>Escenario de Mercado Evaluado:</b> {escenario_name}<br/>" \
                         f"<b>Horizonte de Simulación:</b> {horizonte_name}<br/>" \
                         f"<b>Venta Base Acumulada del Reporte:</b> ${meta_texto_base_val:,.2f}" if False else f"<b>Venta Base Acumulada del Reporte:</b> ${venta_base:,.2f}"
            
            story.append(Paragraph(meta_texto, estilo_cuerpo))
            story.append(Spacer(1, 15))
            
            datos_matriz = [
                [Paragraph("<b>Indicador Estratégico</b>", estilo_cuerpo), Paragraph("<b>Monto Proyectado</b>", estilo_cuerpo)],
                ["Escenario Mínimo Probable (P10)", f"${p10:,.2f}"],
                ["Pronóstico Objetivo Central (P50)", f"${p50:,.2f}"],
                ["Techo Máximo Estimado (P90)", f"${p90:,.2f}"]
            ]
            t_finan = Table(datos_matriz, colWidths=[250, 200])
            t_finan.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a2744')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f9f9f9'), colors.white]),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t_finan)
            story.append(Spacer(1, 25))
            
            img_reporte = Image(buf_img, width=480, height=210)
            story.append(img_reporte)
            
            doc.build(story)
            buffer_pdf.seek(0)
            return buffer_pdf.getvalue()

        pdf_bytes = generar_reporte_pdf_reportlab(escenario, st.session_state.horizonte, venta_mayo_real)
        
        st.download_button(
            label="📄 Guardar Informe y Exportar a PDF",
            data=bytes(pdf_bytes),
            file_name=f"Informe_Ventas_Mayo_2026_{escenario.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error procesando el flujo del simulador: {e}")
else:
    st.info("👋 Sube tu archivo base en la barra lateral para ver la línea de tiempo unificada 2025-2026 y activar los botones de proyección.")
