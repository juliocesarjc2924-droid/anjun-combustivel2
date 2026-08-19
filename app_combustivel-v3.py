import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="ANJUN - Indicador de Combustível Executivo",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Enterprise Layout
st.markdown("""
<style>
    /* Main body background and font */
    .main {
        background-color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    /* Metric Card Custom Design */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
        transition: all 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
        border-color: #cbd5e1;
    }
    /* Title text styling */
    h1 {
        color: #0f172a;
        font-weight: 800 !important;
        letter-spacing: -0.025em;
    }
    h2 {
        color: #1e293b;
        font-weight: 700 !important;
    }
    h3 {
        color: #334155;
        font-weight: 600 !important;
    }
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
        color: #475569;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f172a !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to convert Portuguese month name/year to chronological sort index
def get_fortnight_sort_key(name):
    if 'Jul' in name:
        return 1 if '1ª' in name else 2
    if 'Ago' in name:
        return 3 if '1ª' in name else 4
    if 'Set' in name:
        return 5 if '1ª' in name else 6
    return 99

# --- DATA LOADING ---
@st.cache_data
def load_and_clean_data(file_path_or_buffer):
    try:
        df = pd.read_csv(file_path_or_buffer, sep=';')
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return None

    # Helper to clean currency and numeric strings
    def clean_numeric(val):
        if pd.isna(val):
            return 0.0
        val_str = str(val).replace('R$', '').replace('.', '').replace(',', '.').strip()
        try:
            return float(val_str)
        except ValueError:
            return 0.0

    # Apply data cleansing
    numeric_cols = [
        'LITROS', 'VL/LITRO', 'VALOR EMISSAO', 
        'HODOMETRO OU HORIMETRO', 'KM RODADOS OU HORAS TRABALHADAS', 
        'KM/LITRO OU LITROS/HORA'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
            
    # Clean up dates
    if 'DATA TRANSACAO' in df.columns:
        df['DATA TRANSACAO'] = pd.to_datetime(df['DATA TRANSACAO'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df['DATA'] = df['DATA TRANSACAO'].dt.date
        
    # Standardize names
    df['NOME MOTORISTA'] = df['NOME MOTORISTA'].str.title()
    df['NOME ESTABELECIMENTO'] = df['NOME ESTABELECIMENTO'].str.title()
    
    # Fortnight (Quinzena) Definition
    def get_fortnight(row):
        dt = row['DATA TRANSACAO']
        if pd.isna(dt):
            return 'N/A'
        half = '1ª Q.'
        if dt.day > 15:
            half = '2ª Q.'
        
        months_br = {
            1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
        }
        m_name = months_br.get(dt.month, dt.strftime('%b'))
        year_short = dt.strftime('%y')
        return f"{half} {m_name}/{year_short}"

    df['QUINZENA'] = df.apply(get_fortnight, axis=1)
    df['CATEGORIA'] = df['MODELO VEICULO'].map({'MASTER': 'Master', 'EXPRESS': 'Delivery'}).fillna('Outros')
    
    # Calculate real cost per km if possible (Value / KM Rodados)
    # Mask division by zero or weird values
    df['CUSTO_KM'] = np.where(df['KM RODADOS OU HORAS TRABALHADAS'] > 0, df['VALOR EMISSAO'] / df['KM RODADOS OU HORAS TRABALHADAS'], 0.0)
    
    return df

# App Title & Header
col_logo, col_title = st.columns([1, 11])
with col_title:
    st.title("📊 Painel Executivo de Combustível — ANJUN")
    st.markdown("*Acompanhamento Estratégico de Performance, Custos Operacionais e Eficiência Energética*")

# Let user upload a file, otherwise fall back to default
uploaded_file = st.sidebar.file_uploader("📥 Enviar nova planilha (.csv)", type=["csv"])

df_raw = None
if uploaded_file is not None:
    df_raw = load_and_clean_data(uploaded_file)
    st.sidebar.success("Nova planilha carregada com sucesso!")
else:
    import os
    default_paths = ['Historico_de_abastecimento.csv', '/workspace/knowledge/Historico_de_abastecimento.csv']
    for p in default_paths:
        if os.path.exists(p):
            df_raw = load_and_clean_data(p)
            break
            
if df_raw is None:
    st.warning("⚠️ Por favor, faça o upload de uma planilha CSV no menu lateral para começar.")
    st.stop()

# --- SIDEBAR ADVANCED FILTERS ---
st.sidebar.header("🔍 Controles e Filtros de Análise")

# 1. Date Range
if 'DATA' in df_raw.columns and df_raw['DATA'].notna().any():
    min_date = df_raw['DATA'].min()
    max_date = df_raw['DATA'].max()
    date_range = st.sidebar.date_input(
        "Período de Análise",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
else:
    date_range = None

# 2. State (UF) Filter
ufs = sorted(df_raw['UF'].dropna().unique().tolist()) if 'UF' in df_raw.columns else []
selected_ufs = st.sidebar.multiselect("Estados (UF)", options=ufs, default=ufs)

# 3. Category Filter
categories = sorted(df_raw['CATEGORIA'].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Categoria do Veículo", options=categories, default=categories)

# 4. Vehicle Plate Filter
plates = sorted(df_raw['PLACA'].dropna().unique().tolist()) if 'PLACA' in df_raw.columns else []
selected_plates = st.sidebar.multiselect("Placas", options=plates, default=plates)

# 5. Driver Filter
drivers = sorted(df_raw['NOME MOTORISTA'].dropna().unique().tolist()) if 'NOME MOTORISTA' in df_raw.columns else []
selected_drivers = st.sidebar.multiselect("Motoristas", options=drivers, default=drivers)

# 6. Gas Station Filter
stations = sorted(df_raw['NOME ESTABELECIMENTO'].dropna().unique().tolist()) if 'NOME ESTABELECIMENTO' in df_raw.columns else []
selected_stations = st.sidebar.multiselect("Postos de Combustível", options=stations, default=[])

# 7. Fuel Type Filter
fuels = sorted(df_raw['TIPO COMBUSTIVEL'].dropna().unique().tolist()) if 'TIPO COMBUSTIVEL' in df_raw.columns else []
selected_fuels = st.sidebar.multiselect("Tipo de Combustível", options=fuels, default=fuels)

# 8. Transaction Value Filter
min_val, max_val = float(df_raw['VALOR EMISSAO'].min()), float(df_raw['VALOR EMISSAO'].max())
selected_val_range = st.sidebar.slider(
    "Faixa de Valor da Transação (R$)",
    min_value=min_val,
    max_value=max_val,
    value=(min_val, max_val)
)

# --- FILTER APPLICATION ---
df_filtered = df_raw.copy()

if date_range and len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df_filtered[(df_filtered['DATA'] >= start_date) & (df_filtered['DATA'] <= end_date)]

if selected_ufs:
    df_filtered = df_filtered[df_filtered['UF'].isin(selected_ufs)]
if selected_categories:
    df_filtered = df_filtered[df_filtered['CATEGORIA'].isin(selected_categories)]
if selected_plates:
    df_filtered = df_filtered[df_filtered['PLACA'].isin(selected_plates)]
if selected_drivers:
    df_filtered = df_filtered[df_filtered['NOME MOTORISTA'].isin(selected_drivers)]
if selected_stations:
    df_filtered = df_filtered[df_filtered['NOME ESTABELECIMENTO'].isin(selected_stations)]
if selected_fuels:
    df_filtered = df_filtered[df_filtered['TIPO COMBUSTIVEL'].isin(selected_fuels)]

df_filtered = df_filtered[
    (df_filtered['VALOR EMISSAO'] >= selected_val_range[0]) & 
    (df_filtered['VALOR EMISSAO'] <= selected_val_range[1])
]

if df_filtered.empty:
    st.error("❌ Nenhum registro encontrado para a combinação de filtros selecionada. Ajuste as opções ao lado.")
    st.stop()

# --- EXECUTIVE KPI METRICS ---
st.markdown("### 📌 Indicadores de Desempenho da Frota")

col1, col2, col3, col4 = st.columns(4)
col5, col6, col7, col8 = st.columns(4)

total_spend = df_filtered['VALOR EMISSAO'].sum()
total_liters = df_filtered['LITROS'].sum()
total_km = df_filtered[df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM']['KM RODADOS OU HORAS TRABALHADAS'].sum()

# Accurate general average consumption calculation for Diesel
diesel_filtered = df_filtered[(df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & (df_filtered['LITROS'] > 0)]
diesel_liters_total = diesel_filtered['LITROS'].sum()
general_avg_km_l = total_km / diesel_liters_total if diesel_liters_total > 0 else 0.0

# General cost per kilometer
general_cost_km = total_spend / total_km if total_km > 0 else 0.0

# Counts
num_vehicles = df_filtered['PLACA'].nunique()
num_drivers = df_filtered['NOME MOTORISTA'].nunique()
num_transactions = len(df_filtered)

with col1:
    st.metric("Gasto Total Acumulado", f"R$ {total_spend:,.2f}")
with col2:
    st.metric("Volume Total Abastecido", f"{total_liters:,.2f} L")
with col3:
    st.metric("Distância Total Rodada", f"{total_km:,.0f} km" if total_km > 0 else "N/A")
with col4:
    st.metric("Consumo Médio Geral", f"{general_avg_km_l:.2f} km/L" if general_avg_km_l > 0 else "N/A", help="Média geral ponderada de Diesel")

with col5:
    st.metric("Qtd. Veículos Ativos", f"{num_vehicles} veículos")
with col6:
    st.metric("Qtd. Motoristas Ativos", f"{num_drivers} motoristas")
with col7:
    st.metric("Total Abastecimentos", f"{num_transactions} transações")
with col8:
    st.metric("Custo Médio por KM", f"R$ {general_cost_km:.2f}/km" if general_cost_km > 0 else "N/A", help="Gasto total dividido pela quilometragem total rodada")

st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)

# Sorting fortnights correctly for all charts
all_quinzenas = sorted(df_filtered['QUINZENA'].unique(), key=get_fortnight_sort_key)

# --- APP TABS ---
tab_oper, tab_efet, tab_mot, tab_est_pos, tab_audit = st.tabs([
    "📈 Desempenho Operacional (Quinzenal)",
    "🚚 Eficiência & Categoria (Master vs Delivery)",
    "👨🏻‍✈️ Análise de Motoristas",
    "🌍 Distribuição Geográfica & Postos",
    "🔍 Auditoria & Base de Dados"
])

# -----------------------------------------------------------------------------
# TAB 1: DESEMPENHO OPERACIONAL QUINZENAL
# -----------------------------------------------------------------------------
with tab_oper:
    st.subheader("📊 Análise de Custos e Consumo Quinzenal")
    
    # Aggregation by fortnight
    fq_summary = df_filtered.groupby('QUINZENA')[['VALOR EMISSAO', 'LITROS']].sum().reindex(all_quinzenas).reset_index()
    
    # Plotly Double Y-Axis Chart (Bar vs Line)
    fig_fq_dual = go.Figure()
    
    # Bar for spend
    fig_fq_dual.add_trace(go.Bar(
        x=fq_summary['QUINZENA'],
        y=fq_summary['VALOR EMISSAO'],
        name="Valor Gasto (R$)",
        marker_color="#0f172a",
        text=fq_summary['VALOR EMISSAO'].apply(lambda x: f"R$ {x:,.2f}"),
        textposition="auto",
        yaxis="y1"
    ))
    
    # Line for liters
    fig_fq_dual.add_trace(go.Scatter(
        x=fq_summary['QUINZENA'],
        y=fq_summary['LITROS'],
        name="Volume Consumido (L)",
        mode="lines+markers+text",
        line=dict(color="#3b82f6", width=4),
        marker=dict(size=10),
        text=fq_summary['LITROS'].apply(lambda x: f"{x:,.0f} L"),
        textposition="top center",
        yaxis="y2"
    ))
    
    fig_fq_dual.update_layout(
        title="Comparativo de Custos Totais vs. Volume Consumido por Quinzena",
        xaxis=dict(title="Quinzena"),
        yaxis=dict(title="Valor Gasto (R$)", titlefont=dict(color="#0f172a"), tickfont=dict(color="#0f172a")),
        yaxis2=dict(title="Volume (Litros)", titlefont=dict(color="#3b82f6"), tickfont=dict(color="#3b82f6"), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255, 255, 255, 0.7)"),
        margin=dict(l=40, r=40, t=60, b=40),
        height=500
    )
    st.plotly_chart(fig_fq_dual, use_container_width=True)
    
    # Table comparison of fortnights
    st.markdown("#### 🗒️ Resumo das Métricas por Quinzena")
    fq_table_data = df_filtered.groupby('QUINZENA').agg(
        gasto_total=('VALOR EMISSAO', 'sum'),
        litros_totais=('LITROS', 'sum'),
        abastecimentos=('VALOR EMISSAO', 'count')
    ).reindex(all_quinzenas).reset_index()
    
    # Calculate Km for Diesel per fortnight
    diesel_fq_km = df_filtered[df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM'].groupby('QUINZENA')['KM RODADOS OU HORAS TRABALHADAS'].sum().reindex(all_quinzenas)
    fq_table_data['km_rodados'] = fq_table_data['QUINZENA'].map(diesel_fq_km).fillna(0)
    fq_table_data['consumo_medio'] = np.where(fq_table_data['litros_totais'] > 0, fq_table_data['km_rodados'] / fq_table_data['litros_totais'], 0.0)
    
    st.dataframe(
        fq_table_data,
        column_config={
            "QUINZENA": "Quinzena",
            "gasto_total": st.column_config.NumberColumn("Valor Total", format="R$ %,.2f"),
            "litros_totais": st.column_config.NumberColumn("Litros Totais", format="%,.2f L"),
            "abastecimentos": st.column_config.NumberColumn("Abastecimentos", format="%d"),
            "km_rodados": st.column_config.NumberColumn("Distância Rodada", format="%,.0f km"),
            "consumo_medio": st.column_config.NumberColumn("Consumo Médio", format="%.2f km/L")
        },
        hide_index=True,
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# TAB 2: EFICIÊNCIA & CATEGORIA (MASTER VS DELIVERY)
# -----------------------------------------------------------------------------
with tab_efet:
    st.subheader("🚚 Eficiência de Combustível por Placa e Categoria")
    
    col_ef1, col_ef2 = st.columns(2)
    
    # Filtering for actual fuel efficiencies (excluding obvious outliers like Arla entries or typos)
    df_diesel_eff = df_filtered[
        (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_filtered['KM/LITRO OU LITROS/HORA'] > 0) & 
        (df_filtered['KM/LITRO OU LITROS/HORA'] < 30)
    ]
    
    with col_ef1:
        st.markdown("#### Consumo Médio (km/L) por Veículo")
        if not df_diesel_eff.empty:
            avg_plate_eff = df_diesel_eff.groupby(['PLACA', 'CATEGORIA'])['KM/LITRO OU LITROS/HORA'].mean().reset_index()
            avg_plate_eff = avg_plate_eff.sort_values(by='KM/LITRO OU LITROS/HORA', ascending=False)
            
            fig_eff = px.bar(
                avg_plate_eff,
                x='PLACA',
                y='KM/LITRO OU LITROS/HORA',
                color='CATEGORIA',
                labels={'KM/LITRO OU LITROS/HORA': 'Autonomia Média (km/L)', 'PLACA': 'Placa', 'CATEGORIA': 'Categoria'},
                color_discrete_map={'Master': '#22c55e', 'Delivery': '#3b82f6'},
                text_auto='.2f',
                title='Comparativo de Consumo de Diesel por Placa'
            )
            fig_eff.update_layout(xaxis={'categoryorder': 'total descending'})
            st.plotly_chart(fig_eff, use_container_width=True)
        else:
            st.info("Nenhum dado de Diesel (km/L) elegível para exibição gráfica.")
            
    with col_ef2:
        st.markdown("#### Custo Operacional por Quilômetro (R$/km)")
        # Filter where distance is recorded
        df_km_cost = df_filtered[
            (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            (df_filtered['KM RODADOS OU HORAS TRABALHADAS'] > 0)
        ]
        if not df_km_cost.empty:
            plate_km_cost = df_km_cost.groupby(['PLACA', 'CATEGORIA']).apply(
                lambda x: x['VALOR EMISSAO'].sum() / x['KM RODADOS OU HORAS TRABALHADAS'].sum()
            ).reset_index(name='R_KM')
            plate_km_cost = plate_km_cost.sort_values(by='R_KM', ascending=True)
            
            fig_km = px.bar(
                plate_km_cost,
                x='PLACA',
                y='R_KM',
                color='CATEGORIA',
                labels={'R_KM': 'Custo Real (R$/km)', 'PLACA': 'Placa', 'CATEGORIA': 'Categoria'},
                color_discrete_map={'Master': '#22c55e', 'Delivery': '#3b82f6'},
                text_auto='R$ .2f',
                title='Custo Financeiro por KM Rodado'
            )
            st.plotly_chart(fig_km, use_container_width=True)
        else:
            st.info("Dados de quilometragem indisponíveis para cálculo de R$/km.")

    st.markdown("#### 🔍 Comparativo Direto por Categoria (Médias)")
    if not df_diesel_eff.empty:
        cat_metrics = df_diesel_eff.groupby('CATEGORIA').agg(
            consumo_medio=('KM/LITRO OU LITROS/HORA', 'mean'),
            abastecimentos=('VALOR EMISSAO', 'count'),
            valor_medio_abast=('VALOR EMISSAO', 'mean')
        ).reset_index()
        
        st.dataframe(
            cat_metrics,
            column_config={
                "CATEGORIA": "Categoria",
                "consumo_medio": st.column_config.NumberColumn("Consumo Médio", format="%.2f km/L"),
                "abastecimentos": st.column_config.NumberColumn("Total Abastecimentos", format="%d"),
                "valor_medio_abast": st.column_config.NumberColumn("Valor Médio / Refuel", format="R$ %,.2f")
            },
            hide_index=True,
            use_container_width=True
        )

# -----------------------------------------------------------------------------
# TAB 3: ANÁLISE DE MOTORISTAS
# -----------------------------------------------------------------------------
with tab_mot:
    st.subheader("👨🏻‍✈️ Performance e Faturamento por Motorista (Visão Quinzenal)")
    
    col_m1, col_m2 = st.columns(2)
    
    # Spend by driver per fortnight
    driver_spend_fq = df_filtered.groupby(['NOME MOTORISTA', 'QUINZENA'])['VALOR EMISSAO'].sum().reset_index()
    driver_spend_fq = driver_spend_fq[driver_spend_fq['QUINZENA'].isin(all_quinzenas)]
    
    # Refuelings counts by driver per fortnight
    driver_count_fq = df_filtered.groupby(['NOME MOTORISTA', 'QUINZENA']).size().reset_index(name='CONTAGEM')
    driver_count_fq = driver_count_fq[driver_count_fq['QUINZENA'].isin(all_quinzenas)]
    
    with col_m1:
        st.markdown("#### Valor Total Abastecido por Motorista (R$)")
        fig_driver_spend = px.bar(
            driver_spend_fq,
            y='NOME MOTORISTA',
            x='VALOR EMISSAO',
            color='QUINZENA',
            barmode='group',
            orientation='h',
            labels={'VALOR EMISSAO': 'Gasto Total (R$)', 'NOME MOTORISTA': 'Motorista', 'QUINZENA': 'Quinzena'},
            color_discrete_sequence=px.colors.qualitative.Prism,
            title='Gastos Totais de Abastecimento por Quinzena'
        )
        fig_driver_spend.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_driver_spend, use_container_width=True)
        
    with col_m2:
        st.markdown("#### Quantidade de Abastecimentos por Motorista")
        fig_driver_cnt = px.bar(
            driver_count_fq,
            y='NOME MOTORISTA',
            x='CONTAGEM',
            color='QUINZENA',
            barmode='group',
            orientation='h',
            labels={'CONTAGEM': 'Quantidade de Abastecimentos', 'NOME MOTORISTA': 'Motorista', 'QUINZENA': 'Quinzena'},
            color_discrete_sequence=px.colors.qualitative.Prism,
            title='Número de Transações de Abastecimento por Quinzena'
        )
        fig_driver_cnt.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_driver_cnt, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 4: DISTRIBUIÇÃO GEOGRÁFICA & POSTOS
# -----------------------------------------------------------------------------
with tab_est_pos:
    st.subheader("🌍 Consolidação de Consumo por Região (UF) e Estabelecimento")
    
    col_eg1, col_eg2 = st.columns(2)
    
    with col_eg1:
        st.markdown("#### Comparativo de Abastecimentos por Estado (UF)")
        state_summary = df_filtered.groupby('UF').agg(
            gasto_total=('VALOR EMISSAO', 'sum'),
            litros_totais=('LITROS', 'sum'),
            quantidade=('VALOR EMISSAO', 'count')
        ).reset_index()
        
        fig_state = px.bar(
            state_summary,
            x='UF',
            y='gasto_total',
            color='UF',
            labels={'gasto_total': 'Gasto Total (R$)', 'UF': 'Estado'},
            text_auto='R$ .2f',
            title='Faturamento Acumulado de Abastecimento por UF'
        )
        st.plotly_chart(fig_state, use_container_width=True)
        
    with col_eg2:
        st.markdown("#### Principais Postos de Combustível Utilizados (Top 10)")
        station_summary = df_filtered.groupby('NOME ESTABELECIMENTO').agg(
            gasto_total=('VALOR EMISSAO', 'sum'),
            quantidade=('VALOR EMISSAO', 'count')
        ).reset_index().sort_values(by='quantidade', ascending=False).head(10)
        
        fig_station = px.bar(
            station_summary,
            x='quantidade',
            y='NOME ESTABELECIMENTO',
            orientation='h',
            labels={'quantidade': 'Qtd. Abastecimentos', 'NOME ESTABELECIMENTO': 'Posto de Combustível'},
            text_auto=True,
            title='Frequência de Abastecimento por Posto (Top 10)',
            color_discrete_sequence=['#475569']
        )
        fig_station.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_station, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 5: AUDITORIA & BASE DE DADOS
# -----------------------------------------------------------------------------
with tab_audit:
    st.subheader("🔍 Auditoria de Consumos & Base de Dados Filtrada")
    
    col_aud1, col_aud2 = st.columns(2)
    
    with col_aud1:
        # Detect refuelings with 0 distance (Anomalies)
        anomalies_zero_km = df_filtered[
            (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            (df_filtered['KM RODADOS OU HORAS TRABALHADAS'] == 0)
        ]
        if not anomalies_zero_km.empty:
            st.warning(f"🚨 Alerta: Identificados **{len(anomalies_zero_km)}** abastecimentos de Diesel com KM rodada zerada!")
            st.dataframe(
                anomalies_zero_km[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'LITROS', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']],
                use_container_width=True
            )
        else:
            st.success("✅ Parabéns! Não foram encontrados registros de Diesel com KM rodada zerada nos filtros atuais.")
            
    with col_aud2:
        # Detect refuelings with suspicious efficiency (very high or low km/L)
        anomalies_eff = df_filtered[
            (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            ((df_filtered['KM/LITRO OU LITROS/HORA'] < 4) | (df_filtered['KM/LITRO OU LITROS/HORA'] > 18)) &
            (df_filtered['KM/LITRO OU LITROS/HORA'] != 0)
        ]
        if not anomalies_eff.empty:
            st.error(f"⚠️ Alerta: Identificados **{len(anomalies_eff)}** abastecimentos com rendimento atípico (< 4 km/L ou > 18 km/L)!")
            st.dataframe(
                anomalies_eff[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'KM/LITRO OU LITROS/HORA', 'LITROS', 'VALOR EMISSAO']],
                use_container_width=True
            )
        else:
            st.success("✅ Não foram encontrados consumos atípicos (< 4 km/L ou > 18 km/L) no período selecionado.")

    st.markdown("#### 📂 Tabela de Dados Completa")
    display_cols = [
        'DATA TRANSACAO', 'PLACA', 'CATEGORIA', 'NOME MOTORISTA', 'TIPO COMBUSTIVEL',
        'LITROS', 'VL/LITRO', 'KM RODADOS OU HORAS TRABALHADAS',
        'KM/LITRO OU LITROS/HORA', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO', 'UF'
    ]
    display_cols = [col for col in display_cols if col in df_filtered.columns]
    
    st.dataframe(
        df_filtered[display_cols].sort_values(by='DATA TRANSACAO', ascending=False),
        use_container_width=True,
        column_config={
            "VALOR EMISSAO": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
            "VL/LITRO": st.column_config.NumberColumn("Preço/Litro", format="R$ %.3f"),
            "LITROS": st.column_config.NumberColumn("Litros", format="%.2f L"),
            "KM RODADOS OU HORAS TRABALHADAS": st.column_config.NumberColumn("KM Rodados", format="%.0f km"),
            "KM/LITRO OU LITROS/HORA": st.column_config.NumberColumn("Consumo", format="%.2f km/L"),
        }
    )

    # Export buffer
    csv_buffer = df_filtered.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        label="📥 Exportar Base de Dados Filtrada (CSV)",
        data=csv_buffer,
        file_name="historico_combustivel_auditoria.csv",
        mime="text/csv"
    )
