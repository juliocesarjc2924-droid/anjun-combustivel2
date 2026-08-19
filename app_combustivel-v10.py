import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# --- PAGE CONFIGURATION & THEME ---
st.set_page_config(
    page_title="ANJUN - Gestão de Combustível",
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
    
    /* Botões de Indicadores Consolidados (Estilo KPI Card) */
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
    
    /* Estilo de Abas (Tabs) no topo */
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
</style>
""", unsafe_allow_html=True)

# Helper to format numbers in Brazilian Portuguese format (. for thousands, , for decimals)
def format_real(val):
    if pd.isna(val) or val is None:
        return "R$ 0,00"
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_num(val, decimals=1):
    if pd.isna(val) or val is None:
        return "0"
    fmt_str = f"{{:,.{decimals}f}}"
    return fmt_str.format(val).replace(",", "X").replace(".", ",").replace("X", ".")

# Helper function to convert Portuguese month name/year to chronological sort index
def get_fortnight_sort_key(name):
    if 'Jul' in name:
        return 1 if '1ª' in name else 2
    if 'Ago' in name:
        return 3 if '1ª' in name else 4
    if 'Set' in name:
        return 5 if '1ª' in name else 6
    return 99

# Status color emojis for signaling data (Traffic Light System)
def get_status_emoji_eff(val):
    if val > 8.5:
        return "🟢" # Verde: Excelente autonomia
    elif val >= 6.5:
        return "🟡" # Amarelo: Consumo médio/alerta
    else:
        return "🔴" # Vermelho: Consumo excessivo

def get_status_emoji_cost_km(val):
    if val < 0.85:
        return "🟢" # Verde: Custo baixo por km
    elif val <= 1.05:
        return "🟡" # Amarelo: Custo médio
    else:
        return "🔴" # Vermelho: Custo alto

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
    st.sidebar.warning("⚠️ Por favor, envie o arquivo de histórico de abastecimento.")
    st.stop()

# --- SIDEBAR ADVANCED FILTERS (STRICTLY THE 5 REQUESTED BY USER) ---
st.sidebar.markdown("### 🔍 Filtros de Análise")

# 1. Período de análise
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

# --- PREPARE DATASET FOR SAME-DAY ARLA RULE ---
# Map which vehicle plates and dates had Arla refuels
df_arla_days = df_raw[df_raw['TIPO COMBUSTIVEL'] == 'Arla 32'][['DATA', 'PLACA']].drop_duplicates()
arla_keys = set(zip(df_arla_days['DATA'], df_arla_days['PLACA']))

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
        <h1 style="margin:0; font-size: 26px; color: #0f172a;">Indicador de Combustível — ANJUN</h1>
        <p style="margin:0; color: #64748b; font-size:14px;">Acompanhamento de Custos, Autonomia e Auditoria de Frota</p>
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
                    f'🔗 <b>Filtros Ativos:</b> {", ".join(active_filters)}. '
                    f'Todos os gráficos e tabelas estão sendo filtrados!</div>', unsafe_allow_html=True)
    with cols_active[1]:
        if st.button("🔄 Limpar Filtros", key="clear_active_cross_filters", use_container_width=True):
            st.session_state['global_clicked_quinzena'] = None
            st.session_state['global_clicked_placa'] = None
            st.session_state['global_clicked_motorista'] = None
            st.session_state['global_clicked_estado'] = None
            st.rerun()

# --- CONSOLIDATED METRIC BUTTON CARDS ---
st.markdown("### 📊 Indicadores Consolidados (Clique para redefinir)")
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

with col1:
    if st.button(f"Gasto Total\n\n{format_real(total_spend)}", key="kpi_spend"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col2:
    if st.button(f"Volume Total\n\n{format_num(total_liters, 1)} L", key="kpi_liters"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col3:
    if st.button(f"Distância Total\n\n{format_num(total_km, 0)} km", key="kpi_km"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col4:
    if st.button(f"Média Geral\n\n{format_num(general_avg_km_l, 2)} km/L", key="kpi_avg"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col5:
    if st.button(f"Custo/KM Médio\n\n{format_real(general_cost_km)}/km", key="kpi_cost_km"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col6:
    if st.button(f"Veículos\n\n{format_num(num_vehicles, 0)} Ativos", key="kpi_veiculos"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col7:
    if st.button(f"Motoristas\n\n{format_num(num_drivers, 0)} Ativos", key="kpi_motoristas"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()
with col8:
    if st.button(f"Abastecimentos\n\n{format_num(num_transactions, 0)} Abast.", key="kpi_transacoes"):
        st.session_state['global_clicked_quinzena'] = None
        st.session_state['global_clicked_placa'] = None
        st.session_state['global_clicked_motorista'] = None
        st.session_state['global_clicked_estado'] = None
        st.rerun()

st.markdown("<hr style='margin: 15px 0 25px 0; border:0; border-top: 1px solid #cbd5e1;'>", unsafe_allow_html=True)

# Sidebar Clear Filters Button (Always Present)
if st.sidebar.button("🔄 Limpar Todos os Filtros", key="clear_all_global_filters_sidebar", use_container_width=True):
    st.session_state['global_clicked_quinzena'] = None
    st.session_state['global_clicked_placa'] = None
    st.session_state['global_clicked_motorista'] = None
    st.session_state['global_clicked_estado'] = None
    st.rerun()

all_quinzenas = sorted(df_global['QUINZENA'].unique(), key=get_fortnight_sort_key)

# Helper to format dataframes for display with Portuguese standards (. thousands, , decimals)
def format_df_for_display(df_to_format):
    df_disp = df_to_format.copy()
    if 'VALOR EMISSAO' in df_disp.columns:
        df_disp['VALOR EMISSAO'] = df_disp['VALOR EMISSAO'].apply(format_real)
    if 'VL/LITRO' in df_disp.columns:
        df_disp['VL/LITRO'] = df_disp['VL/LITRO'].apply(lambda x: f"R$ {x:,.3f}".replace(",", "X").replace(".", ",").replace("X", "."))
    if 'LITROS' in df_disp.columns:
        df_disp['LITROS'] = df_disp['LITROS'].apply(lambda x: f"{format_num(x, 2)} L")
    if 'KM RODADOS OU HORAS TRABALHADAS' in df_disp.columns:
        df_disp['KM RODADOS OU HORAS TRABALHADAS'] = df_disp['KM RODADOS OU HORAS TRABALHADAS'].apply(lambda x: f"{format_num(x, 0)} km")
    if 'KM/LITRO OU LITROS/HORA' in df_disp.columns:
        df_disp['KM/LITRO OU LITROS/HORA'] = df_disp['KM/LITRO OU LITROS/HORA'].apply(lambda x: f"{get_status_emoji_eff(x)} {format_num(x, 2)} km/L" if x > 0 else "0,00 km/L")
    if 'HODOMETRO OU HORIMETRO' in df_disp.columns:
        df_disp['HODOMETRO OU HORIMETRO'] = df_disp['HODOMETRO OU HORIMETRO'].apply(lambda x: f"{format_num(x, 0)} km")
    return df_disp

# --- TABS FOR NAVIGATION (returned by user demand, short & compact titles) ---
tab_oper, tab_efet, tab_mot, tab_est_pos, tab_audit = st.tabs([
    "📈 Custos & Volumes",
    "🚚 Eficiência Frota",
    "👨🏻‍✈️ Motoristas",
    "🌍 Estados & Postos",
    "🔍 Auditoria & Dados"
])

# -----------------------------------------------------------------------------
# TAB 1: CUSTOS E VOLUMES
# -----------------------------------------------------------------------------
with tab_oper:
    st.subheader("📈 Custos & Volumes Quinzenais")
    
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
        text=fq_summary['VALOR EMISSAO'].apply(format_real),
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
        text=fq_summary['LITROS'].apply(lambda x: f"{format_num(x, 0)} L"),
        textposition="top center",
        yaxis="y2"
    ))
    
    fig_fq_dual.update_layout(
        title=dict(text="Custos e Volumes por Quinzena", font=dict(size=14, color="#1e293b", family="Inter")),
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
    df_base_disp = df_global[['DATA TRANSACAO', 'PLACA', 'CATEGORIA', 'NOME MOTORISTA', 'TIPO COMBUSTIVEL', 'LITROS', 'VL/LITRO', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']].sort_values(by='DATA TRANSACAO', ascending=False)
    st.dataframe(
        format_df_for_display(df_base_disp),
        use_container_width=True,
        hide_index=True
    )

# -----------------------------------------------------------------------------
# PAGE 2: EFICIÊNCIA E DESEMPENHO DE VEÍCULOS
# -----------------------------------------------------------------------------
with tab_efet:
    st.subheader("🚚 Eficiência & Desempenho dos Veículos")
    
    # Charts Section (Aligned side-by-side above tables)
    col_ef1, col_ef2 = st.columns(2)
    
    df_diesel_eff = df_global[
        (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_global['KM/LITRO OU LITROS/HORA'] > 0) & 
        (df_global['KM/LITRO OU LITROS/HORA'] < 30)
    ]
    
    with col_ef1:
        st.markdown("#### Autonomia (km/L) por Placa")
        if not df_diesel_eff.empty:
            avg_plate_eff = df_diesel_eff.groupby(['PLACA', 'CATEGORIA'])['KM/LITRO OU LITROS/HORA'].mean().reset_index()
            avg_plate_eff = avg_plate_eff.sort_values(by='KM/LITRO OU LITROS/HORA', ascending=False)
            
            # Map colors using the Traffic Light System (Verde, Amarelo, Vermelho)
            colors_eff = []
            for val in avg_plate_eff['KM/LITRO OU LITROS/HORA']:
                if val > 8.5:
                    colors_eff.append('#16a34a') # Verde
                elif val >= 6.5:
                    colors_eff.append('#eab308') # Amarelo
                else:
                    colors_eff.append('#ef4444') # Vermelho
            
            fig_eff = px.bar(
                avg_plate_eff,
                x='PLACA',
                y='KM/LITRO OU LITROS/HORA',
                labels={'KM/LITRO OU LITROS/HORA': 'Consumo Médio (km/L)', 'PLACA': 'Placa'},
                title='Consumo de Diesel por Veículo',
                height=450
            )
            fig_eff.update_traces(marker_color=colors_eff)
            fig_eff.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
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
        st.markdown("#### Custo Operacional por KM (R$/km)")
        df_km_cost = df_global[
            (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            (df_global['KM RODADOS OU HORAS TRABALHADAS'] > 0)
        ]
        if not df_km_cost.empty:
            plate_km_cost = df_km_cost.groupby(['PLACA', 'CATEGORIA']).apply(
                lambda x: x['VALOR EMISSAO'].sum() / x['KM RODADOS OU HORAS TRABALHADAS'].sum()
            ).reset_index(name='R_KM')
            plate_km_cost = plate_km_cost.sort_values(by='R_KM', ascending=True)
            
            # Map colors using the Traffic Light System (Verde, Amarelo, Vermelho)
            colors_cost_km = []
            for val in plate_km_cost['R_KM']:
                if val < 0.85:
                    colors_cost_km.append('#16a34a') # Verde (Econômico)
                elif val <= 1.05:
                    colors_cost_km.append('#eab308') # Amarelo (Médio)
                else:
                    colors_cost_km.append('#ef4444') # Vermelho (Caro)
            
            fig_km = px.bar(
                plate_km_cost,
                x='PLACA',
                y='R_KM',
                labels={'R_KM': 'Custo Real (R$/km)', 'PLACA': 'Placa'},
                title='Custo Financeiro de Rodagem (R$ por KM)',
                height=450
            )
            fig_km.update_traces(marker_color=colors_cost_km, text=plate_km_cost['R_KM'].apply(format_real), textposition="auto")
            fig_km.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", yaxis=dict(tickprefix="R$ "))
            st.plotly_chart(fig_km, use_container_width=True)
        else:
            st.info("Quilometragem indisponível para cálculo de custo/km.")

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)

    # Table section below the charts as requested!
    st.markdown("#### 🗒️ Histórico de KM & Hodômetro por Quinzena")
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
    
    # Formatted version for visual comfort and Brazilian standards
    vehicle_fq_disp = vehicle_fq_metrics.copy()
    vehicle_fq_disp['km_rodados'] = vehicle_fq_disp['km_rodados'].apply(lambda x: f"{format_num(x, 0)} km")
    vehicle_fq_disp['hodometro_atual'] = vehicle_fq_disp['hodometro_atual'].apply(lambda x: f"{format_num(x, 0)} km")
    vehicle_fq_disp['litros'] = vehicle_fq_disp['litros'].apply(lambda x: f"{format_num(x, 1)} L")
    vehicle_fq_disp['gasto'] = vehicle_fq_disp['gasto'].apply(format_real)
    # Traffic light emoji prepended to autonomy in table
    vehicle_fq_disp['consumo_medio'] = vehicle_fq_disp['consumo_medio'].apply(lambda x: f"{get_status_emoji_eff(x)} {format_num(x, 2)} km/L")
    
    st.dataframe(
        vehicle_fq_disp.sort_values(by=['QUINZENA', 'PLACA'], key=lambda x: x.map(get_fortnight_sort_key) if x.name == 'QUINZENA' else x),
        column_config={
            "PLACA": "Placa do Veículo",
            "CATEGORIA": "Categoria",
            "QUINZENA": "Quinzena",
            "km_rodados": "KM Rodados",
            "hodometro_atual": "Hodômetro Atual (Max)",
            "litros": "Volume total",
            "gasto": "Gasto total",
            "consumo_medio": "Autonomia Média"
        },
        hide_index=True,
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# PAGE 3: PERFORMANCE DE MOTORISTAS
# -----------------------------------------------------------------------------
with tab_mot:
    st.subheader("👨🏻‍✈️ Performance & Custos por Motorista")
    
    col_m1, col_m2 = st.columns(2)
    
    # Spend by driver per fortnight
    driver_spend_fq = df_global.groupby(['NOME MOTORISTA', 'QUINZENA'])['VALOR EMISSAO'].sum().reset_index()
    driver_spend_fq = driver_spend_fq[driver_spend_fq['QUINZENA'].isin(all_quinzenas)]
    
    # Calculations for Driver's R$/KM (Cost per kilometer per driver) as requested!
    df_diesel_drv = df_global[
        (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
        (df_global['KM RODADOS OU HORAS TRABALHADAS'] > 0)
    ]
    
    with col_m1:
        st.markdown("#### Gasto Acumulado de Abastecimento (R$)")
        fig_driver_spend = px.bar(
            driver_spend_fq,
            y='NOME MOTORISTA',
            x='VALOR EMISSAO',
            color='QUINZENA',
            barmode='group',
            orientation='h',
            labels={'VALOR EMISSAO': 'Gasto Total', 'NOME MOTORISTA': 'Motorista', 'QUINZENA': 'Quinzena'},
            color_discrete_sequence=['#009a53', '#dc2626', '#64748b'],
            text=driver_spend_fq['VALOR EMISSAO'].apply(format_real),
            title='Gasto Acumulado de Abastecimento por Motorista',
            height=450
        )
        fig_driver_spend.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", xaxis=dict(tickprefix="R$ "))
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
        if not df_diesel_drv.empty:
            driver_km_cost = df_diesel_drv.groupby('NOME MOTORISTA').apply(
                lambda x: x['VALOR EMISSAO'].sum() / x['KM RODADOS OU HORAS TRABALHADAS'].sum()
            ).reset_index(name='R_KM')
            driver_km_cost = driver_km_cost.sort_values(by='R_KM', ascending=True)
            
            # Map colors using Traffic Light System for drivers
            colors_drv_cost = []
            for val in driver_km_cost['R_KM']:
                if val < 0.85:
                    colors_drv_cost.append('#16a34a') # Verde (Econômico)
                elif val <= 1.05:
                    colors_drv_cost.append('#eab308') # Amarelo
                else:
                    colors_drv_cost.append('#ef4444') # Vermelho
            
            fig_driver_km = px.bar(
                driver_km_cost,
                y='NOME MOTORISTA',
                x='R_KM',
                orientation='h',
                labels={'R_KM': 'Custo (R$/km)', 'NOME MOTORISTA': 'Motorista'},
                title='Custo Financeiro de Condução (R$ por KM)',
                height=450
            )
            fig_driver_km.update_traces(marker_color=colors_drv_cost, text=driver_km_cost['R_KM'].apply(format_real), textposition="auto")
            fig_driver_km.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", xaxis=dict(tickprefix="R$ "))
            st.plotly_chart(fig_driver_km, use_container_width=True)
        else:
            st.info("Dados de quilometragem indisponíveis para calcular R$/km por motorista.")

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
    
    st.markdown("#### 🗒️ Histórico Detalhado por Motorista")
    df_driver_disp = df_global[['DATA TRANSACAO', 'QUINZENA', 'NOME MOTORISTA', 'PLACA', 'CATEGORIA', 'TIPO COMBUSTIVEL', 'LITROS', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']].sort_values(by='DATA TRANSACAO', ascending=False)
    st.dataframe(
        format_df_for_display(df_driver_disp),
        use_container_width=True,
        hide_index=True
    )

# -----------------------------------------------------------------------------
# PAGE 4: DISTRIBUIÇÃO GEOGRÁFICA & POSTOS
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
            labels={'gasto_total': 'Gasto Total', 'UF': 'Estado'},
            color_discrete_sequence=['#009a53', '#dc2626', '#64748b'],
            text=state_summary['gasto_total'].apply(format_real),
            title='Investimento de Abastecimento por UF',
            height=450
        )
        fig_state.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", yaxis=dict(tickprefix="R$ "))
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
        st.markdown("#### Top 10 Postos por Gasto Acumulado (R$)")
        station_summary_spend = df_global.groupby('NOME ESTABELECIMENTO').agg(
            gasto_total=('VALOR EMISSAO', 'sum'),
            quantidade=('VALOR EMISSAO', 'count')
        ).reset_index().sort_values(by='gasto_total', ascending=False).head(10)
        
        fig_station_spend = px.bar(
            station_summary_spend,
            x='gasto_total',
            y='NOME ESTABELECIMENTO',
            orientation='h',
            labels={'gasto_total': 'Gasto Total', 'NOME ESTABELECIMENTO': 'Posto de Combustível'},
            title='Volume Financeiro por Posto (Top 10)',
            color_discrete_sequence=['#009a53'], # Verde Anjun
            height=450
        )
        fig_station_spend.update_traces(text=station_summary_spend['gasto_total'].apply(format_real), textposition="auto")
        fig_station_spend.update_layout(yaxis={'categoryorder': 'total ascending'}, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", xaxis=dict(tickprefix="R$ "))
        st.plotly_chart(fig_station_spend, use_container_width=True)

    st.markdown("<hr style='margin: 20px 0;'>", unsafe_allow_html=True)
    
    st.markdown("#### 🗒️ Resumo Geográfico por Estado (UF)")
    state_disp = state_summary.copy()
    state_disp['gasto_total'] = state_disp['gasto_total'].apply(format_real)
    state_disp['litros_totais'] = state_disp['litros_totais'].apply(lambda x: f"{format_num(x, 1)} L")
    state_disp['quantidade'] = state_disp['quantidade'].apply(lambda x: f"{format_num(x, 0)} abastecimentos")
    
    st.dataframe(
        state_disp,
        column_config={
            "UF": "Estado",
            "gasto_total": "Investimento Total",
            "litros_totais": "Litros Consumidos",
            "quantidade": "Qtd. Abastecimentos"
        },
        hide_index=True,
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# PAGE 5: AUDITORIA E BASE DE DADOS
# -----------------------------------------------------------------------------
with tab_audit:
    st.subheader("🔍 Auditoria de Inconsistências & Tabela Geral")
    
    # 1. Gráficos e Tabelas de Inconsistências (Renderizados Acima!)
    col_aud1, col_aud2 = st.columns(2)
    
    with col_aud1:
        # Renamed to "Abastecimento com km zerado" and checked with Arla same-day exclude logic!
        anomalies_zero_km_raw = df_global[
            (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            (df_global['KM RODADOS OU HORAS TRABALHADAS'] == 0)
        ]
        
        # Apply the business rule: do not show if Arla was refueled for the same vehicle on the same day
        if not anomalies_zero_km_raw.empty:
            has_arla_same_day = anomalies_zero_km_raw.apply(lambda r: (r['DATA'], r['PLACA']) in arla_keys, axis=1)
            anomalies_zero_km = anomalies_zero_km_raw[~has_arla_same_day]
        else:
            anomalies_zero_km = anomalies_zero_km_raw
            
        st.markdown("#### 🚨 Abastecimento com km zerado")
        if not anomalies_zero_km.empty:
            st.warning(f"Identificados {len(anomalies_zero_km)} abastecimentos de Diesel com KM zerada no mesmo dia (sem Arla).")
            
            # Interactive Selection Row (Corrected single-row selection mode format with dash!)
            selected_zero_km = st.dataframe(
                format_df_for_display(anomalies_zero_km[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'LITROS', 'VALOR EMISSAO', 'NOME ESTABELECIMENTO']]),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="zero_km_select"
            )
        else:
            st.success("✅ Nenhum abastecimento de Diesel com KM zerado encontrado (ou desconsiderado por abastecimento de Arla no mesmo dia).")
            selected_zero_km = None
            
    with col_aud2:
        # Rendimento atípico updated to < 4 km/L or > 12 km/L
        anomalies_eff = df_global[
            (df_global['TIPO COMBUSTIVEL'] == 'DIESEL S-10 COMUM') & 
            ((df_global['KM/LITRO OU LITROS/HORA'] < 4) | (df_global['KM/LITRO OU LITROS/HORA'] > 12)) &
            (df_global['KM/LITRO OU LITROS/HORA'] != 0)
        ]
        st.markdown("#### ⚠️ Rendimento Atípico (< 4 km/L ou > 12 km/L)")
        if not anomalies_eff.empty:
            st.error(f"Identificados {len(anomalies_eff)} abastecimentos fora da faixa padrão (< 4 ou > 12 km/L).")
            
            # Interactive Selection Row (Corrected single-row selection mode format!)
            selected_eff = st.dataframe(
                format_df_for_display(anomalies_eff[['DATA TRANSACAO', 'PLACA', 'NOME MOTORISTA', 'KM/LITRO OU LITROS/HORA', 'LITROS', 'VALOR EMISSAO']]),
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
        clicked_transaction_date = anomalies_zero_km.iloc[row_idx]['DATA TRANSACAO']
        clicked_plate_num = anomalies_zero_km.iloc[row_idx]['PLACA']
        
    elif selected_eff and "selection" in selected_eff and "rows" in selected_eff["selection"] and selected_eff["selection"]["rows"]:
        row_idx = selected_eff["selection"]["rows"][0]
        clicked_transaction_date = anomalies_eff.iloc[row_idx]['DATA TRANSACAO']
        clicked_plate_num = anomalies_eff.iloc[row_idx]['PLACA']

    st.markdown("<hr style='margin: 25px 0;'>", unsafe_allow_html=True)
    
    st.markdown("#### 📂 Tabela de Dados Geral")
    
    if clicked_transaction_date and clicked_plate_num:
        st.markdown(f'<div class="detail-box">🔍 <b>Filtro Ativo:</b> Exibindo o registro de <b>{clicked_plate_num}</b> em {clicked_transaction_date}. Clique novamente sobre a linha da tabela de inconsistências para limpar.</div>', unsafe_allow_html=True)
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
        format_df_for_display(df_base_show[display_cols].sort_values(by='DATA TRANSACAO', ascending=False)),
        use_container_width=True,
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
