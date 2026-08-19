import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# --- PAGE CONFIGURATION & THEME ---
st.set_page_config(
    page_title="ANJUN - Gestão Inteligente de Combustível",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Inspirado no Power BI com Cores Claras e Harmônicas da ANJUN)
st.markdown("""
<style>
    /* Estilo Geral */
    .main {
        background-color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    /* Cabeçalho do Aplicativo */
    .app-header {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 25px;
        border-left: 6px solid #009a53;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    /* Cartões de Métricas (Power BI Look) */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #009a53 !important; /* Cor Verde Anjun */
        padding: 15px 20px !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 4px 0 rgba(0, 0, 0, 0.02) !important;
        transition: all 0.2s ease-in-out !important;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08) !important;
        border-color: #cbd5e1 !important;
    }
    
    /* Botões personalizados */
    .stButton>button {
        background-color: #009a53 !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
    }
    .stButton>button:hover {
        background-color: #007a41 !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important;
    }
    
    /* Estilo de Abas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        color: #475569;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #009a53 !important;
        color: #ffffff !important;
        box-shadow: 0 2px 4px 0 rgba(0, 0, 0, 0.05);
    }
    
    /* Caixa de Dica Interativa */
    .hint-box {
        background-color: #f0fdf4;
        border-left: 4px solid #16a34a;
        color: #166534;
        padding: 12px;
        border-radius: 6px;
        font-size: 14px;
        margin-bottom: 15px;
    }
    
    /* Detalhamento de Seleção */
    .detail-box {
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        color: #1e40af;
        padding: 12px;
        border-radius: 6px;
        font-size: 14px;
        margin-bottom: 15px;
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
            1: 'Jul', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
        }
        # Force month names to match available months in the data cleanly
        m_name = months_br.get(dt.month, dt.strftime('%b'))
        year_short = dt.strftime('%y')
        return f"{half} {m_name}/{year_short}"

    df['QUINZENA'] = df.apply(get_fortnight, axis=1)
    df['CATEGORIA'] = df['MODELO VEICULO'].map({'MASTER': 'Master', 'EXPRESS': 'Delivery'}).fillna('Outros')
    df['CUSTO_KM'] = np.where(df['KM RODADOS OU HORAS TRABALHADAS'] > 0, df['VALOR EMISSAO'] / df['KM RODADOS OU HORAS TRABALHADAS'], 0.0)
    
    return df

# --- LOGO & HEADER WITH BRAND COLORS ---
logo_path = 'logo Anjun.png'
col_logo, col_title = st.columns([2, 10])

with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    elif os.path.exists('/workspace/knowledge/logo Anjun.png'):
        st.image('/workspace/knowledge/logo Anjun.png', use_container_width=True)
    else:
        # Beautiful fallback logo rendered with CSS matching Anjun identity
        st.markdown("""
        <div style="font-family:'Inter', sans-serif; font-size:38px; font-weight:800; color:#009a53; line-height:1.2; position:relative; letter-spacing:-1px; padding: 10px 0;">
            <span>A</span><span style="position:relative; border-bottom: 4px solid #009a53; padding-bottom:2px;">n<span style="color:#dc2626; position:absolute; top:-10px; left:16px; font-size:24px; line-height:1;">•</span>j</span><span>u</span><span>n</span>
            <span style="font-size:10px; font-weight:normal; color:#64748b; vertical-align:super; margin-left:2px;">®</span>
        </div>
        """, unsafe_allow_html=True)

with col_title:
    st.markdown("""
    <div style="padding-top: 10px;">
        <h1 style="margin:0; font-size: 28px; color: #0f172a;">Painel de Controle — Indicador de Combustível</h1>
        <p style="margin:0; color: #64748b; font-size:15px;">Acompanhamento Estratégico de Performance, Custos e Auditoria de Frota</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin: 10px 0 25px 0; border:0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

# --- LOADING THE DATASET ---
uploaded_file = st.sidebar.file_uploader("📥 Enviar nova planilha (.csv)", type=["csv"])

df_raw = None
if uploaded_file is not None:
    df_raw = load_and_clean_data(uploaded_file)
    st.sidebar.success("Nova planilha carregada!")
else:
    default_paths = ['Historico_de_abastecimento.csv', '/workspace/knowledge/Historico_de_abastecimento.csv']
    for p in default_paths:
        if os.path.exists(p):
            df_raw = load_and_clean_data(p)
            break
            
if df_raw is None:
    st.warning("⚠️ Por favor, envie o arquivo 'Historico_de_abastecimento.csv' no painel à esquerda ou use o uploader do menu lateral.")
    st.stop()

# --- SIDEBAR ADVANCED FILTERS ---
st.sidebar.markdown("### 🔍 Filtros de Análise")

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
selected_plates = st.sidebar.multiselect("Placas dos Veículos", options=plates, default=plates)

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
    "Faixa de Valor de Transação (R$)",
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
    st.error("❌ Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

# --- METRIC CARDS ---
total_spend = df_filtered['VALOR EMISSAO'].sum()
total_liters = df_filtered['LITROS'].sum()
total_km = df_filtered[df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM']['KM RODADOS OU HORAS TRABALHADAS'].sum()

# Consumption General Diesel
diesel_filtered = df_filtered[(df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & (df_filtered['LITROS'] > 0)]
diesel_liters_total = diesel_filtered['LITROS'].sum()
general_avg_km_l = total_km / diesel_liters_total if diesel_liters_total > 0 else 0.0

general_cost_km = total_spend / total_km if total_km > 0 else 0.0
num_vehicles = df_filtered['PLACA'].nunique()
num_drivers = df_filtered['NOME MOTORISTA'].nunique()
num_transactions = len(df_filtered)

st.markdown("### 📊 Indicadores Consolidados")
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

with col1:
    st.metric("Gasto Total", f"R$ {total_spend:,.2f}")
with col2:
    st.metric("Litros Totais", f"{total_liters:,.1f} L")
with col3:
    st.metric("Distância Rodada", f"{total_km:,.0f} km")
with col4:
    st.metric("Média Geral", f"{general_avg_km_l:.2f} km/L")
with col5:
    st.metric("Custo/KM Médio", f"R$ {general_cost_km:.2f}/km" if general_cost_km > 0 else "N/A")
with col6:
    st.metric("Veículos Ativos", f"{num_vehicles}")
with col7:
    st.metric("Motoristas Ativos", f"{num_drivers}")

st.markdown("<br>", unsafe_allow_html=True)

# Sorting fortnights correctly for all charts
all_quinzenas = sorted(df_filtered['QUINZENA'].unique(), key=get_fortnight_sort_key)

# --- APP TABS ---
tab_oper, tab_efet, tab_mot, tab_est_pos, tab_audit = st.tabs([
    "📈 Custos & Volumes Quinzenais",
    "🚚 Eficiência & Desempenho de Veículos",
    "👨🏻‍✈️ Performance de Motoristas",
    "🌍 Regiões & Postos",
    "🔍 Auditoria & Dados"
])

# -----------------------------------------------------------------------------
# TAB 1: CUSTOS E VOLUMES QUINZENAIS (DYNAMIC INTERACTIVE)
# -----------------------------------------------------------------------------
with tab_oper:
    st.subheader("📊 Relatório de Custos e Consumo Quinzenal")
    
    # Aggregation by fortnight
    fq_summary = df_filtered.groupby('QUINZENA')[['VALOR EMISSAO', 'LITROS']].sum().reindex(all_quinzenas).reset_index()
    
    # Plotly Double Y-Axis Chart (Bar vs Line)
    fig_fq_dual = go.Figure()
    
    # Bar for spend
    fig_fq_dual.add_trace(go.Bar(
        x=fq_summary['QUINZENA'],
        y=fq_summary['VALOR EMISSAO'],
        name="Valor Gasto (R$)",
        marker_color="#009a53", # Verde Anjun
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
        line=dict(color="#dc2626", width=4), # Vermelho Anjun
        marker=dict(size=10, color="#dc2626"),
        text=fq_summary['LITROS'].apply(lambda x: f"{x:,.0f} L"),
        textposition="top center",
        yaxis="y2"
    ))
    
    fig_fq_dual.update_layout(
        title=dict(text="Comparativo Quinzenal: Investimento Financeiro vs Volume (Litros)", font=dict(size=16, color="#1e293b", family="Inter")),
        xaxis=dict(title="Quinzena"),
        yaxis=dict(title=dict(text="Valor Gasto (R$)", font=dict(color="#009a53")), tickfont=dict(color="#009a53")),
        yaxis2=dict(title=dict(text="Volume (Litros)", font=dict(color="#dc2626")), tickfont=dict(color="#dc2626"), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255, 255, 255, 0.8)"),
        margin=dict(l=40, r=40, t=60, b=40),
        height=450,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff"
    )
    
    # Streamlit Interactive Selection (on_select="rerun" available in modern Streamlit)
    st.markdown('<div class="hint-box">💡 <b>Dica Interativa (Como no Power BI):</b> Clique em uma das barras do gráfico acima para ver as transações detalhadas daquela quinzena!</div>', unsafe_allow_html=True)
    
    selected_fq = st.plotly_chart(fig_fq_dual, use_container_width=True, on_select="rerun", key="fq_chart_select")
    
    # Interactive filtering based on click
    clicked_fq = None
    if selected_fq and "selection" in selected_fq and "points" in selected_fq["selection"] and selected_fq["selection"]["points"]:
        clicked_fq = selected_fq["selection"]["points"][0].get("x")
        
    if clicked_fq:
        st.markdown(f'<div class="detail-box">🔍 <b>Filtro Ativo:</b> Exibindo transações detalhadas da <b>{clicked_fq}</b>. Clique fora das barras para limpar o filtro.</div>', unsafe_allow_html=True)
        df_show = df_filtered[df_filtered['QUINZENA'] == clicked_fq]
    else:
        df_show = df_filtered

    st.markdown("#### Detalhamento das Transações")
    st.dataframe(
        df_show[['DATA TRANSACAO', 'PLACA', 'CATEGORIA', 'NOME MOTORISTA', 'TIPO COMBUSTIVEL', 'LITROS', 'VL/LITRO', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']].sort_values(by='DATA TRANSACAO', ascending=False),
        use_container_width=True,
        column_config={
            "VALOR EMISSAO": st.column_config.NumberColumn("Valor Gasto", format="R$ %.2f"),
            "VL/LITRO": st.column_config.NumberColumn("Preço/Litro", format="R$ %.3f"),
            "LITROS": st.column_config.NumberColumn("Litros", format="%.2f L")
        },
        hide_index=True
    )

# -----------------------------------------------------------------------------
# TAB 2: EFICIÊNCIA DE VEÍCULOS (WITH DYNAMIC Drill-Down + Quinzena KM & Odometer)
# -----------------------------------------------------------------------------
with tab_efet:
    st.subheader("🚚 Eficiência Operacional e Desempenho Físico")
    
    # Calculating metrics per vehicle & fortnight as requested
    st.markdown("#### 🗒️ Desempenho de Quilometragem e Hodômetro por Quinzena")
    
    df_diesel_only = df_filtered[df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM']
    vehicle_fq_metrics = df_filtered.groupby(['PLACA', 'CATEGORIA', 'QUINZENA']).agg(
        km_rodados=('KM RODADOS OU HORAS TRABALHADAS', 'sum'),
        hodometro_atual=('HODOMETRO OU HORIMETRO', 'max'),
        litros=('LITROS', 'sum'),
        gasto=('VALOR EMISSAO', 'sum')
    ).reset_index()
    
    vehicle_fq_metrics['consumo_medio'] = np.where(
        vehicle_fq_metrics['litros'] > 0, 
        vehicle_fq_metrics['km_rodados'] / vehicle_fq_metrics['litros'], 
        0.0
    )
    
    st.dataframe(
        vehicle_fq_metrics.sort_values(by=['QUINZENA', 'PLACA'], key=lambda x: x.map(get_fortnight_sort_key) if x.name == 'QUINZENA' else x),
        column_config={
            "PLACA": "Placa do Veículo",
            "CATEGORIA": "Categoria",
            "QUINZENA": "Quinzena",
            "km_rodados": st.column_config.NumberColumn("KM Rodados na Quinzena", format="%,.0f km"),
            "hodometro_atual": st.column_config.NumberColumn("Hodômetro Atual (Max)", format="%,.0f km"),
            "litros": st.column_config.NumberColumn("Volume (L)", format="%.1f L"),
            "gasto": st.column_config.NumberColumn("Gasto Total (R$)", format="R$ %,.2f"),
            "consumo_medio": st.column_config.NumberColumn("Autonomia Média", format="%.2f km/L")
        },
        hide_index=True,
        use_container_width=True
    )
    
    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
    
    # Charts Section
    col_ef1, col_ef2 = st.columns(2)
    
    df_diesel_eff = df_filtered[
        (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_filtered['KM/LITRO OU LITROS/HORA'] > 0) & 
        (df_filtered['KM/LITRO OU LITROS/HORA'] < 30)
    ]
    
    with col_ef1:
        st.markdown("#### Autonomia Média (km/L) por Veículo")
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
                title='Comparativo de Consumo por Placa (Clique para Detalhar)'
            )
            fig_eff.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
            
            st.markdown('<div class="hint-box">💡 Clique em qualquer barra do gráfico para carregar a "Ficha de Abastecimentos" deste veículo abaixo!</div>', unsafe_allow_html=True)
            selected_plate_data = st.plotly_chart(fig_eff, use_container_width=True, on_select="rerun", key="plate_chart_select")
        else:
            st.info("Nenhum dado de Diesel (km/L) disponível para a plotagem do gráfico.")
            selected_plate_data = None
            
    with col_ef2:
        st.markdown("#### Custo Operacional por Quilômetro (R$/km)")
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
                title='Custo Financeiro de Rodagem (R$ por KM)'
            )
            fig_km.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
            st.plotly_chart(fig_km, use_container_width=True)
        else:
            st.info("Quilometragem indisponível para cálculo de custo/km.")

    # Vehicle Dynamic Drill-down
    clicked_plate = None
    if selected_plate_data and "selection" in selected_plate_data and "points" in selected_plate_data["selection"] and selected_plate_data["selection"]["points"]:
        clicked_plate = selected_plate_data["selection"]["points"][0].get("x")
        
    if clicked_plate:
        st.markdown(f'<div class="detail-box">🔍 <b>Ficha Técnica Ativa:</b> Mostrando histórico do veículo <b>{clicked_plate}</b></div>', unsafe_allow_html=True)
        df_plate_details = df_filtered[df_filtered['PLACA'] == clicked_plate]
        
        # Display specific metrics for this clicked vehicle
        det_col1, det_col2, det_col3, det_col4 = st.columns(4)
        v_total_spend = df_plate_details['VALOR EMISSAO'].sum()
        v_total_liters = df_plate_details['LITROS'].sum()
        v_total_km = df_plate_details['KM RODADOS OU HORAS TRABALHADAS'].sum()
        v_max_odo = df_plate_details['HODOMETRO OU HORIMETRO'].max()
        
        with det_col1:
            st.metric("Gasto Acumulado", f"R$ {v_total_spend:,.2f}")
        with det_col2:
            st.metric("Total Litros", f"{v_total_liters:,.2f} L")
        with det_col3:
            st.metric("Km Rodados no Período", f"{v_total_km:,.0f} km")
        with det_col4:
            st.metric("Último Hodômetro", f"{v_max_odo:,.0f} km")
            
        st.dataframe(
            df_plate_details[['DATA TRANSACAO', 'QUINZENA', 'NOME MOTORISTA', 'LITROS', 'VL/LITRO', 'KM RODADOS OU HORAS TRABALHADAS', 'KM/LITRO OU LITROS/HORA', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']],
            use_container_width=True,
            column_config={
                "VALOR EMISSAO": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "LITROS": st.column_config.NumberColumn("Litros", format="%.2f L"),
                "KM/LITRO OU LITROS/HORA": st.column_config.NumberColumn("Consumo", format="%.2f km/L"),
                "KM RODADOS OU HORAS TRABALHADAS": "KM Rodados",
                "VL/LITRO": "Preço/L"
            },
            hide_index=True
        )

# -----------------------------------------------------------------------------
# TAB 3: ANÁLISE DE MOTORISTAS (INTERACTIVE Drill-Down)
# -----------------------------------------------------------------------------
with tab_mot:
    st.subheader("👨🏻‍✈️ Performance e Faturamento dos Motoristas")
    
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
            color_discrete_sequence=['#009a53', '#dc2626', '#64748b'],
            title='Gastos Acumulados de Abastecimento por Quinzena (Clique na barra)'
        )
        fig_driver_spend.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
        st.markdown('<div class="hint-box">💡 Clique em qualquer barra de motorista para analisar sua ficha técnica completa de condução abaixo!</div>', unsafe_allow_html=True)
        selected_driver_data = st.plotly_chart(fig_driver_spend, use_container_width=True, on_select="rerun", key="driver_chart_select")
        
    with col_m2:
        st.markdown("#### Quantidade de Abastecimentos")
        fig_driver_cnt = px.bar(
            driver_count_fq,
            y='NOME MOTORISTA',
            x='CONTAGEM',
            color='QUINZENA',
            barmode='group',
            orientation='h',
            labels={'CONTAGEM': 'Qtd Abastecimentos', 'NOME MOTORISTA': 'Motorista', 'QUINZENA': 'Quinzena'},
            color_discrete_sequence=['#009a53', '#dc2626', '#64748b'],
            title='Número de Abastecimentos Efetuados por Quinzena'
        )
        fig_driver_cnt.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
        st.plotly_chart(fig_driver_cnt, use_container_width=True)

    # Driver Drill-down Selection
    clicked_driver = None
    if selected_driver_data and "selection" in selected_driver_data and "points" in selected_driver_data["selection"] and selected_driver_data["selection"]["points"]:
        clicked_driver = selected_driver_data["selection"]["points"][0].get("y")
        
    if clicked_driver:
        st.markdown(f'<div class="detail-box">🔍 <b>Ficha Operacional Ativa:</b> Mostrando histórico de <b>{clicked_driver}</b></div>', unsafe_allow_html=True)
        df_driver_details = df_filtered[df_filtered['NOME MOTORISTA'] == clicked_driver]
        
        # Display driver specific metrics
        dm1, dm2, dm3, dm4 = st.columns(4)
        m_total_spend = df_driver_details['VALOR EMISSAO'].sum()
        m_total_liters = df_driver_details['LITROS'].sum()
        m_total_abast = len(df_driver_details)
        m_avg_consumption = df_driver_details[df_driver_details['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM']['KM/LITRO OU LITROS/HORA'].mean()
        
        with dm1:
            st.metric("Total Gasto", f"R$ {m_total_spend:,.2f}")
        with dm2:
            st.metric("Total Litros", f"{m_total_liters:,.2f} L")
        with dm3:
            st.metric("Total Abastecimentos", f"{m_total_abast} transações")
        with dm4:
            st.metric("Consumo Médio Praticado", f"{m_avg_consumption:.2f} km/L" if m_avg_consumption > 0 else "N/A")
            
        st.dataframe(
            df_driver_details[['DATA TRANSACAO', 'QUINZENA', 'PLACA', 'CATEGORIA', 'TIPO COMBUSTIVEL', 'LITROS', 'VL/LITRO', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']],
            use_container_width=True,
            column_config={
                "VALOR EMISSAO": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "LITROS": st.column_config.NumberColumn("Litros", format="%.2f L"),
                "VL/LITRO": "Preço/L"
            },
            hide_index=True
        )

# -----------------------------------------------------------------------------
# TAB 4: REGIÕES & POSTOS
# -----------------------------------------------------------------------------
with tab_est_pos:
    st.subheader("🌍 Consolidação Territorial e Rede de Postos Credenciados")
    
    col_eg1, col_eg2 = st.columns(2)
    
    with col_eg1:
        st.markdown("#### Investimento de Abastecimento por Estado (UF)")
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
            color_discrete_sequence=['#009a53', '#dc2626', '#64748b'],
            text_auto='R$ .2f',
            title='Faturamento Acumulado de Abastecimento por UF'
        )
        fig_state.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
        st.plotly_chart(fig_state, use_container_width=True)
        
    with col_eg2:
        st.markdown("#### Frequência de Utilização de Postos de Combustível")
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
            title='Postos Mais Utilizados (Top 10)',
            color_discrete_sequence=['#009a53'] # Verde Anjun
        )
        fig_station.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
        st.plotly_chart(fig_station, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 5: AUDITORIA & DADOS
# -----------------------------------------------------------------------------
with tab_audit:
    st.subheader("🔍 Auditoria de Inconsistências e Tabela Base")
    
    col_aud1, col_aud2 = st.columns(2)
    
    with col_aud1:
        anomalies_zero_km = df_filtered[
            (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            (df_filtered['KM RODADOS OU HORAS TRABALHADAS'] == 0)
        ]
        if not anomalies_zero_km.empty:
            st.warning(f"🚨 Alerta: Identificados **{len(anomalies_zero_km)}** abastecimentos de Diesel com KM rodada zerada!")
            st.dataframe(
                anomalies_zero_km[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'LITROS', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ Nenhum registro de Diesel com KM rodada zerada foi encontrado.")
            
    with col_aud2:
        anomalies_eff = df_filtered[
            (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            ((df_filtered['KM/LITRO OU LITROS/HORA'] < 4) | (df_filtered['KM/LITRO OU LITROS/HORA'] > 18)) &
            (df_filtered['KM/LITRO OU LITROS/HORA'] != 0)
        ]
        if not anomalies_eff.empty:
            st.error(f"⚠️ Alerta: Identificados **{len(anomalies_eff)}** abastecimentos com rendimento atípico (< 4 ou > 18 km/L)!")
            st.dataframe(
                anomalies_eff[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'KM/LITRO OU LITROS/HORA', 'LITROS', 'VALOR EMISSAO']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ Nenhum consumo atípico encontrado.")

    st.markdown("#### 📂 Tabela de Dados Geral")
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
        },
        hide_index=True
    )

    # Export buffer
    csv_buffer = df_filtered.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        label="📥 Exportar Base de Dados Filtrada (CSV)",
        data=csv_buffer,
        file_name="historico_combustivel_auditoria.csv",
        mime="text/csv"
    )
