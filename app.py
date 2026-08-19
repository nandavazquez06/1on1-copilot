import streamlit as st
import datetime
import json

st.set_page_config(page_title="Dashboard de Feedbacks Ricarreira - Sessão 1A1", page_icon="📊", layout="wide")
st.title("📊 Dashboard de Feedbacks - Sessão 1A1 (Ricarreira)")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

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
[00:15] Lead: Olá! Tudo ótimo, assisti a imersão do Ricardo e o conteúdo do YouTube da Ricarreira e já queria tirar dúvidas sobre o CRH.
[00:30] Closer: Excelente. Hoje vamos analisar o seu momento atual de carreira, entender sua ancoragem acadêmica no LinkedIn e ver exatamente quanto tempo e dinheiro você está deixando na mesa com a nossa calculadora 'Tempo é Dinheiro'.
[02:00] Closer: Analisando seu perfil, vejo que você tem uma bagagem incrível...
[05:00] Closer: Apresentando a nossa proposta para o programa CRH: A Âncora 1 é de 12x de R$ 997 ou R$ 9.500 à vista. Comprando hoje na nossa condição de urgência, fica por R$ 8.500 à vista ou R$ 5.000 no plano especial ao vivo.
[10:00] Lead: Perfeito! Vou passar o cartão agora para garantir minha vaga no CRH!
[12:00] Closer: Excelente! Seja muito bem-vinda ao programa CRH da Ricarreira!"""
    
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
            with st.spinner("🤖 Analisando a reunião da Ricarreira com base na metodologia FHT..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    
                    prompt_sistema = """Você é um auditor sênior de chamadas High Ticket da Ricarreira (programa CRH, fundado pelo especialista Ricardo).
Sua missão é auditar o desempenho do closer na sessão 1A1, utilizando a metodologia FHT (Formula High Ticket).

REGRAS RÍGIDAS DE NOTA & CONVERSÃO:
1. IDENTIFICAÇÃO DE CONVERSÃO:
   - Se a transcrição/descrição indicar que o LEAD COMPROU / CONVERTEU (ex: passou cartão, enviou PIX, aceitou a proposta ou disse 'vou fechar/comprar'), a nota final OBRIGATORIAMENTE DEVE SER ENTRE 8.0 E 10.0.
   - O primeiro item da sua resposta DEVE SER O STATUS DA SESSÃO em destaque:
     `🟢 STATUS: LEAD CONVERTIDO` ou `🔴 STATUS: NÃO CONVERTIDO`.

2. LÓGICA DE PONTUAÇÃO:
   - **LEAD CONVERTIDO (Nota 8.0 a 10.0):** Reconheça o sucesso comercial. Mesmo se o closer tiver pulado alguma etapa por conta da rapidez e prontidão do lead aquecido da Ricarreira, valorize a eficácia de vendas.
   - **NÃO CONVERTIDO + ROTEIRO BOM (Nota 6.5 a 8.0):** Se o lead não comprou por motivo financeiro/imprevisto pessoal, mas o closer executou a estrutura FHT com maestria, pontue bem o processo, mas identifique os gatilhos finais faltantes.
   - **NÃO CONVERTIDO + ROTEIRO FRACO (Nota 0 a 6.0):** Se o closer cometeu erros de condução, não ancorou preços e perdeu o fechamento.

3. PILARES FHT AVALIADOS:
   - Diagnóstico do momento profissional do Lead
   - Ancoragem Acadêmica & LinkedIn
   - Calculadora 'Tempo é Dinheiro'
   - Ancoragem Dupla de Preço (Âncora 1: 12x R$ 997 / R$ 9.500 à vista -> Condição Urgência: R$ 8.500 à vista ou R$ 5.000 ao vivo)
   - Prova Social / Garantia Condicional de 51 dias
   - Pitch de Fechamento e Contorno de Objeções High Ticket

ESTRUTURA DE RESPOSTA OBRIGATÓRIA (Markdown):
### 🟢 STATUS: LEAD CONVERTIDO  *(ou 🔴 STATUS: NÃO CONVERTIDO)*

**Resumo Executivo & Nota do Closer: [X.X / 10]**
*(Explicar detalhadamente a nota considerando o resultado de conversão e a aderência ao roteiro FHT)*

---
- **🎯 Pontos Fortes da Sessão**
- **🚨 Pontos de Melhoria Críticos**
- **💡 Plano de Ação para o Próximo Treinamento**
"""
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": f"Empresa: Ricarreira\nLead: {nome_lead}\nClosers: {closers_nomes}\n\nTranscrição/Dados da Sessão:\n{transcricao_texto}"}
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
