import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import io
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# --- PAGE CONFIGURATION & THEME ---
st.set_page_config(
    page_title="ANJUN - Indicador de Combustível",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Inspirado no Power BI com Cores Claras e Harmônicas da ANJUN)
st.markdown("""
<style>
    /* Estilo Geral - Claro mas Não Branco (Cinza Azulado Suave) */
    .stApp {
        background-color: #f8fafc !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar background: light slate-100 */
    section[data-testid="stSidebar"] {
        background-color: #f1f5f9 !important;
        border-right: 1px solid #e2e8f0 !important;
    }
    
    /* Cabeçalho do Aplicativo */
    .app-header {
        background-color: #ffffff;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border-left: 6px solid #009a53;
    }
    
    /* Botões de Indicadores Consolidados (Estilo KPI Card como Botão) */
    div.stButton > button {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-left: 5px solid #009a53 !important; /* Cor Verde Anjun */
        padding: 10px 14px !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
        width: 100% !important;
        text-align: left !important;
        transition: all 0.2s ease-in-out !important;
        white-space: normal !important; /* Quebra de texto automática */
        word-wrap: break-word !important;
        height: auto !important;
        min-height: 85px !important;
    }
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08) !important;
        border-color: #009a53 !important;
        background-color: #f0fdf4 !important; /* Feedback verde claro ao passar o mouse */
    }
    
    /* Style tabs to look like professional corporate navigation */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 10px;
        margin-bottom: 15px;
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

# Helper to format numbers and currency in Brazilian Portuguese standard (e.g. 1.234,56)
def format_pt_br(val, decimals=2, is_currency=False):
    if val is None or pd.isna(val):
        return "R$ 0,00" if is_currency else "0"
    fmt = f"{{:,.{decimals}f}}"
    formatted = fmt.format(val)
    parts = formatted.split('.')
    if len(parts) == 2:
        integers = parts[0].replace(',', '.')
        dec = parts[1]
        result = f"{integers},{dec}"
    else:
        result = formatted.replace(',', '.')
    if is_currency:
        return f"R$ {result}"
    return result

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
        m_name = months_br.get(dt.month, dt.strftime('%b'))
        year_short = dt.strftime('%y')
        return f"{half} {m_name}/{year_short}"

    df['QUINZENA'] = df.apply(get_fortnight, axis=1)
    df['CATEGORIA'] = df['MODELO VEICULO'].map({'MASTER': 'Master', 'EXPRESS': 'Delivery'}).fillna('Outros')
    df['CUSTO_KM'] = np.where(df['KM RODADOS OU HORAS TRABALHADAS'] > 0, df['VALOR EMISSAO'] / df['KM RODADOS OU HORAS TRABALHADAS'], 0.0)
    
    return df

# --- INITIALIZE GLOBAL CROSS-FILTER SESSION STATES ---
if 'global_clicked_quinzena' not in st.session_state:
    st.session_state['global_clicked_quinzena'] = None
if 'global_clicked_placa' not in st.session_state:
    st.session_state['global_clicked_placa'] = None
if 'global_clicked_motorista' not in st.session_state:
    st.session_state['global_clicked_motorista'] = None
if 'global_clicked_estado' not in st.session_state:
    st.session_state['global_clicked_estado'] = None

# --- FIXED LOGO AT THE TOP OF THE SIDEBAR ---
logo_path = 'logo Anjun.png'
st.sidebar.markdown("<div style='text-align: center; padding-bottom: 15px;'>", unsafe_allow_html=True)
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, use_container_width=True)
elif os.path.exists('/workspace/knowledge/logo Anjun.png'):
    st.sidebar.image('/workspace/knowledge/logo Anjun.png', use_container_width=True)
else:
    # Fallback logo rendered with CSS matching Anjun identity
    st.sidebar.markdown("""
    <div style="font-family:'Inter', sans-serif; font-size:36px; font-weight:800; color:#009a53; line-height:1.2; position:relative; letter-spacing:-1px; padding: 10px 0; text-align: center;">
        <span>A</span><span style="position:relative; border-bottom: 4px solid #009a53; padding-bottom:2px;">n<span style="color:#dc2626; position:absolute; top:-10px; left:16px; font-size:24px; line-height:1;">•</span>j</span><span>u</span><span>n</span>
        <span style="font-size:10px; font-weight:normal; color:#64748b; vertical-align:super; margin-left:2px;">®</span>
    </div>
    """, unsafe_allow_html=True)
st.sidebar.markdown("</div>", unsafe_allow_html=True)

# --- LOADING THE DATASET ---
uploaded_file = st.sidebar.file_uploader("📥 Enviar planilha (.csv)", type=["csv"])

df_raw = None
if uploaded_file is not None:
    df_raw = load_and_clean_data(uploaded_file)
    st.sidebar.success("Planilha carregada!")
else:
    default_paths = ['Historico_de_abastecimento.csv', '/workspace/knowledge/Historico_de_abastecimento.csv']
    for p in default_paths:
        if os.path.exists(p):
            df_raw = load_and_clean_data(p)
            break
            
if df_raw is None:
    st.sidebar.warning("⚠️ Envie o arquivo de histórico de abastecimento.")
    st.stop()

# --- SIDEBAR ADVANCED FILTERS (STRICTLY THE 5 SPECIFIED BY USER) ---
st.sidebar.markdown("### 🔍 Filtros de Análise")

# 1. Periodo de análise
if 'DATA' in df_raw.columns and df_raw['DATA'].notna().any():
    min_date = df_raw['DATA'].min()
    max_date = df_raw['DATA'].max()
    date_range = st.sidebar.date_input(
        "Período de análise",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
else:
    date_range = None

# 2. Estados
ufs = sorted(df_raw['UF'].dropna().unique().tolist()) if 'UF' in df_raw.columns else []
selected_ufs = st.sidebar.multiselect("Estados", options=ufs, default=ufs)

# 3. Categoria dos veiculos
categories = sorted(df_raw['CATEGORIA'].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Categoria dos veiculos", options=categories, default=categories)

# 4. Tipo de combustivel
fuels = sorted(df_raw['TIPO COMBUSTIVEL'].dropna().unique().tolist()) if 'TIPO COMBUSTIVEL' in df_raw.columns else []
selected_fuels = st.sidebar.multiselect("Tipo de combustivel", options=fuels, default=fuels)

# 5. Faixa de Valor de Transação
min_val, max_val = float(df_raw['VALOR EMISSAO'].min()), float(df_raw['VALOR EMISSAO'].max())
selected_val_range = st.sidebar.slider(
    "Faixa de Valor de Transação",
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
if selected_fuels:
    df_filtered = df_filtered[df_filtered['TIPO COMBUSTIVEL'].isin(selected_fuels)]

df_filtered = df_filtered[
    (df_filtered['VALOR EMISSAO'] >= selected_val_range[0]) & 
    (df_filtered['VALOR EMISSAO'] <= selected_val_range[1])
]

if df_filtered.empty:
    st.error("❌ Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

# --- APPLY GLOBAL INTERACTIVE CROSS-FILTERS ---
df_global = df_filtered.copy()

if st.session_state['global_clicked_quinzena']:
    df_global = df_global[df_global['QUINZENA'] == st.session_state['global_clicked_quinzena']]
if st.session_state['global_clicked_placa']:
    df_global = df_global[df_global['PLACA'] == st.session_state['global_clicked_placa']]
if st.session_state['global_clicked_motorista']:
    df_global = df_global[df_global['NOME MOTORISTA'] == st.session_state['global_clicked_motorista']]
if st.session_state['global_clicked_estado']:
    df_global = df_global[df_global['UF'] == st.session_state['global_clicked_estado']]

# --- METRIC CALCULATIONS FROM GLOBALLY FILTERED DATAFRAME ---
total_spend = df_global['VALOR EMISSAO'].sum()
total_liters = df_global['LITROS'].sum()
total_km = df_global[df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM']['KM RODADOS OU HORAS TRABALHADAS'].sum()

# Consumption General Diesel
diesel_filtered = df_global[(df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & (df_global['LITROS'] > 0)]
diesel_liters_total = diesel_filtered['LITROS'].sum()
general_avg_km_l = total_km / diesel_liters_total if diesel_liters_total > 0 else 0.0

general_cost_km = total_spend / total_km if total_km > 0 else 0.0
num_vehicles = df_global['PLACA'].nunique()
num_drivers = df_global['NOME MOTORISTA'].nunique()
num_transactions = len(df_global)

# --- HEADER AREA ---
st.markdown("""
<div class="app-header">
    <div style="padding-top: 5px;">
        <h1 style="margin:0; font-size: 24px; color: #0f172a;">Indicador de Combustível</h1>
        <p style="margin:0; color: #64748b; font-size:13px;">Gestão de Frota ANJUN</p>
    </div>
</div>
""", unsafe_allow_html=True)

# --- GLOBAL ACTIVE FILTERS BANNER ---
active_filters = []
if st.session_state['global_clicked_quinzena']:
    active_filters.append(f"Quinzena: {st.session_state['global_clicked_quinzena']}")
if st.session_state['global_clicked_placa']:
    active_filters.append(f"Veículo: {st.session_state['global_clicked_placa']}")
if st.session_state['global_clicked_motorista']:
    active_filters.append(f"Motorista: {st.session_state['global_clicked_motorista']}")
if st.session_state['global_clicked_estado']:
    active_filters.append(f"Estado: {st.session_state['global_clicked_estado']}")

if active_filters:
    cols_active = st.columns([10, 2])
    with cols_active[0]:
        st.markdown(f'<div style="background-color: #e0f2fe; border-left: 4px solid #0284c7; padding: 10px; border-radius: 6px; color: #0369a1; font-size:13px; margin-bottom:15px;">'
                    f'🔗 <b>Filtros Cruzados Globais Ativos (Interativos):</b> {", ".join(active_filters)}. '
                    f'Todos os gráficos e tabelas estão sendo filtrados!</div>', unsafe_allow_html=True)
    with cols_active[1]:
        if st.button("🔄 Limpar Filtros", key="clear_active_cross_filters", use_container_width=True):
            st.session_state['global_clicked_quinzena'] = None
            st.session_state['global_clicked_placa'] = None
            st.session_state['global_clicked_motorista'] = None
            st.session_state['global_clicked_estado'] = None
            st.rerun()

# --- CONSOLIDATED METRIC BUTTON CARDS ---
st.markdown("### 📊 Indicadores Consolidados")
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

with col1:
    if st.button(f"Gasto Total\n\n{format_pt_br(total_spend, 2, True)}", key="kpi_spend"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col2:
    if st.button(f"Volume Total\n\n{format_pt_br(total_liters, 1)} L", key="kpi_liters"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col3:
    if st.button(f"Distância Total\n\n{format_pt_br(total_km, 0)} km", key="kpi_km"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col4:
    if st.button(f"Média Geral\n\n{format_pt_br(general_avg_km_l, 2)} km/L", key="kpi_avg"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col5:
    if st.button(f"Custo/KM Médio\n\n{format_pt_br(general_cost_km, 2, True)}/km", key="kpi_cost_km"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col6:
    if st.button(f"Veículos\n\n{num_vehicles} Ativos", key="kpi_veiculos"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col7:
    if st.button(f"Motoristas\n\n{num_drivers} Ativos", key="kpi_motoristas"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col8:
    if st.button(f"Abastecimentos\n\n{num_transactions} Transações", key="kpi_transacoes"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()

st.markdown("<hr style='margin: 10px 0 20px 0; border:0; border-top: 1px solid #cbd5e1;'>", unsafe_allow_html=True)

# --- APP TABS ---
tab_oper, tab_efet, tab_mot, tab_est_pos, tab_audit = st.tabs([
    "📈 Custos & Volumes",
    "🚚 Eficiência Frota",
    "👨🏻‍✈️ Motoristas",
    "🌍 Estados & Postos",
    "🔍 Auditoria & Dados"
])

all_quinzenas = sorted(df_global['QUINZENA'].unique(), key=get_fortnight_sort_key)

# -----------------------------------------------------------------------------
# TAB 1: CUSTOS & VOLUMES QUINZENAIS
# -----------------------------------------------------------------------------
with tab_oper:
    st.subheader("📊 Relatório de Custos e Consumo Quinzenal")
    
    # Aggregation by fortnight
    fq_summary = df_global.groupby('QUINZENA')[['VALOR EMISSAO', 'LITROS']].sum().reindex(all_quinzenas).reset_index()
    
    # Plotly Double Y-Axis Chart (Bar vs Line)
    fig_fq_dual = go.Figure()
    
    # Bar for spend
    fig_fq_dual.add_trace(go.Bar(
        x=fq_summary['QUINZENA'],
        y=fq_summary['VALOR EMISSAO'],
        name="Valor Gasto (R$)",
        marker_color="#009a53", # Verde Anjun
        text=fq_summary['VALOR EMISSAO'].apply(lambda x: format_pt_br(x, 2, True)),
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
        text=fq_summary['LITROS'].apply(lambda x: format_pt_br(x, 0) + " L"),
        textposition="top center",
        yaxis="y2"
    ))
    
    fig_fq_dual.update_layout(
        title=dict(text="Custos e Volumes por Quinzena", font=dict(size=15, color="#1e293b", family="Inter")),
        xaxis=dict(title="Quinzena"),
        yaxis=dict(title=dict(text="Valor Gasto", font=dict(color="#009a53")), tickfont=dict(color="#009a53"), tickprefix="R$ "),
        yaxis2=dict(title=dict(text="Volume (Litros)", font=dict(color="#dc2626")), tickfont=dict(color="#dc2626"), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255, 255, 255, 0.8)"),
        margin=dict(l=40, r=40, t=50, b=40),
        height=450,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff"
    )
    
    selected_fq = st.plotly_chart(fig_fq_dual, use_container_width=True, on_select="rerun", key="fq_chart_select")
    
    # Interactive filtering based on click
    clicked_fq = None
    if selected_fq and "selection" in selected_fq and "points" in selected_fq["selection"] and selected_fq["selection"]["points"]:
        clicked_fq = selected_fq["selection"]["points"][0].get("x")
        if clicked_fq != st.session_state['global_clicked_quinzena']:
            st.session_state['global_clicked_quinzena'] = clicked_fq
            st.rerun()
            
    # Clear filter if clicked empty area
    if selected_fq and "selection" in selected_fq and not selected_fq["selection"]["points"] and st.session_state['global_clicked_quinzena'] is not None:
        st.session_state['global_clicked_quinzena'] = None
        st.rerun()

    st.markdown("#### Detalhamento das Transações")
    st.dataframe(
        df_global[['DATA TRANSACAO', 'PLACA', 'CATEGORIA', 'NOME MOTORISTA', 'TIPO COMBUSTIVEL', 'LITROS', 'VL/LITRO', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']].sort_values(by='DATA TRANSACAO', ascending=False),
        use_container_width=True,
        column_config={
            "VALOR EMISSAO": st.column_config.NumberColumn("Valor Gasto", format="R$ %.2f"),
            "VL/LITRO": st.column_config.NumberColumn("Preço/Litro", format="R$ %.3f"),
            "LITROS": st.column_config.NumberColumn("Litros", format="%.2f L")
        },
        hide_index=True
    )

# -----------------------------------------------------------------------------
# TAB 2: EFICIÊNCIA FROTA (WITH SEMAPHORE COLOR LOGIC - NO YELLOW)
# -----------------------------------------------------------------------------
with tab_efet:
    st.subheader("🚚 Eficiência & Desempenho")
    
    # Charts Section (Aligned side-by-side above tables)
    col_ef1, col_ef2 = st.columns(2)
    
    df_diesel_eff = df_global[
        (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_global['KM/LITRO OU LITROS/HORA'] > 0) & 
        (df_global['KM/LITRO OU LITROS/HORA'] < 30)
    ]
    
    with col_ef1:
        st.markdown("#### Autonomia por Veículo (km/L)")
        if not df_diesel_eff.empty:
            avg_plate_eff = df_diesel_eff.groupby(['PLACA', 'CATEGORIA'])['KM/LITRO OU LITROS/HORA'].mean().reset_index()
            avg_plate_eff = avg_plate_eff.sort_values(by='KM/LITRO OU LITROS/HORA', ascending=False)
            
            # Apply Semaphore Colors (No Yellow: > 7 Green, 6 to 7 Amarelo #f7cd23, < 6 Red)
            avg_plate_eff['COR'] = np.select(
                [avg_plate_eff['KM/LITRO OU LITROS/HORA'] > 7.0, avg_plate_eff['KM/LITRO OU LITROS/HORA'] >= 6.0],
                ['#009a53', '#f7cd23'], # Green ANJUN, Amarelo #f7cd23
                default='#dc2626' # Red
            )
            
            # Formatting labels
            avg_plate_eff['TEXT_LABEL'] = avg_plate_eff['KM/LITRO OU LITROS/HORA'].apply(lambda x: format_pt_br(x, 2) + " km/L")
            
            fig_eff = px.bar(
                avg_plate_eff,
                x='PLACA',
                y='KM/LITRO OU LITROS/HORA',
                color='COR',
                color_discrete_map='identity',
                labels={'KM/LITRO OU LITROS/HORA': 'Autonomia Média (km/L)', 'PLACA': 'Placa'},
                text='TEXT_LABEL',
                title='Consumo de Diesel por Veículo (Clique para Filtrar)',
                height=450
            )
            fig_eff.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
            fig_eff.update_traces(textposition='auto')
            selected_plate_data = st.plotly_chart(fig_eff, use_container_width=True, on_select="rerun", key="plate_chart_select")
            
            # Global filtering on click
            if selected_plate_data and "selection" in selected_plate_data and "points" in selected_plate_data["selection"] and selected_plate_data["selection"]["points"]:
                clicked_pl = selected_plate_data["selection"]["points"][0].get("x")
                if clicked_pl != st.session_state['global_clicked_placa']:
                    st.session_state['global_clicked_placa'] = clicked_pl
                    st.rerun()
            if selected_plate_data and "selection" in selected_plate_data and not selected_plate_data["selection"]["points"] and st.session_state['global_clicked_placa'] is not None:
                st.session_state['global_clicked_placa'] = None
                st.rerun()
        else:
            st.info("Nenhum dado de Diesel (km/L) disponível para a plotagem do gráfico.")
            
    with col_ef2:
        st.markdown("#### Custo por KM por Veículo (R$/km)")
        df_km_cost = df_global[
            (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            (df_global['KM RODADOS OU HORAS TRABALHADAS'] > 0)
        ]
        if not df_km_cost.empty:
            plate_km_cost = df_km_cost.groupby(['PLACA', 'CATEGORIA']).apply(
                lambda x: x['VALOR EMISSAO'].sum() / x['KM RODADOS OU HORAS TRABALHADAS'].sum()
            ).reset_index(name='R_KM')
            plate_km_cost = plate_km_cost.sort_values(by='R_KM', ascending=True)
            
            # Apply Cost Semaphore Colors (< 0.85 Green, 0.85 to 0.95 Amarelo #f7cd23, > 0.95 Red)
            plate_km_cost['COR'] = np.select(
                [plate_km_cost['R_KM'] < 0.85, plate_km_cost['R_KM'] <= 0.95],
                ['#009a53', '#f7cd23'],
                default='#dc2626'
            )
            
            # Formatting labels
            plate_km_cost['TEXT_LABEL'] = plate_km_cost['R_KM'].apply(lambda x: format_pt_br(x, 2, True) + "/km")
            
            fig_km = px.bar(
                plate_km_cost,
                x='PLACA',
                y='R_KM',
                color='COR',
                color_discrete_map='identity',
                labels={'R_KM': 'Custo Real (R$/km)', 'PLACA': 'Placa'},
                text='TEXT_LABEL',
                title='Custo Financeiro de Rodagem (R$ por KM)',
                height=450
            )
            fig_km.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", yaxis=dict(tickprefix="R$ "))
            fig_km.update_traces(textposition='auto')
            st.plotly_chart(fig_km, use_container_width=True)
        else:
            st.info("Quilometragem indisponível para cálculo de custo/km.")

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)

    # Table section below the charts as requested!
    st.markdown("#### 🗒️ Desempenho Físico por Veículo e Quinzena")
    vehicle_fq_metrics = df_global.groupby(['PLACA', 'CATEGORIA', 'QUINZENA']).agg(
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
    
    # Apply discret symbols in table (🟢, 🟠, 🔴)
    def get_table_signal(val):
        if val > 7.0: return "🟢 Excelente"
        elif val >= 6.0: return "🟠 Alerta"
        return "🔴 Crítico"
        
    vehicle_fq_metrics['Status'] = vehicle_fq_metrics['consumo_medio'].apply(get_table_signal)
    
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
            "consumo_medio": st.column_config.NumberColumn("Autonomia Média", format="%.2f km/L"),
            "Status": "Status de Consumo"
        },
        hide_index=True,
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# TAB 3: PERFORMANCE DE MOTORISTAS (WITH R$/KM AND SAME SEMAPHORE COLOR LOGIC)
# -----------------------------------------------------------------------------
with tab_mot:
    st.subheader("👨🏻‍✈️ Performance de Motoristas")
    
    col_m1, col_m2 = st.columns(2)
    
    # Gasto total por motorista por quinzena
    driver_spend_fq = df_global.groupby(['NOME MOTORISTA', 'QUINZENA'])['VALOR EMISSAO'].sum().reset_index()
    driver_spend_fq = driver_spend_fq[driver_spend_fq['QUINZENA'].isin(all_quinzenas)]
    
    # Custo por km por motorista
    df_drv_km_cost = df_global[
        (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_global['KM RODADOS OU HORAS TRABALHADAS'] > 0)
    ]
    
    with col_m1:
        st.markdown("#### Investimento por Motorista por Quinzena (R$)")
        fig_driver_spend = px.bar(
            driver_spend_fq,
            y='NOME MOTORISTA',
            x='VALOR EMISSAO',
            color='QUINZENA',
            barmode='group',
            orientation='h',
            labels={'VALOR EMISSAO': 'Gasto Total (R$)', 'NOME MOTORISTA': 'Motorista', 'QUINZENA': 'Quinzena'},
            color_discrete_sequence=['#009a53', '#f7cd23', '#dc2626'],
            text=driver_spend_fq['VALOR EMISSAO'].apply(lambda x: format_pt_br(x, 2, True)),
            title='Gastos Totais por Motorista (Clique para Filtrar)',
            height=450
        )
        fig_driver_spend.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", xaxis=dict(tickprefix="R$ "))
        fig_driver_spend.update_traces(textposition='auto')
        selected_driver_data = st.plotly_chart(fig_driver_spend, use_container_width=True, on_select="rerun", key="driver_chart_select")
        
        # Global selection
        if selected_driver_data and "selection" in selected_driver_data and "points" in selected_driver_data["selection"] and selected_driver_data["selection"]["points"]:
            clicked_dr = selected_driver_data["selection"]["points"][0].get("y")
            if clicked_dr != st.session_state['global_clicked_motorista']:
                st.session_state['global_clicked_motorista'] = clicked_dr
                st.rerun()
        if selected_driver_data and "selection" in selected_driver_data and not selected_driver_data["selection"]["points"] and st.session_state['global_clicked_motorista'] is not None:
            st.session_state['global_clicked_motorista'] = None
            st.rerun()
        
    with col_m2:
        st.markdown("#### Custo por KM por Motorista (R$/km)")
        if not df_drv_km_cost.empty:
            driver_km_cost = df_drv_km_cost.groupby('NOME MOTORISTA').apply(
                lambda x: x['VALOR EMISSAO'].sum() / x['KM RODADOS OU HORAS TRABALHADAS'].sum()
            ).reset_index(name='R_KM')
            driver_km_cost = driver_km_cost.sort_values(by='R_KM', ascending=True)
            
            # Apply driver Semaphore Colors (same logic as trucks: < 0.85 Green, 0.85 to 0.95 Amarelo #f7cd23, > 0.95 Red)
            driver_km_cost['COR'] = np.select(
                [driver_km_cost['R_KM'] < 0.85, driver_km_cost['R_KM'] <= 0.95],
                ['#009a53', '#f7cd23'],
                default='#dc2626'
            )
            
            # Formatting labels
            driver_km_cost['TEXT_LABEL'] = driver_km_cost['R_KM'].apply(lambda x: format_pt_br(x, 2, True) + "/km")
            
            fig_driver_km = px.bar(
                driver_km_cost,
                x='R_KM',
                y='NOME MOTORISTA',
                color='COR',
                color_discrete_map='identity',
                labels={'R_KM': 'Custo Real (R$/km)', 'NOME MOTORISTA': 'Motorista'},
                text='TEXT_LABEL',
                title='Custo Médio de Condução por Motorista (R$/km)',
                height=450,
                orientation='h'
            )
            fig_driver_km.update_layout(yaxis={'categoryorder': 'total descending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", xaxis=dict(tickprefix="R$ "))
            fig_driver_km.update_traces(textposition='auto')
            st.plotly_chart(fig_driver_km, use_container_width=True)
        else:
            st.info("Dados de quilometragem indisponíveis para cálculo de R$/km de motoristas.")

    st.markdown("<hr style='margin: 20px 0;'>\", unsafe_allow_html=True")
    
    st.markdown("#### 🗒️ Histórico Detalhado por Motorista")
    st.dataframe(
        df_global[['DATA TRANSACAO', 'QUINZENA', 'NOME MOTORISTA', 'PLACA', 'CATEGORIA', 'TIPO COMBUSTIVEL', 'LITROS', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']].sort_values(by='DATA TRANSACAO', ascending=False),
        use_container_width=True,
        column_config={
            "VALOR EMISSAO": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "LITROS": st.column_config.NumberColumn("Litros", format="%.2f L")
        },
        hide_index=True
    )

# -----------------------------------------------------------------------------
# TAB 4: ESTADOS & POSTOS (TOP 10 SPEND IN REAIS)
# -----------------------------------------------------------------------------
with tab_est_pos:
    st.subheader("🌍 Regiões & Postos")
    
    col_eg1, col_eg2 = st.columns(2)
    
    with col_eg1:
        st.markdown("#### Gastos por Estado (UF)")
        state_summary = df_global.groupby('UF').agg(
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
            color_discrete_sequence=['#009a53', '#f7cd23', '#dc2626'],
            text=state_summary['gasto_total'].apply(lambda x: format_pt_br(x, 2, True)),
            title='Faturamento Acumulado de Abastecimento por UF (Clique para Filtrar)',
            height=450
        )
        fig_state.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", yaxis=dict(tickprefix="R$ "))
        fig_state.update_traces(textposition='auto')
        selected_state_data = st.plotly_chart(fig_state, use_container_width=True, on_select="rerun", key="state_chart_select")
        
        # Global selection
        if selected_state_data and "selection" in selected_state_data and "points" in selected_state_data["selection"] and selected_state_data["selection"]["points"]:
            clicked_st = selected_state_data["selection"]["points"][0].get("x")
            if clicked_st != st.session_state['global_clicked_estado']:
                st.session_state['global_clicked_estado'] = clicked_st
                st.rerun()
        if selected_state_data and "selection" in selected_state_data and not selected_state_data["selection"]["points"] and st.session_state['global_clicked_estado'] is not None:
            st.session_state['global_clicked_estado'] = None
            st.rerun()
        
    with col_eg2:
        st.markdown("#### Gastos por Postos de Combustível (Top 10 em R$)")
        station_summary = df_global.groupby('NOME ESTABELECIMENTO').agg(
            gasto_total=('VALOR EMISSAO', 'sum'),
            quantidade=('VALOR EMISSAO', 'count')
        ).reset_index().sort_values(by='gasto_total', ascending=False).head(10)
        
        station_summary['TEXT_LABEL'] = station_summary['gasto_total'].apply(lambda x: format_pt_br(x, 2, True))
        
        fig_station = px.bar(
            station_summary,
            x='gasto_total',
            y='NOME ESTABELECIMENTO',
            orientation='h',
            labels={'gasto_total': 'Valor Total Abastecido (R$)', 'NOME ESTABELECIMENTO': 'Posto de Combustível'},
            text='TEXT_LABEL',
            title='Postos com Maior Valor Total Abastecido (Top 10)',
            color_discrete_sequence=['#009a53'], # Verde Anjun
            height=450
        )
        fig_station.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", xaxis=dict(tickprefix="R$ "))
        fig_station.update_traces(textposition='auto')
        st.plotly_chart(fig_station, use_container_width=True)

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
    
    st.markdown("#### 🗒️ Resumo Geográfico Completo por Estado (UF)")
    st.dataframe(
        state_summary,
        column_config={
            "UF": "Estado (UF)",
            "gasto_total": st.column_config.NumberColumn("Investimento Gasto", format="R$ %,.2f"),
            "litros_totais": st.column_config.NumberColumn("Litros Consumidos", format="%,.2f L"),
            "quantidade": st.column_config.NumberColumn("Contagem Abastecimentos", format="%d")
        },
        hide_index=True,
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# TAB 5: AUDITORIA & DADOS (SMART ZERO-KM AND ADJUSTED TYPICAL EFFICIENCY LIMITS)
# -----------------------------------------------------------------------------
with tab_audit:
    st.subheader("🔍 Auditoria & Dados")
    
    # 1. Gráficos e Tabelas de Inconsistências (Renderizados Acima!)
    col_aud1, col_aud2 = st.columns(2)
    
    # Find zero km refuels for Diesel
    anomalies_zero_km_raw = df_global[
        (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_global['KM RODADOS OU HORAS TRABALHADAS'] == 0)
    ]
    
    # EXCLUDE if same vehicle had Arla refueling on the same day in df_raw
    arla_refuels = df_raw[df_raw['TIPO COMBUSTIVEL'] == 'Arla 32']
    
    anomalies_zero_km_filtered_list = []
    for idx, row in anomalies_zero_km_raw.iterrows():
        same_day_arla = arla_refuels[
            (arla_refuels['PLACA'] == row['PLACA']) & 
            (arla_refuels['DATA'] == row['DATA'])
        ]
        if same_day_arla.empty:
            anomalies_zero_km_filtered_list.append(row)
            
    if anomalies_zero_km_filtered_list:
        anomalies_zero_km_filtered = pd.DataFrame(anomalies_zero_km_filtered_list)
    else:
        anomalies_zero_km_filtered = pd.DataFrame(columns=anomalies_zero_km_raw.columns)
    
    with col_aud1:
        st.markdown("#### 🚨 Abastecimento com km zerado")
        if not anomalies_zero_km_filtered.empty:
            st.warning(f"Identificados {len(anomalies_zero_km_filtered)} abastecimentos de Diesel com KM zerado (sem abastecimento de Arla no mesmo dia).")
            
            # Interactive Selection Row
            selected_zero_km = st.dataframe(
                anomalies_zero_km_filtered[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'LITROS', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="zero_km_select"
            )
        else:
            st.success("✅ Nenhum abastecimento de Diesel com KM zerado (fora da regra de Arla) encontrado.")
            selected_zero_km = None
            
    with col_aud2:
        # User defined: Atypical efficiency threshold updated to < 4 OR > 12 km/L as requested!
        anomalies_eff = df_global[
            (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            ((df_global['KM/LITRO OU LITROS/HORA'] < 4) | (df_global['KM/LITRO OU LITROS/HORA'] > 12)) &
            (df_global['KM/LITRO OU LITROS/HORA'] != 0)
        ]
        st.markdown("#### ⚠️ Rendimento Atípico (< 4 km/L ou > 12 km/L)")
        if not anomalies_eff.empty:
            st.error(f"Identificados {len(anomalies_eff)} abastecimentos fora da faixa de rendimento padrão.")
            
            # Interactive Selection Row
            selected_eff = st.dataframe(
                anomalies_eff[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'KM/LITRO OU LITROS/HORA', 'LITROS', 'VALOR EMISSAO']],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="eff_select"
            )
        else:
            st.success("✅ Nenhum consumo atípico (< 4 ou > 12 km/L) encontrado.")
            selected_eff = None

    # Check row selections to dynamically filter the General Table below
    clicked_transaction_date = None
    clicked_plate_num = None
    
    if selected_zero_km and "selection" in selected_zero_km and "rows" in selected_zero_km["selection"] and selected_zero_km["selection"]["rows"]:
        row_idx = selected_zero_km["selection"]["rows"][0]
        clicked_transaction_date = anomalies_zero_km_filtered.iloc[row_idx]['DATA TRANSACAO']
        clicked_plate_num = anomalies_zero_km_filtered.iloc[row_idx]['PLACA']
        
    elif selected_eff and "selection" in selected_eff and "rows" in selected_eff["selection"] and selected_eff["selection"]["rows"]:
        row_idx = selected_eff["selection"]["rows"][0]
        clicked_transaction_date = anomalies_eff.iloc[row_idx]['DATA TRANSACAO']
        clicked_plate_num = anomalies_eff.iloc[row_idx]['PLACA']

    st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
    
    st.markdown("#### 📂 Tabela de Dados Geral")
    
    if clicked_transaction_date and clicked_plate_num:
        st.markdown(f'<div class="detail-box">🔍 <b>Filtro de Inconsistência Ativo:</b> Exibindo o registro de <b>{clicked_plate_num}</b> em {clicked_transaction_date}. Clique novamente na linha da tabela de inconsistências acima para limpar o filtro.</div>', unsafe_allow_html=True)
        # Filter table below
        df_base_show = df_global[(df_global['DATA TRANSACAO'] == clicked_transaction_date) & (df_global['PLACA'] == clicked_plate_num)]
    else:
        df_base_show = df_global

    display_cols = [
        'DATA TRANSACAO', 'PLACA', 'CATEGORIA', 'NOME MOTORISTA', 'TIPO COMBUSTIVEL',
        'LITROS', 'VL/LITRO', 'KM RODADOS OU HORAS TRABALHADAS',
        'KM/LITRO OU LITROS/HORA', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO', 'UF'
    ]
    display_cols = [col for col in display_cols if col in df_global.columns]
    
    st.dataframe(
        df_base_show[display_cols].sort_values(by='DATA TRANSACAO', ascending=False),
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
    csv_buffer = df_base_show.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        label="📥 Exportar Base de Dados Filtrada (CSV)",
        data=csv_buffer,
        file_name="historico_combustivel_auditoria.csv",
        mime="text/csv"
    )

# --- DYNAMIC REPORT PRINTING (PDF GENERATION) ---
st.markdown("<hr style='margin: 30px 0;'>", unsafe_allow_html=True)
st.markdown("### 🖨️ Exportação de Relatório Executivo")
st.write("Gere um relatório consolidado em formato PDF contendo todas as métricas gerenciais, faturamento por quinzena, desempenho físico de veículos e custos de motoristas de acordo com os filtros atuais.")

# PDF Generation Function call
def generate_pdf_report(df_filtered, total_spend, total_liters, total_km, general_avg_km_l, general_cost_km, num_vehicles, num_drivers, num_transactions, anomalies_zero_km_filtered, anomalies_eff):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54, leftMargin=54,
        topMargin=54, bottomMargin=54
    )
    
    # Define design system colors
    COLORS = {
        'heading': HexColor('#009a53'),  # Verde Anjun
        'body': HexColor('#1e293b'),     # Slate 800
        'accent': HexColor('#dc2626'),    # Vermelho Anjun
        'muted': HexColor('#64748b'),     # Slate 500
        'bg_alt': HexColor('#f8fafc'),    # Slate 50
        'bg_header': HexColor('#009a53'), # Verde Anjun for table headers
        'white': HexColor('#ffffff')
    }
    
    styles = getSampleStyleSheet()
    
    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=COLORS['heading'],
        leading=24,
        spaceAfter=6,
        alignment=TA_LEFT
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        fontName='Helvetica',
        fontSize=11,
        textColor=COLORS['muted'],
        leading=14,
        spaceAfter=15,
        alignment=TA_LEFT
    )
    h1_style = ParagraphStyle(
        'H1',
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=COLORS['heading'],
        leading=15,
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        fontName='Helvetica',
        fontSize=9,
        textColor=COLORS['body'],
        leading=12,
        spaceAfter=4,
        alignment=TA_LEFT
    )
    thead_style = ParagraphStyle(
        'THead',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=COLORS['white'],
        leading=10
    )
    tbody_style = ParagraphStyle(
        'TBody',
        fontName='Helvetica',
        fontSize=8,
        textColor=COLORS['body'],
        leading=10
    )
    tbody_bold_style = ParagraphStyle(
        'TBodyBold',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=COLORS['body'],
        leading=10
    )
    
    story = []
    
    # 1. Header (Logo / Brand Name + Title)
    story.append(Paragraph("<b>ANJUN</b> Transportes", title_style))
    story.append(Paragraph("Relatório Gerencial de Controle de Abastecimento e Eficiência da Frota", subtitle_style))
    story.append(Spacer(1, 10))
    
    # 2. Key Metrics Grid (KPIs)
    story.append(Paragraph("<b>Resumo Geral do Período</b>", h1_style))
    
    kpi_data = [
        [
            Paragraph("<b>Investimento Total</b>", tbody_bold_style),
            Paragraph(format_pt_br(total_spend, 2, True), tbody_style),
            Paragraph("<b>Litros Abastecidos</b>", tbody_bold_style),
            Paragraph(f"{format_pt_br(total_liters, 1)} L", tbody_style)
        ],
        [
            Paragraph("<b>Distância Rodada</b>", tbody_bold_style),
            Paragraph(f"{format_pt_br(total_km, 0)} km", tbody_style),
            Paragraph("<b>Consumo Médio Geral</b>", tbody_bold_style),
            Paragraph(f"{format_pt_br(general_avg_km_l, 2)} km/L", tbody_style)
        ],
        [
            Paragraph("<b>Custo por KM</b>", tbody_bold_style),
            Paragraph(f"{format_pt_br(general_cost_km, 2, True)}/km", tbody_style),
            Paragraph("<b>Abastecimentos</b>", tbody_bold_style),
            Paragraph(str(num_transactions), tbody_style)
        ],
        [
            Paragraph("<b>Veículos Ativos</b>", tbody_bold_style),
            Paragraph(str(num_vehicles), tbody_style),
            Paragraph("<b>Motoristas Ativos</b>", tbody_bold_style),
            Paragraph(str(num_drivers), tbody_style)
        ]
    ]
    
    kpi_table = Table(kpi_data, colWidths=[120, 130, 120, 130])
    kpi_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 0), (0, -1), COLORS['bg_alt']),
        ('BACKGROUND', (2, 0), (2, -1), COLORS['bg_alt']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))
    
    # 3. Fortnightly Summary
    story.append(Paragraph("<b>Custos e Volumes por Quinzena</b>", h1_style))
    all_quinzenas_pdf = sorted(df_filtered['QUINZENA'].unique(), key=get_fortnight_sort_key)
    fq_data = df_filtered.groupby('QUINZENA').agg(
        gasto_total=('VALOR EMISSAO', 'sum'),
        litros_totais=('LITROS', 'sum'),
        abastecimentos=('VALOR EMISSAO', 'count')
    ).reindex(all_quinzenas_pdf).reset_index()
    
    diesel_fq_km = df_filtered[df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM'].groupby('QUINZENA')['KM RODADOS OU HORAS TRABALHADAS'].sum().reindex(all_quinzenas_pdf)
    fq_data['km_rodados'] = fq_data['QUINZENA'].map(diesel_fq_km).fillna(0)
    fq_data['consumo_medio'] = np.where(fq_data['litros_totais'] > 0, fq_data['km_rodados'] / fq_data['litros_totais'], 0.0)
    
    fq_table_rows = [
        [Paragraph(f"<b>{col}</b>", thead_style) for col in ["Quinzena", "Gasto Total", "Litros Consumidos", "Abastecimentos", "KM Rodados", "Consumo (km/L)"]]
    ]
    for idx, row in fq_data.iterrows():
        fq_table_rows.append([
            Paragraph(str(row['QUINZENA']), tbody_bold_style),
            Paragraph(format_pt_br(row['gasto_total'], 2, True), tbody_style),
            Paragraph(f"{format_pt_br(row['litros_totais'], 1)} L", tbody_style),
            Paragraph(str(row['abastecimentos']), tbody_style),
            Paragraph(f"{format_pt_br(row['km_rodados'], 0)} km", tbody_style),
            Paragraph(f"{format_pt_br(row['consumo_medio'], 2)} km/L", tbody_style)
        ])
    
    fq_table = Table(fq_table_rows, colWidths=[100, 85, 85, 75, 75, 80])
    fq_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['bg_header']),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['bg_alt']]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(fq_table)
    story.append(Spacer(1, 15))
    
    # 4. Vehicle Efficiency Summary
    story.append(Paragraph("<b>Eficiência Operacional por Veículo</b>", h1_style))
    df_diesel_eff = df_filtered[
        (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_filtered['KM/LITRO OU LITROS/HORA'] > 0)
    ]
    avg_plate_eff = df_diesel_eff.groupby(['PLACA', 'CATEGORIA'])['KM/LITRO OU LITROS/HORA'].mean().reset_index()
    
    df_km_cost = df_filtered[
        (df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_filtered['KM RODADOS OU HORAS TRABALHADAS'] > 0)
    ]
    plate_km_cost = df_km_cost.groupby(['PLACA', 'CATEGORIA']).apply(
        lambda x: x['VALOR EMISSAO'].sum() / x['KM RODADOS OU HORAS TRABALHADAS'].sum()
    ).reset_index(name='R_KM')
    
    vehicle_merged = pd.merge(avg_plate_eff, plate_km_cost, on=['PLACA', 'CATEGORIA'], how='outer')
    
    veh_table_rows = [
        [Paragraph(f"<b>{col}</b>", thead_style) for col in ["Placa", "Categoria", "Autonomia Média (km/L)", "Custo Real (R$/km)", "Status"]]
    ]
    for idx, row in vehicle_merged.iterrows():
        # Determine status
        eff = row['KM/LITRO OU LITROS/HORA']
        if pd.isna(eff) or eff == 0:
            status_text = "N/A"
        elif eff > 7.0:
            status_text = "🟢 Excelente"
        elif eff >= 6.0:
            status_text = "🟠 Alerta"
        else:
            status_text = "🔴 Crítico"
            
        r_km = row['R_KM']
        r_km_text = format_pt_br(r_km, 2, True) + "/km" if not pd.isna(r_km) else "N/A"
        eff_text = format_pt_br(eff, 2) + " km/L" if not pd.isna(eff) else "N/A"
        
        veh_table_rows.append([
            Paragraph(str(row['PLACA']), tbody_bold_style),
            Paragraph(str(row['CATEGORIA']), tbody_style),
            Paragraph(eff_text, tbody_style),
            Paragraph(r_km_text, tbody_style),
            Paragraph(status_text, tbody_bold_style)
        ])
        
    veh_table = Table(veh_table_rows, colWidths=[80, 100, 110, 110, 100])
    veh_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['bg_header']),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['bg_alt']]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(veh_table)
    
    # 5. Page Break for structured look
    story.append(PageBreak())
    
    # 6. Driver Performance Summary
    story.append(Paragraph("<b>Performance e Custos por Motorista</b>", h1_style))
    driver_summary = df_filtered.groupby('NOME MOTORISTA').agg(
        gasto_total=('VALOR EMISSAO', 'sum'),
        litros_totais=('LITROS', 'sum'),
        abastecimentos=('VALOR EMISSAO', 'count')
    ).reset_index()
    
    driver_km = df_filtered[df_filtered['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM'].groupby('NOME MOTORISTA')['KM RODADOS OU HORAS TRABALHADAS'].sum()
    driver_summary['km_rodados'] = driver_summary['NOME MOTORISTA'].map(driver_km).fillna(0)
    driver_summary['custo_km'] = np.where(driver_summary['km_rodados'] > 0, driver_summary['gasto_total'] / driver_summary['km_rodados'], 0.0)
    driver_summary['consumo_medio'] = np.where(driver_summary['litros_totais'] > 0, driver_summary['km_rodados'] / driver_summary['litros_totais'], 0.0)
    
    drv_table_rows = [
        [Paragraph(f"<b>{col}</b>", thead_style) for col in ["Motorista", "Gasto Total", "Litros", "KM Rodados", "Custo/KM", "Consumo Médio", "Status"]]
    ]
    for idx, row in driver_summary.iterrows():
        r_km = row['custo_km']
        if r_km == 0:
            status_text = "N/A"
        elif r_km < 0.85:
            status_text = "🟢 Econômico"
        elif r_km <= 0.95:
            status_text = "🟠 Alerta"
        else:
            status_text = "🔴 Elevado"
            
        drv_table_rows.append([
            Paragraph(str(row['NOME MOTORISTA']), tbody_bold_style),
            Paragraph(format_pt_br(row['gasto_total'], 2, True), tbody_style),
            Paragraph(f"{format_pt_br(row['litros_totais'], 1)} L", tbody_style),
            Paragraph(f"{format_pt_br(row['km_rodados'], 0)} km", tbody_style),
            Paragraph(f"{format_pt_br(r_km, 2, True)}/km", tbody_style),
            Paragraph(f"{format_pt_br(row['consumo_medio'], 2)} km/L", tbody_style),
            Paragraph(status_text, tbody_bold_style)
        ])
        
    drv_table = Table(drv_table_rows, colWidths=[120, 70, 55, 65, 60, 70, 60])
    drv_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['bg_header']),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['bg_alt']]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(drv_table)
    story.append(Spacer(1, 15))
    
    # 7. Gas Stations Summary (Top 10)
    story.append(Paragraph("<b>Investimento nos Postos de Combustível (Top 10)</b>", h1_style))
    station_summary = df_filtered.groupby('NOME ESTABELECIMENTO').agg(
        gasto_total=('VALOR EMISSAO', 'sum'),
        quantidade=('VALOR EMISSAO', 'count')
    ).reset_index().sort_values(by='gasto_total', ascending=False).head(10)
    
    st_table_rows = [
        [Paragraph(f"<b>{col}</b>", thead_style) for col in ["Posto de Combustível", "Valor Abastecido", "Qtd. Abastecimentos", "Valor Médio / Transação"]]
    ]
    for idx, row in station_summary.iterrows():
        val = row['gasto_total']
        cnt = row['quantidade']
        avg_val = val / cnt if cnt > 0 else 0.0
        st_table_rows.append([
            Paragraph(str(row['NOME ESTABELECIMENTO']), tbody_bold_style),
            Paragraph(format_pt_br(val, 2, True), tbody_style),
            Paragraph(str(cnt), tbody_style),
            Paragraph(format_pt_br(avg_val, 2, True), tbody_style)
        ])
        
    st_table = Table(st_table_rows, colWidths=[180, 100, 100, 120])
    st_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['bg_header']),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['bg_alt']]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 15))
    
    # 8. Auditoria
    story.append(Paragraph("<b>Auditoria de Inconsistências Detectadas</b>", h1_style))
    story.append(Paragraph(f"• Abastecimentos com km zerado (excluindo same-day Arla): <b>{len(anomalies_zero_km_filtered)} ocorrências</b>", body_style))
    story.append(Paragraph(f"• Abastecimentos com autonomia atípica (< 4 km/L ou > 12 km/L): <b>{len(anomalies_eff)} ocorrências</b>", body_style))
    
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(HexColor('#cbd5e1'))
        canvas.setLineWidth(0.5)
        canvas.line(54, 40, doc.pagesize[0]-54, 40)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(COLORS['muted'])
        canvas.drawString(54, 28, f"Relatório Gerencial de Combustível - ANJUN S.A. | Gerado em {date.today().strftime('%d/%m/%Y')}")
        canvas.drawRightString(doc.pagesize[0]-54, 28, f"Página {doc.page}")
        canvas.restoreState()
        
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer.getvalue()

try:
    pdf_bytes = generate_pdf_report(
        df_global, total_spend, total_liters, total_km, general_avg_km_l, 
        general_cost_km, num_vehicles, num_drivers, num_transactions, 
        anomalies_zero_km_filtered, anomalies_eff
    )
    st.download_button(
        label="🖨️ Imprimir Relatório Executivo (PDF)",
        data=pdf_bytes,
        file_name=f"Relatorio_Gerencial_ANJUN_Combustivel_{date.today().strftime('%d_%m_%Y')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e:
    st.error(f"Erro ao preparar exportador PDF: {e}")
