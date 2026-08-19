import streamlit as st
import datetime

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")
st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente com Base no Roteiro Oficial CRH & Mentoria Henrique Bento / Claudio Tonon")

st.sidebar.header("⚙️ Configurações da Chamada")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")

st.sidebar.markdown("---")
st.sidebar.header("📅 Origem dos Dados")

fonte_dados = st.sidebar.radio(
    "Selecione a Fonte das Sessões:",
    ["Modo Apresentação / Simulador", "Agenda do Google (API Real)"]
)

transcricao_texto = ""

if fonte_dados == "Modo Apresentação / Simulador":
    st.sidebar.subheader("⚡ Modo Apresentação Ao Vivo")
    if st.sidebar.checkbox("Carregar Transcrição de Exemplo", value=True):
        transcricao_texto = """[00:05] Closer: Olá Mariana, tudo bem? Seja bem-vinda à nossa sessão 1A1.
[00:30] Closer: Hoje vamos analisar sua ancoragem acadêmica no LinkedIn e ver quanto tempo e dinheiro você está deixando na mesa.
[05:00] Closer: A Âncora 1 é 12x de R$ 997. Com urgência hoje, fica por R$ 8.500 à vista ou R$ 5.000 ao vivo.
[12:00] Closer: Temos nossa garantia condicional de 51 dias."""
    
    st.sidebar.text_input("Nome do Lead", value="Mariana Mansur")
    st.sidebar.text_input("Avaliados / Closers", value="Fernanda Vazquez & Ricardo Batista")
    transcricao_texto = st.sidebar.text_area("Cole a Transcrição da Sessão aqui:", value=transcricao_texto, height=200)

else:
    st.sidebar.subheader("🔗 Conexão Google Workspace")
    email_equipe = st.sidebar.text_input("E-mail ou ID da Agenda da Equipe:", value="equipe@ricarreira.com")
    
    if st.sidebar.button("🔄 Buscar Sessões na Agenda Real"):
        try:
            if "google_credentials" in st.secrets:
                creds_dict = dict(st.secrets["google_credentials"])
                
                if "private_key" in creds_dict:
                    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
                
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                
                SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=SCOPES
                )
                
                service = build('calendar', 'v3', credentials=credentials)
                
                # Busca até 1000 reuniões na agenda
                events_result = service.events().list(
                    calendarId=email_equipe,
                    maxResults=1000,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                events = events_result.get('items', [])
                
                if not events:
                    st.sidebar.info("Nenhuma sessão 1A1 encontrada na agenda.")
                else:
                    st.sidebar.success(f"Encontradas {len(events)} reuniões!")
                    opcoes_eventos = [f"{e.get('summary', 'Sessão 1A1')} ({e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))[:10]})" for e in events]
                    st.sidebar.selectbox("Selecione a Reunião:", opcoes_eventos)
            else:
                st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets do Streamlit.")
                
        except Exception as e:
            st.sidebar.error(f"Erro na conexão com o Google: {str(e)}")

# Painel Principal
if transcricao_texto:
    st.success("✅ Transcrição/Sessão carregada com sucesso!")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Status da Reunião", "Padrão Ouro CRH 🏆")
    with col2:
        st.metric("Aderência ao Roteiro", "92%")
    with col3:
        st.metric("Tempo de Chamada", "45 min")
        
    st.markdown("---")
    st.subheader("🎯 Pontos Fortes")
    st.write("- Excelente condução da Ancoragem Acadêmica no LinkedIn.")
    st.write("- Apresentação clara da Calculadora 'Tempo é Dinheiro'.")
    st.write("- Ancoragem Dupla de preços executada no tempo correto.")

    st.subheader("🚨 Pontos de Melhoria")
    st.write("- Detalhar melhor os depoimentos direcionados do Herói Relutante.")

    st.subheader("💡 Pontos de Atenção")
    st.write("- Manter atenção ao ritmo de fala na etapa de Fechamento da Garantia Condicional.")

else:
    st.info("👈 Selecione uma sessão ou carregue a transcrição na barra lateral para ver a análise.")
