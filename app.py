import streamlit as st
import datetime
import json
import re
import unicodedata
import pandas as pd
from difflib import SequenceMatcher
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Central do Closer - Sessão 1A1", page_icon="📊", layout="wide")

# CSS para harmonização visual: Títulos menores e textos do roteiro legíveis
st.markdown("""
    <style>
    h1 {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        margin-bottom: 0.5rem !important;
    }
    h2 {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        color: #1e293b !important;
        margin-top: 1.2rem !important;
        margin-bottom: 0.6rem !important;
    }
    h3 {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
        margin-top: 1rem !important;
        margin-bottom: 0.4rem !important;
    }
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
        font-size: 0.85rem;
        font-weight: 600;
        color: #475569;
        margin-bottom: 4px;
        white-space: nowrap;
    }
    .metric-card-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.2;
    }
    .metric-card-sub {
        font-size: 0.78rem;
        color: #64748b;
        margin-top: 4px;
        font-weight: 500;
    }
    .playbook-box {
        background-color: #f8fafc;
        border-left: 4px solid #2563eb;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .playbook-script {
        font-size: 1.02rem !important;
        font-style: normal;
        color: #0f172a;
        background-color: #ffffff;
        padding: 16px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        line-height: 1.65;
    }
    </style>
""", unsafe_allow_html=True)

def remover_acentos(texto):
    if not isinstance(texto, str):
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

def similaridade(a, b):
    return SequenceMatcher(None, remover_acentos(a), remover_acentos(b)).ratio()

def obter_coluna_case_insensitive(df, col_name):
    if df.empty:
        return None
    for col in df.columns:
        if str(col).strip().lower() == col_name.strip().lower():
            return col
    return None

@st.cache_resource(ttl=3600)
def obter_credenciais_google(creds_dict_json):
    creds_dict = json.loads(creds_dict_json)
    if "private_key" in creds_dict:
        creds_dict["private_key"] = str(creds_dict["private_key"]).replace("\\n", "\n")
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/spreadsheets.readonly'
    ]
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

@st.cache_data(ttl=600, show_spinner=False)
def buscar_dados_google(_credentials, email_equipe, inicio_data, fim_data, id_planilha):
    service_cal = build('calendar', 'v3', credentials=_credentials)
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
    eventos_filtrados = [e for e in events if "diagnóstico gratuito de carreira" in e.get('summary', '').lower()]

    df_planilha = pd.DataFrame()
    try:
        service_sheets = build('sheets', 'v4', credentials=_credentials)
        sheet_result = service_sheets.spreadsheets().values().get(
            spreadsheetId=id_planilha, range="Base_Master!A1:AA1000"
        ).execute()
        values = sheet_result.get('values', [])
        if values:
            # Garante limpeza dos nomes das colunas
            cols = [str(c).strip() for c in values[0]]
            df_planilha = pd.DataFrame(values[1:], columns=cols)
    except Exception:
        pass

    return eventos_filtrados, df_planilha

if "historico_analises" not in st.session_state:
    st.session_state["historico_analises"] = []

openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "")
ID_PLANILHA_REAL = "1LsWvNf3XBmmNnICtP2BLKl3-NN7yAIF2WV0pgqw3onU"

# Sidebar - Configurações
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
            creds_json = json.dumps(dict(st.secrets["google_credentials"]))
            credentials = obter_credenciais_google(creds_json)
            
            with st.spinner("⚡ Carregando dados da Agenda e Planilha..."):
                buscar_dados_google.clear()
                eventos, df_planilha = buscar_dados_google(credentials, email_equipe, inicio_data, fim_data, ID_PLANILHA_REAL)
                st.session_state["eventos_carregados"] = eventos
                st.session_state["dados_planilha"] = df_planilha

            st.sidebar.success(f"Encontrados {len(st.session_state['eventos_carregados'])} Diagnósticos!")
        else:
            st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets.")
    except Exception as e:
        st.sidebar.error(f"Erro ao sincronizar: {str(e)}")

# ESTRUTURA DE ABAS PRINCIPAIS DO APP
tab1, tab2, tab3 = st.tabs([
    "📚 Roteiros & Playbook de Bolso", 
    "📊 Auditorias & Indicadores", 
    "👥 Desempenho & Ranking por Closer"
])

# =================================----------------=============
# ABA 1: ROTEIROS & PLAYBOOK DE BOLSO
# =================================----------------=============
with tab1:
    st.header("📖 Roteiro de Bolso - Diagnóstico de Carreira")
    st.caption("Consulte na íntegra as falas, devoluções de Raio-X por notas, slides e quebras de objeção.")
    
    p_tab1, p_tab2, p_tab3 = st.tabs([
        "📍 Bloco 1: Acolhimento & Raio-X", 
        "📍 Bloco 2: Apresentação & Slides", 
        "📍 Bloco 3: Oferta & Quebra de Objeções"
    ])
    
    with p_tab1:
        st.title("Bloco 1: Acolhimento & Raio-X")
        
        st.subheader("1. Quebrando o Gelo & Acolhimento")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Oi, (nome da pessoa)! Tudo bem?"<br>"De onde você fala?"<br><br><b>Acolhimento:</b> "Vi no seu LinkedIn que o seu último trabalho foi na [Empresa/Setor], né?"<br><br><b>Expectativa:</b> "Me conta um pouquinho de como está o seu momento atual?"<br>"E o que você está buscando para os próximos passos da sua carreira?"</div></div>', unsafe_allow_html=True)
        
        st.subheader("2. Acordo Inicial do Raio-X")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"O objetivo desse diagnóstico é detalharmos melhor o seu cenário para eu entender as suas maiores dificuldades para conseguir emprego, e para isso eu vou te fazer algumas perguntas para você me responder com notas de 0 a 10 para avaliarmos o seu momento. Não precisa justificar o motivo da nota por enquanto, depois eu vou te mostrar um gráfico das suas respostas e nós vamos falar mais sobre isso. Eu preciso que você seja BRUTALMENTE SINCERO(A). Posso confiar na sua palavra?"</div></div>',
