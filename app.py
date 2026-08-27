import streamlit as st
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks Ricarreira - Sessão 1A1", page_icon="📊", layout="wide")
st.title("📊 Dashboard de Feedbacks - Sessão 1A1 (Ricarreira)")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

# Puxa configurações automáticas das Secrets
openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "c_a962f63fcda4c9ee4743b4876d57e5271e457be2e914af39e1227aa0dcf1ca31@group.calendar.google.com")

st.sidebar.header("⚙️ Configurações do App")
if openai_key:
    st.sidebar.success("🔑 OpenAI API Key conectada!")
else:
    openai_key = st.sidebar.text_input("OpenAI API Key (Manual)", type="password")

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
    
    email_equipe = st.sidebar.text_input("ID da Agenda da Equipe:", value=id_agenda_secrets)
    
    if "eventos_carregados" not in st.session_state:
        st.session_state["eventos_carregados"] = []

    if st.sidebar.button("🔄 Buscar Sessões na Agenda Real"):
        try:
            # Reconstrução nativa e segura da Service Account
            private_key_lines = [
                "-----BEGIN PRIVATE KEY-----",
                "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC8eNmA31N045f/",
                "TShTjZGMLKafRpgWhUXm86xTDNMulQw0e08nv98C3J69zp0GrPxdVZuTSbJ0SqHa",
                "Af38NT19NHSLuORN0gMswvFl3grLNj8mfm6JYJcQdUuPctb9q0KgOstSS/br9tUe",
                "g6oFuqH9hQy3n0p2TUgVTbYwRDG82IdKs2y8Q5+leE7/T9TKse/mVuTxmnkxcWIm",
                "I9LoiN94pHDp1xMCckOvDXs0Mxe+1YGnFnj8iaop/mD+VUwfsppaiYnJMxWpnzfg",
                "v+rgv6NSwwOQn3+0WLPHIHM6ghUwlyTQ1v1qF5fUMLxFfvMCBsS2E0tFtbyWW6GE",
                "3J9NcDCbAgMBAAECggEAUM33YrtdCqZxinHIMlpl5pVWMr+PgUhOegBLB6hd+oDI",
                "pM+hVkd7E70HChXFWRFdeZ60fud/7T/6OH/WJwWkgUO2HBl/OKYr2ksSODyEoC93",
                "z8cxGREic1n2tV/lMQj2HcBXX8dV7ED9ioGkqaQkw48BrtBKmoHzv757uCHkuTPY",
                "In9AtX9Vh/HDFk5lTREvuj7oVv/x+fpkR2naev/ftF5ufDaIKo12ZNXo7b+U+NNb",
                "Oba5SmwJgLLqj3zttYdWsmcir7mFRrorz0/4Ckn9/+TTi46eQn8QhZ1OlLmtWyPg",
                "2Cvx4ZIl+ZmzbKRm2Rv/IJQ3bZstClpG7dRXDr9iUQKBgQDdFxxoN00w2hm880zh",
                "bkK7sbtX15o61lQL22iBvmUGi9nqWsfe1UE5nRINXv/Q0RI+cDB25S9l3//2GAN2",
                "qRSymAyreIvTEgvODVLOvyi5//XHQXk1RkXnQUcyZ04p0cWd8GAN2dTdwBpzPFU",
                "HTRhd4zHXhI+BJXdtHvD28YE4ih1jlQcieWI0lUVSeZvCQtBoWkL2jT6rXOEQVf",
                "FD382MCgYA05krdHn8IUWuQQtmYaxQe0YZqwc8/vIraMLX9kkSujCkMfnV1K9ES",
                "zhNCHcMb4v284C70gycDxJZx7RtdmPCutH9dRhFa9mTaslXxc+A3e5p6Dn3CvsHr",
                "GLCfsVqZz540YXI8s/FAUSFcOA5H4UJ9HHAy0CbNInA4bzI7jAJSCw==",
                "-----END PRIVATE KEY-----"
            ]
            
            creds_dict = {
                "type": "service_account",
                "project_id": "crh-dashboard-1a1",
                "private_key_id": "7d51cddfb7b2df4f83db479d8bd19abed38fd53f",
                "private_key": "\n".join(private_key_lines) + "\n",
                "client_email": "robo-auditor-1a1@crh-dashboard-1a1.iam.gserviceaccount.com",
                "client_id": "107052444758278770613",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/robo-auditor-1a1%40crh-dashboard-1a1.iam.gserviceaccount.com",
                "universe_domain": "googleapis.com"
            }
            
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
            st.error("🔑 Nenhuma API Key da OpenAI foi encontrada. Insira nas Secrets do Streamlit ou digite na barra lateral.")
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
