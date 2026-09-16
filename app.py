import streamlit as st
import datetime
import json
import re
import unicodedata
import pandas as pd
from difflib import SequenceMatcher
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")

# CSS para garantir que os cards e textos fiquem 100% legíveis sem cortes
st.markdown("""
    <style>
    .metric-container {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 20px;
    }
    .metric-card-custom {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        flex: 1;
        text-align: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .metric-card-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: #475569;
        margin-bottom: 4px;
        white-space: nowrap;
    }
    .metric-card-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.2;
    }
    .metric-card-sub {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 4px;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

def remover_acentos(texto):
    if not isinstance(texto, str):
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

def similaridade(a, b):
    return SequenceMatcher(None, remover_acentos(a), remover_acentos(b)).ratio()

if "historico_analises" not in st.session_state:
    st.session_state["historico_analises"] = []

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "")
ID_PLANILHA_REAL = "1LsWvNf3XBmmNnICtP2BLKl3-NN7yAIF2WV0pgqw3onU"

# Sidebar
st.sidebar.header("⚙️ Configurações do App")
if openai_key:
    st.sidebar.success("🔑 OpenAI API Key conectada!")
else:
    openai_key = st.sidebar.text_input("OpenAI API Key (Manual)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("📅 Filtro por Período")

email_equipe = st.sidebar.text_input("ID da Agenda da Equipe:", value=id_agenda_secrets)

periodo_selecionado = st.sidebar.selectbox(
    "Selecione o Período:",
    ["Esta Semana (Semana Atual)", "Semana Passada", "Personalizado (Escolher Datas)"]
)

hoje = datetime.date.today()

if periodo_selecionado == "Esta Semana (Semana Atual)":
    inicio_data = hoje - datetime.timedelta(days=hoje.weekday())
    fim_data = inicio_data + datetime.timedelta(days=6)
elif periodo_selecionado == "Semana Passada":
    inicio_data = hoje - datetime.timedelta(days=hoje.weekday() + 7)
    fim_data = inicio_data + datetime.timedelta(days=6)
else:
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        inicio_data = st.date_input("De:", value=hoje - datetime.timedelta(days=7))
    with col_d2:
        fim_data = st.date_input("Até:", value=hoje)

st.sidebar.caption(f"📍 Buscando entre: **{inicio_data.strftime('%d/%m/%Y')}** e **{fim_data.strftime('%d/%m/%Y')}**")

if "eventos_carregados" not in st.session_state:
    st.session_state["eventos_carregados"] = []

if "dados_planilha" not in st.session_state:
    st.session_state["dados_planilha"] = pd.DataFrame()

if st.sidebar.button("🔄 Sincronizar Agenda & Tabela Master", use_container_width=True):
    try:
        if "google_credentials" in st.secrets:
            creds_dict = dict(st.secrets["google_credentials"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = str(creds_dict["private_key"]).replace("\\n", "\n")
            
            SCOPES = [
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/spreadsheets.readonly'
            ]
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            
            # Agenda
            service_cal = build('calendar', 'v3', credentials=credentials)
            time_min = datetime.datetime.combine(inicio_data, datetime.time.min).isoformat() + 'Z'
            time_max = datetime.datetime.combine(fim_data, datetime.time.max).isoformat() + 'Z'
            
            events_result = service_cal.events().list(
                calendarId=email_equipe,
                timeMin=time_min,
                timeMax=time_max,
                q="Diagnóstico Gratuito de Carreira",
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            st.session_state["eventos_carregados"] = [
                e for e in events if "diagnóstico gratuito de carreira" in e.get('summary', '').lower()
            ]

            # Planilha Master
            try:
                service_sheets = build('sheets', 'v4', credentials=credentials)
                sheet_result = service_sheets.spreadsheets().values().get(
                    spreadsheetId=ID_PLANILHA_REAL, range="Base_Master!A1:AA1000"
                ).execute()
                values = sheet_result.get('values', [])
                if values:
                    df = pd.DataFrame(values[1:], columns=values[0])
                    st.session_state["dados_planilha"] = df
            except Exception as e_sheet:
                st.sidebar.warning(f"Agenda OK, erro planilha: {str(e_sheet)}")

            st.sidebar.success(f"Encontrados {len(st.session_state['eventos_carregados'])} Diagnósticos!")
        else:
            st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets.")
    except Exception as e:
        st.sidebar.error(f"Erro ao sincronizar: {str(e)}")

# -------------------------------------------------------------
# 1. CARDS DE DESEMPENHO E CONVERSÃO
# -------------------------------------------------------------
historico = st.session_state["historico_analises"]
total_periodo = len(st.session_state["eventos_carregados"])
total_analisadas = len(historico)

vendas_ato = sum(1 for item in historico if "Ato" in str(item.get("status_venda", "")))
vendas_fup = sum(1 for item in historico if "FUP" in str(item.get("status_venda", "")))
total_convertidos = vendas_ato + vendas_fup

taxa_conversao = (total_convertidos / total_analisadas * 100) if total_analisadas > 0 else 0.0
media_nota = (sum(item.get("nota", 0.0) for item in historico) / total_analisadas) if total_analisadas > 0 else 0.0

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f'<div class="metric-card-custom"><div class="metric-card-title">📅 Sessões Agendadas</div><div class="metric-card-value">{total_periodo}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card-custom"><div class="metric-card-title">📊 Auditadas pela IA</div><div class="metric-card-value">{total_analisadas}</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card-custom"><div class="metric-card-title">🟢 Convertidos</div><div class="metric-card-value">{total_convertidos}</div><div class="metric-card-sub">{vendas_ato} Ato | {vendas_fup} FUP
