import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from openai import OpenAI

# Tentar importar bibliotecas do Google Cloud
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Configuração da página
st.set_page_config(
    page_title="Dashboard 1A1 - Ricarreira",
    page_icon="📊",
    layout="wide"
)

# Estilização Clean
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 12px 16px;
        border-radius: 8px;
    }
    h3 {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente com Base no Roteiro Oficial CRH & Mentoria Henrique Bento / Claudio Tonon")
st.divider()

# Transcrição de Exemplo para Showcase / Teste
DEMO_TRANSCRIPT = """
Closer: Olá Mariana, tudo bem? Vamos analisar seu Raio-X. Vi aqui que no LinkedIn você deu nota 4 e em Entrevistas nota 5. Me conta o porquê dessa nota tão baixa no LinkedIn?
Lead: Ah, eu envio muitos currículos mas ninguém me chama no LinkedIn, me sinto invisível.
Closer: Entendi... E se a gente puder mudar esse cenário hoje? Quero te mostrar nosso programa de acompanhamento da CRH. Deixa eu te contar uma história: o Ricardo por muito tempo relutou em criar um programa individual porque achava que tomaria muito tempo... Mas ele viu que ter acompanhamento muda o jogo.
(Apresentação dos depoimentos e dos entregáveis do App CRH)
Closer: De 0 a 10, o quanto você acha que tudo isso que te apresentei vai te ajudar a resolver sua maior dificuldade?
Lead: Nota 9! Gostei muito, mas preciso ver a questão financeira.
Closer: Maravilha! Vi aqui no seu LinkedIn suas formações e estimamos cerca de R$ 30.000 investidos em pós e cursos sem acompanhamento. E na calculadora, sua pretensão de R$ 8.000 significa que cada semana parada você perde R$ 2.000.
(Apresentação das Ofertas)
Closer: Nosso investimento normal é 12x de R$ 997. Mas fechando até às 23h59 hoje temos a condição especial de R$ 8.500 com entrada de R$ 500 e mais 10x de R$ 800. E para quem fecha agora ao vivo na chamada, fica por R$ 5.000 (R$ 500 entrada + 10x R$ 550) com a Garantia Condicional de 51 dias!
"""

# Reuniões de Exemplo (Simulador)
MOCK_EVENTS = [
    {
        "title": "Sessão 1A1 - Mariana Mansur (CRH)",
        "time": "Hoje às 14:00",
        "lead": "Mariana Mansur",
        "closers": "Fernanda Vazquez & Ricardo Batista",
        "transcript": DEMO_TRANSCRIPT
    },
    {
        "title": "Sessão 1A1 - Carlos Eduardo (Diagnóstico Raio-X)",
        "time": "Hoje às 16:30",
        "lead": "Carlos Eduardo",
        "closers": "Fernanda Vazquez",
        "transcript": "Closer: Olá Carlos, vi no seu Raio-X nota 3 em entrevistas. O que tem travado lá?\nLead: Eu fico muito nervoso ao responder perguntas sobre histórias de conquistas passadas..."
    }
]

# Função para buscar reuniões reais do Google Calendar
def fetch_google_calendar_events(calendar_id):
    if not GOOGLE_API_AVAILABLE:
        return None, "As bibliotecas 'google-api-python-client' e 'google-auth' precisam estar no arquivo requirements.txt."
    
    if "google_credentials" not in st.secrets:
        return None, "Chave 'google_credentials' não encontrada nas Secrets do Streamlit."
    
    try:
        creds_raw = st.secrets["google_credentials"]
        if isinstance(creds_raw, str):
            creds_dict = json.loads(creds_raw)
        else:
            creds_dict = dict(creds_raw)
            
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=credentials)
        
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events, None
    except Exception as e:
        return None, str(e)

# Session States
if "lead_name" not in st.session_state:
    st.session_state["lead_name"] = "Mariana Mansur"
if "closers" not in st.session_state:
    st.session_state["closers"] = "Fernanda Vazquez & Ricardo Batista"
if "transcript" not in st.session_state:
    st.session_state["transcript"] = ""

# Barra Lateral
with st.sidebar:
    st.header("⚙️ Configurações & Conexões")
    api_key = st.text_input("OpenAI API Key", type="password")
    
    st.markdown("---")
    st.subheader("📅 Origem dos Dados")
    
    data_source = st.radio(
        "Selecione a Fonte das Sessões:",
        ["⚡ Modo Apresentação / Simulador", "📅 Agenda do Google (API Real)"]
    )
    
    if data_source == "📅 Agenda do Google (API Real)":
        calendar_email = st.text_input(
            "E-mail da Agenda da Equipe:", 
            value="equipe@ricarreira.com", 
            help="Coloque o e-mail da conta do Google Calendar onde ficam agendadas as reuniões 1A1."
        )
        if st.button("🔄 Buscar Sessões na Agenda Real"):
            with st.spinner("Conectando à Agenda do Google..."):
                events, err = fetch_google_calendar_events(calendar_email)
                if err:
                    st.error(f"Erro na conexão: {err}")
                    st.info("💡 Dica: Verifique se a agenda deste e-mail foi compartilhada com a Conta de Serviço (o e-mail do robô em `client_email`).")
                elif not events:
                    st.warning("Nenhuma reunião futura encontrada na agenda informada.")
                else:
                    st.session_state["real_events"] = events
                    st.success(f"{len(events)} reuniões encontradas!")

    st.markdown("---")
    
    # Preenchimento de exemplo rápido
    if st.checkbox("Carregar Transcrição de Exemplo"):
        st.session_state["transcript"] = DEMO_TRANSCRIPT
        st.session_state["lead_name"] = "Mariana Mansur"
        st.session_state["closers"] = "Fernanda Vazquez & Ricardo Batista"

    lead_name = st.text_input("Nome do Lead", value=st.session_state["lead_name"])
    closers = st.text_input("Avaliados / Closers", value=st.session_state["closers"])
    transcript = st.text_area("Cole a Transcrição da Sessão aqui:", value=st.session_state["transcript"], height=250)
    
    process_btn = st.button("🚀 Gerar Análise de Performance", type="primary", use_container_width=True)

# Painel Central do Simulador/Google Calendar
if data_source == "⚡ Modo Apresentação / Simulador":
    st.subheader("📅 Sessões Agendadas na Agenda (Simulação Showcase)")
    st.caption("Selecione uma reunião sincronizada para importar automaticamente os dados:")
    
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        selected_title = st.selectbox("Escolha a sessão:", [f"{e['time']} - {e['title']}" for e in MOCK_EVENTS])
    with col_btn:
        st.write("")
        if st.button("📥 Importar Dados"):
            selected_evt = next(e for e in MOCK_EVENTS if e['title'] in selected_title)
            st.session_state["lead_name"] = selected_evt["lead"]
            st.session_state["closers"] = selected_evt["closers"]
            st.session_state["transcript"] = selected_evt["transcript"]
            st.success(f"Dados de {selected_evt['lead']} importados!")
            st.rerun()

elif data_source == "📅 Agenda do Google (API Real)" and "real_events" in st.session_state:
    st.subheader("📅 Sessões Encontradas na Agenda Oficial da Equipe")
    real_events = st.session_state["real_events"]
    
    event_options = [f"{e.get('start', {}).get('dateTime', 'Horário N/A')} - {e.get('summary', 'Sem título')}" for e in real_events]
    selected_real_evt_title = st.selectbox("Selecione a reunião da agenda:", event_options)
    
    if st.button("📥 Importar Dados do Evento Selecionado"):
        idx = event_options.index(selected_real_evt_title)
        evt_data = real_events[idx]
        st.session_state["lead_name"] = evt_data.get("summary", "Lead").replace("Sessão 1A1 - ", "")
        st.session_state["transcript"] = evt_data.get("description", "Cole aqui a transcrição do Google Meet...")
        st.success("Dados da reunião importados da Agenda do Google!")
        st.rerun()

st.divider()

# Função de Análise GPT-4o
def analyze_session(text, key):
    client = OpenAI(api_key=key)
    
    prompt = f"""
    Você é um Sales Enablement Director e Auditor Comercial de Elite da Ricarreira/CRH.
    Sua missão é auditar e avaliar minuciosamente uma transcrição de Sessão 1A1 comparando-a estritamente contra o ROTEIRO OFICIAL DE VENDAS DA CRH e o MODELO DE ANÁLISE DO HENRIQUE BENTO.

    ROTEIRO E CHECKLIST TÉCNICO DA CRH PARA AUDITAR:
    1. Transição & História do Herói Relutante: Validação do gráfico do Raio-X + história da relutância do Ricardo em criar o acompanhamento (apenas 4 vagas/mês).
    2. Provas Sociais Direcionadas: Apresentação de depoimentos conectando explicitamente a história exibida com a maior dor dita pelo lead no Raio-X, ANTES de detalhar entregáveis.
    3. Passeio pelos Entregáveis (Pilares + App): Explicação do 'Mapa de Carreira' e funcionalidades do app (Busca ATS, Controle de Vagas, Banco de Currículos Aprovados e Bônus de Onboarding/Aumento).
    4. Validação da Solução (Nota 0 a 10): Pergunta 'De 0 a 10 o quanto isso te ajuda?' e tratamento direto das objeções caso a resposta seja menor que 10, antes de abrir preço.
    5. Ancoragem Dupla de Valor: 
       - Ancoragem Acadêmica: Cálculo estimado de investimentos passados no LinkedIn.
       - Calculadora 'Tempo é Dinheiro': Cálculo ostensivo da perda financeira por dia e por semana parado.
    6. Escada de Oferta e Negociação:
       - Âncora 1 (Cheio): 12x R$ 997 (Entrada R$ 500 + 12x R$ 955 ou R$ 9.500 à vista).
       - Âncora 2 (Urgência 23h59): R$ 8.500 (Entrada R$ 500 + 10x R$ 800 ou R$ 6.500 à vista).
       - Âncora 3 (Ao Vivo): R$ 5.000 (Entrada R$ 500 + 10x R$ 550 ou R$ 4.500 à vista).
       - Cartas de Fechamento: Uso da Garantia Condicional de 51 dias, Combo R$ 500 para Dailys e flexibilização de entrada.

    DIRETRIZES DE CATEGORIZAÇÃO DOS FEEDBACKS:
    - PONTOS FORTES: Momentos e trechos exatos em que o closer executou com excelência o padrão Ricarreira.
    - PONTOS DE MELHORIA (🚨 Erros Práticos): Falhas técnicas diretas, erros operacionais e desvios do roteiro executados na chamada que exigem correção imediata (ex: hesitação no fechamento, pulo da nota de 0 a 10, subexplicação da calculadora).
    - PONTOS DE ATENÇÃO (💡 Alertas & Recomendações): Cuidados preventivos, alertas estratégicos de gestão de tempo, ritmo e tom de voz para evitar objeções nas próximas sessões.

    Seja cirúrgico e aprofundado na análise do tempo de permanência e qualidade do discurso. Cite falas e omissões reais do vendedor.

    Retorne ESTRITAMENTE um objeto JSON válido no formato:
    {{
        "nota_geral": 7.5,
        "notas_criterios": {{
            "Herói Relutante & Conexão": 8.0,
            "Provas e Depoimentos": 7.0,
            "Apresentação de Entregáveis": 8.5,
            "Ancoragem (Acadêmica + Calculadora)": 6.5,
            "Escada de Preços & Negociação": 6.0,
            "Linguagem & Fechamento": 7.5
        }},
        "pontos_fortes": [
            "Trecho ou execução exata alinhada com o roteiro oficial da CRH."
        ],
        "pontos_melhoria": [
            "Erros práticos, falhas técnicas e desvios diretos do roteiro oficial que ocorreram na chamada e precisam de correção imediata."
        ],
        "pontos_atencao": [
            "Alertas preventivos, recomendações de cuidados no tom de voz, ritmo ou gestão de tempo para evitar falhas em chamadas futuras."
        ]
    }}

    Transcrição para Análise:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    
    return json.loads(response.choices[0].message.content)

# Renderização dos Resultados
if process_btn:
    if not api_key:
        st.error("Por favor, informe a sua OpenAI API Key na barra lateral.")
    elif not transcript:
        st.warning("Por favor, insira o texto da transcrição.")
    else:
        with st.spinner("Auditando a sessão contra o Roteiro Oficial CRH e Mentoria Henrique Bento..."):
            try:
                data = analyze_session(transcript, api_key)
                
                # Resumo e Métricas
                col1, col2, col3 = st.columns(3)
                col1.metric("Score Geral", f"{data['nota_geral']} / 10")
                col2.metric("Lead Analisado", lead_name)
                col3.metric("Equipe Avaliada", closers)
                
                st.divider()
                
                # Gráfico
                st.subheader("📈 Desempenho por Pilar do Roteiro Oficial CRH")
                
                df = pd.DataFrame(
                    list(data["notas_criterios"].items()),
                    columns=["Critério", "Nota"]
                )
                
                c_chart, c_details = st.columns([2, 1])
                with c_chart:
                    st.bar_chart(df.set_index("Critério"))
                with c_details:
                    for crit, score in data["notas_criterios"].items():
                        st.write(f"**{crit}:** {score}/10")
                        st.progress(score / 10.0)
                
                st.divider()
                
                # Feedbacks Organizados
                c_fortes, c_melhoria, c_atencao = st.columns(3)
                
                with c_fortes:
                    st.subheader("🎯 Pontos Fortes")
                    for pf in data["pontos_fortes"]:
                        st.success(f"• {pf}")
                        
                with c_melhoria:
                    st.subheader("🚨 Pontos de Melhoria")
                    for pm in data["pontos_melhoria"]:
                        st.warning(f"• {pm}")
                        
                with c_atencao:
                    st.subheader("💡 Pontos de Atenção")
                    for pa in data["pontos_atencao"]:
                        st.info(f"• {pa}")
                
                st.divider()
                
                # Exportar Relatório
                report_text = f"""=== RELATÓRIO DE FEEDBACK 1A1 - RICARREIRA ===
Lead: {lead_name}
Closers: {closers}
Score Geral: {data['nota_geral']} / 10

PONTOS FORTES:
""" + "\n".join([f"- {item}" for item in data['pontos_fortes']]) + """

PONTOS DE MELHORIA:
""" + "\n".join([f"- {item}" for item in data['pontos_melhoria']]) + """

PONTOS DE ATENÇÃO:
""" + "\n".join([f"- {item}" for item in data['pontos_atencao']]) + """
"""
                st.download_button(
                    label="📥 Baixar Feedback em Arquivo de Texto",
                    data=report_text,
                    file_name=f"Feedback_1A1_{lead_name.replace(' ', '_')}.txt",
                    mime="text/plain"
                )

            except Exception as e:
                st.error(f"Erro ao processar análise: {e}")
else:
    st.info("👈 Selecione uma opção na barra lateral e insira a API Key para carregar a análise.")
```

### O que muda agora no seu app:
1. Apareceu na barra lateral a seção **"📅 Origem dos Dados"**.
2. Você pode escolher entre **⚡ Modo Apresentação / Simulador** (para testar sem precisar da agenda na hora) e **📅 Agenda do Google (API Real)**.
3. No modo real, você digita o e-mail da equipe, clica em **Buscar Sessões** e o app consulta a API do Google usando a chave que você salvou em Secrets!

Substitua esse código no arquivo `app.py` do GitHub e clique em **Commit changes**. O app vai carregar a nova interface em instantes!
