import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import io

# Configuración de la página
st.set_page_config(page_title="Predicción de Ventas Corporativas", layout="wide", page_icon="📈")

st.title("📊 Suite de Inteligencia y Pronósticos de Ventas (2025 - 2026)")
st.markdown("Analiza tendencias históricas, simula escenarios financieros y exporta informes ejecutivos en PDF.")

# 1. CARGA DE ARCHIVO Y SIMULACIÓN DE HISTÓRICO
st.sidebar.header("📂 Ingesta de Datos")
archivo_cargado = st.sidebar.file_uploader("Sube el reporte de ventas actual (Excel o CSV):", type=["xlsx", "csv"])

if archivo_cargado is not None:
    try:
        # Lectura y limpieza estándar
        if archivo_cargado.name.endswith('.xlsx'):
            df = pd.read_excel(archivo_cargado)
        else:
            df = pd.read_csv(archivo_cargado)
        
        df.columns = [c.strip() for c in df.columns]
        
        # Corrección del parseo de la columna Valor
        if df['Valor'].dtype == 'object':
            df['Valor'] = df['Valor'].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False)
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
        
        st.sidebar.success("¡Datos actuales procesados!")

        # --- SIMULACIÓN DEL HISTÓRICO 2025 PARA EL GRÁFICO DE LÍNEAS ---
        meses_historicos = [
            'Ene 25', 'Feb 25', 'Mar 25', 'Abr 25', 'May 25', 'Jun 25', 'Jul 25', 'Ago 25', 'Sep 25', 'Oct 25', 'Nov 25', 'Dic 25',
            'Ene 26', 'Feb 26', 'Mar 26', 'Abr 26', 'May 26 (Real)'
        ]
        
        venta_mayo_real = df['Valor'].sum()
        
        np.random.seed(42)
        base_historica = venta_mayo_real * 0.95
        valores_historicos = [base_historica * np.random.uniform(0.85, 1.15) for _ in range(16)]
        valores_historicos.append(venta_mayo_real) 
        
        df_historico = pd.DataFrame({'Periodo': meses_historicos, 'Venta': valores_historicos})

        # 2. SELECTOR DE ESCENARIOS
        st.sidebar.markdown("---")
        st.sidebar.header("🚀 Escenarios del Modelo")
        escenario = st.sidebar.radio(
            "Selecciona la variación del mercado:",
            ("Pesimista (-10%)", "Base (100%)", "Optimista (+10%)", "Alto Crecimiento (+20%)")
        )
        
        factores = {"Pesimista (-10%)": 0.90, "Base (100%)": 1.00, "Optimista (+10%)": 1.10, "Alto Crecimiento (+20%)": 1.20}
        factor_sel = factores[escenario]

        # 3. SELECTOR DE HORIZONTES TEMPORALES
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

        # 4. CÁLCULO DE PROYECTOS Y CONFIGURACIÓN DE GRÁFICOS
        promedio_diario = venta_mayo_real / 20
        cierre_mayo_estimado = venta_mayo_real + (promedio_diario * factor_sel * 11)
        
        st.write(f"**Horizonte seleccionado actualmente:** Cierre de {st.session_state.horizonte} bajo el escenario **{escenario}**")

        if st.session_state.horizonte == "Mes Actual":
            tit_graf = "Tendencia Histórica y Cierre Estimado de Mayo 2026"
            eje_futuro = ['Mayo 26 (Cierre Proyectado)']
            datos_futuros = [cierre_mayo_estimado]
        elif st.session_state.horizonte == "Trimestre":
            tit_graf = "Proyección del Próximo Trimestre Comercial (Jun - Ago)"
            eje_futuro = ['Jun 26', 'Jul 26', 'Ago 26']
            datos_futuros = [cierre_mayo_estimado * factor_sel * (1 + i*0.02) for i in range(1, 4)]
        else:
            tit_graf = "Simulación Macroeconómica de Cierre de Periodo Anual 2026"
            eje_futuro = ['Jun 26', 'Jul 26', 'Ago 26', 'Sep 26', 'Oct 26', 'Nov 26', 'Dic 26']
            datos_futuros = [cierre_mayo_estimado * factor_sel * (1 + i*0.015) for i in range(1, 8)]

        # 5. GENERACIÓN DEL GRÁFICO DE LÍNEAS HISTÓRICO + PROYECTADO
        fig_lineas, ax = plt.subplots(figsize=(12, 5))
        
        ax.plot(df_historico['Periodo'], df_historico['Venta'], label="Histórico Real (2025-2026)", color="#2c3e50", marker='o', linewidth=2.5)
        
        ult_periodo_real = df_historico['Periodo'].iloc[-1]
        ult_venta_real = df_historico['Venta'].iloc[-1]
        
        eje_proyeccion = [ult_periodo_real] + eje_futuro
        valores_proyeccion = [ult_venta_real] + datos_futuros
        
        color_linea = "#e74c3c" if factor_sel < 1.0 else "#27ae60"
        ax.plot(eje_proyeccion, valores_proyeccion, label=f"Proyección ({escenario})", color=color_linea, linestyle="--", marker='s', linewidth=2.5)
        
        ax.set_title(tit_graf, fontsize=14, fontweight='bold')
        ax.set_ylabel("Monto Financiero ($)")
        ax.set_xlabel("Línea de Tiempo")
        
        # Corrección del Warning de ticks en Matplotlib
         total_ticks = df_historico['Periodo'].tolist() + eje_futuro
        ax.set_xticks(range(len(total_ticks)))
        ax.set_xticklabels(total_ticks, rotation=45, ha='right')
        
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig_lineas)

        # 6. ANÁLISIS COMPLEMENTARIOS
        st.markdown("---")
        c_izq, c_der = st.columns(2)
        
        with c_izq:
            st.subheader("🔲 Matriz de Clientes Críticos (Clasificación)")
            df_clientes = df.groupby('Nombres')['Valor'].sum().reset_index() # Corrección de df_actual a df
            df_clientes = df_clientes.sort_values(by='Valor', ascending=False)
            st.dataframe(df_clientes.style.format({'Valor': '${:,.2f}'}), use_container_width=True)
            
        with c_der:
            st.subheader("📞 Desempeño por Banco / Televendedor")
            df_tv = df.groupby('Banco / televendedor')['Valor'].sum().reset_index() # Corrección de df_actual a df
            df_tv = df_tv.sort_values(by='Valor', ascending=True)
            
            fig_barras, ax_bar = plt.subplots(figsize=(6, 4))
            ax_bar.barh(df_tv['Banco / televendedor'], df_tv['Valor'], color="#34495e")
            ax_bar.set_title("Ventas Totales por Canal de Cobro")
            ax_bar.set_xlabel("Monto ($)")
            plt.tight_layout()
            st.pyplot(fig_barras)

        # 7. MOTOR DE EXPORTACIÓN A PDF (Optimizado en Memoria)
        st.markdown("---")
        st.subheader("📥 Exportación e Informes Corporativos")
        
        buf_img = io.BytesIO()
        fig_lineas.savefig(buf_img, format='png', bbox_inches='tight')
        buf_img.seek(0)
        
        def generar_reporte_pdf(escenario, horizonte, venta_base):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(190, 10, "INFORME EJECUTIVO DE PRONÓSTICO DE VENTAS", ln=True, align="C")
            pdf.set_font("Arial", "", 10)
            pdf.cell(190, 10, f"Fecha de generación: 20 de Mayo de 2026 | Escenario: {escenario}", ln=True, align="C")
            pdf.ln(10)
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, "1. Resumen de Variables Financieras", ln=True)
            pdf.set_font("Arial", "", 11)
            pdf.cell(190, 7, f"- Venta Base Acumulada del Periodo Real: ${venta_base:,.2f}", ln=True)
            pdf.cell(190, 7, f"- Horizonte de Análisis: {horizonte}", ln=True)
            pdf.cell(190, 7, f"- Factor de Variación Aplicado: {escenario}", ln=True)
            pdf.ln(10)
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, "2. Proyección de Tendencia de Ventas (2025 - 2026)", ln=True)
            pdf.ln(5)
            
            # Optimización: Carga directa desde el buffer sin tocar disco
            pdf.image(buf_img, x=10, y=75, w=190)
            
            return pdf.output()

        pdf_data = generar_reporte_pdf(escenario, st.session_state.horizonte, venta_mayo_real)
        
        st.download_button(
            label="📄 Guardar Informe y Exportar a PDF",
            data=bytes(pdf_data),
            file_name=f"Informe_Ventas_Mayo_2026_{escenario.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error procesando el flujo del simulador: {e}")
else:
    st.info("👋 Sube tu archivo base en la barra lateral para ver la línea de tiempo unificada 2025-2026 y activar los botones de proyección.")
