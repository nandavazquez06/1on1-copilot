import streamlit as st
import json
import os

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Feedbacks - Sessão 1A1",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente com Base no Roteiro Oficial CRH & Mentoria Henrique Bento / Claudio Tonon")

# Sidebar - Configurações e Fonte de Dados
st.sidebar.header("⚙️ Configurações da Chamada")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")

st.sidebar.markdown("---")
st.sidebar.header("📅 Origem dos Dados")

fonte_dados = st.sidebar.radio(
    "Selecione a Fonte das Sessões:",
    ["Modo Apresentação / Simulador", "Agenda do Google (API Real)"]
)

transcricao_texto = ""
nome_lead = ""
closers_nomes = ""

if fonte_dados == "Modo Apresentação / Simulador":
    st.sidebar.subheader("⚡ Modo Apresentação Ao Vivo")
    usar_exemplo = st.sidebar.checkbox("Carregar Transcrição de Exemplo", value=True)
    
    if usar_exemplo:
        nome_lead = "Mariana Mansur"
        closers_nomes = "Fernanda Vazquez & Ricardo Batista"
        transcricao_texto = """[00:05] Closer: Olá Mariana, tudo bem? Seja bem-vinda à nossa sessão 1A1 da Ricarreira.
[00:15] Lead: Olá! Tudo ótimo.
[00:30] Closer: Excelente. Hoje vamos analisar o seu momento atual de carreira, entender sua ancoragem acadêmica no LinkedIn e ver exatamente quanto tempo e dinheiro você está deixando na mesa com a nossa calculadora 'Tempo é Dinheiro'.
[02:00] Closer: Analisando seu perfil, vejo que você tem uma bagagem incrível...
[05:00] Closer: Apresentando a nossa proposta: A Âncora 1 é de 12x de R$ 997 ou R$ 9.500 à vista. Comprando hoje na nossa condição de urgência, fica por R$ 8.500 à vista ou R$ 5.000 no plano especial ao vivo.
[10:00] Lead: Gostei bastante da proposta e do roteiro do Herói Relutante!
[12:00] Closer: Perfeito! Temos nossa garantia condicional de 51 dias."""

    st.sidebar.text_input("Nome do Lead", value=nome_lead)
    st.sidebar.text_input("Avaliados / Closers", value=closers_nomes)
    transcricao_texto = st.sidebar.text_area("Cole a Transcrição da Sessão aqui:", value=transcricao_texto, height=200)

else:
    st.sidebar.subheader("🔗 Conexão Google Workspace")
    email_equipe = st.sidebar.text_input("E-mail da Agenda da Equipe:", value="equipe@ricarreira.com")
    
    if st.sidebar.button("🔄 Buscar Sessões na Agenda Real"):
        try:
            # Tratamento inteligente do JSON de credenciais para evitar erros de formatação
            if "google_credentials" in st.secrets:
                raw_creds = st.secrets["google_credentials"]
                
                # Se for string, limpa quebras e caracteres especiais
                if isinstance(raw_creds, str):
                    # Tenta carregar limpando formatação incorreta
                    clean_json = raw_creds.strip()
                    creds_dict = json.loads(clean_json, strict=False)
                else:
                    creds_dict = dict(raw_creds)
                
                # Tenta importar bibliotecas do Google
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                
                SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict, scopes=SCOPES
                )
                
                service = build('calendar', 'v3', credentials=credentials)
                
                # Busca eventos na agenda
                events_result = service.events().list(
                    calendarId=email_equipe,
                    maxResults=10,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                events = events_result.get('items', [])
                
                if not events:
                    st.sidebar.info("Nenhuma sessão 1A1 encontrada na agenda próxima.")
                else:
                    st.sidebar.success(f"Encontradas {len(events)} reuniões!")
                    opcoes_eventos = [f"{e.get('summary', 'Sessão 1A1')} ({e.get('start', {}).get('dateTime', '')[:10]})" for e in events]
                    evento_sel = st.sidebar.selectbox("Selecione a Reunião:", opcoes_eventos)
                    
            else:
                st.sidebar.error("Credenciais do Google não encontradas nas Secrets do Streamlit.")
                
        except Exception as e:
            st.sidebar.error(f"Erro na conexão com o Google: {str(e)}")
            st.sidebar.info("💡 Dica: Verifique se a agenda deste e-mail foi compartilhada com o e-mail da Conta de Serviço do Google Cloud.")

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
    st.info("👈 Insira a API Key e selecione uma sessão na barra lateral para iniciar a análise.")
