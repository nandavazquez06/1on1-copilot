import streamlit as st
import datetime
import json

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")
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
    if st.sidebar.checkbox("Carregar Transcrição de Exemplo", value=True):
        nome_lead = "Mariana Mansur"
        closers_nomes = "Fernanda Vazquez & Ricardo Batista"
        transcricao_texto = """[00:05] Closer: Olá Mariana, tudo bem? Seja bem-vinda à nossa sessão 1A1 da Ricarreira.
[00:15] Lead: Olá! Tudo ótimo.
[00:30] Closer: Excelente. Hoje vamos analisar o seu momento atual de carreira, entender sua ancoragem acadêmica no LinkedIn e ver exatamente quanto tempo e dinheiro você está deixando na mesa com a nossa calculadora 'Tempo é Dinheiro'.
[02:00] Closer: Analisando seu perfil, vejo que você tem uma bagagem incrível, mas seu posicionamento acadêmico e LinkedIn ainda não refletem seu valor sênior...
[05:00] Closer: Apresentando a nossa proposta: A Âncora 1 é de 12x de R$ 997 ou R$ 9.500 à vista. Comprando hoje na nossa condição de urgência, fica por R$ 8.500 à vista ou R$ 5.000 no plano especial ao vivo.
[10:00] Lead: Gostei bastante da proposta e do roteiro do Herói Relutante!
[12:00] Closer: Perfeito! Temos nossa garantia condicional de 51 dias para você aplicar o método sem risco."""
    
    nome_lead = st.sidebar.text_input("Nome do Lead", value=nome_lead)
    closers_nomes = st.sidebar.text_input("Avaliados / Closers", value=closers_nomes)
    transcricao_texto = st.sidebar.text_area("Cole a Transcrição da Sessão aqui:", value=transcricao_texto, height=200)

else:
    st.sidebar.subheader("🔗 Conexão Google Workspace")
    
    id_agenda_padrao = "c_a962f63fcda4c9ee4743b4876d57e5271e457be2e914af39e1227aa0dcf1ca31@group.calendar.google.com"
    email_equipe = st.sidebar.text_input("ID da Agenda da Equipe:", value=id_agenda_padrao)
    
    if "eventos_carregados" not in st.session_state:
        st.session_state["eventos_carregados"] = []

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
                
                events_result = service.events().list(
                    calendarId=email_equipe,
                    maxResults=1000,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                events = events_result.get('items', [])
                
                if not events:
                    st.sidebar.info("Nenhuma sessão 1A1 encontrada na agenda.")
                    st.session_state["eventos_carregados"] = []
                else:
                    st.session_state["eventos_carregados"] = events
                    st.sidebar.success(f"Encontradas {len(events)} reuniões!")
            else:
                st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets do Streamlit.")
                
        except Exception as e:
            st.sidebar.error(f"Erro na conexão com o Google: {str(e)}")

    if st.session_state["eventos_carregados"]:
        events = st.session_state["eventos_carregados"]
        opcoes_map = {}
        for e in events:
            nome = e.get('summary', 'Sessão 1A1')
            data = e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))[:10]
            label = f"{nome} ({data})"
            opcoes_map[label] = e

        evento_sel_label = st.sidebar.selectbox("Selecione a Reunião:", list(opcoes_map.keys()))
        evento_obj = opcoes_map[evento_sel_label]

        nome_lead = evento_obj.get('summary', 'Sessão 1A1')
        descricao_evento = evento_obj.get("description", "")
        
        # Pega a transcrição da descrição do evento ou observações
        transcricao_texto = descricao_evento if descricao_evento.strip() else f"Sessão: {nome_lead}\nData: {evento_obj.get('start', {}).get('dateTime', '')}\nParticipantes: {', '.join([p.get('email', '') for p in evento_obj.get('attendees', [])])}"
        
        st.sidebar.write("---")
        st.sidebar.markdown(f"**Lead Selecionado:** {nome_lead}")

# Painel Principal
st.subheader(f"📋 Analisando: {nome_lead if nome_lead else 'Nenhuma sessão selecionada'}")

if transcricao_texto:
    with st.expander("📄 Ver Transcrição / Detalhes da Reunião Selecionada"):
        st.text_area("Conteúdo da Sessão:", value=transcricao_texto, height=150, disabled=True)

    if st.button("🚀 Gerar Análise de Performance com IA"):
        if not openai_key:
            st.error("🔑 Por favor, insira sua OpenAI API Key na barra lateral para gerar o diagnóstico com IA.")
        else:
            with st.spinner("🤖 Analisando a reunião com base no Roteiro Oficial CRH & Mentoria Bento/Tonon..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    
                    prompt_sistema = """Você é um especialista e auditor sênior de chamadas de vendas do método CRH (Mentoria Henrique Bento e Claudio Tonon).
Sua tarefa é analisar rigorosamente a transcrição/detalhes da sessão 1A1 fornecida.

Avalie detalhadamente os seguintes pilares do Roteiro CRH:
1. Conexão Inicial e Diagnóstico de Carreira
2. Ancoragem Acadêmica & LinkedIn
3. Uso da Calculadora "Tempo é Dinheiro"
4. Apresentação do Preço e Ancoragem Dupla (Âncora 1: 12x R$ 997 / R$ 9.500 à vista -> Condição Urgência: R$ 8.500 à vista ou R$ 5.000 ao vivo)
5. Utilização de Depoimentos / Herói Relutante e Garantia Condicional de 51 dias
6. Pitch de Fechamento e Contorno de Objeções

Responda em formato Markdown estruturado com:
- **Resumo Executivo & Nota do Closer (0 a 10)**
- **🎯 Pontos Fortes (Minucioso, com exemplos do texto)**
- **🚨 Pontos de Melhoria Críticos (Erros no roteiro ou gatilhos perdidos)**
- **💡 Ações Práticas Recomendadas para o Próximo Treinamento**
"""
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": f"Lead/Reunião: {nome_lead}\nClosers: {closers_nomes}\n\nTranscrição/Dados da Sessão:\n{transcricao_texto}"}
                        ],
                        temperature=0.3
                    )
                    
                    analise_ia = response.choices[0].message.content
                    st.markdown("---")
                    st.markdown(analise_ia)
                    
                except Exception as err:
                    st.error(f"Erro ao chamar a OpenAI API: {str(err)}")

else:
    st.info("👈 Selecione uma sessão na barra lateral para carregar os dados e rodar a análise.")
