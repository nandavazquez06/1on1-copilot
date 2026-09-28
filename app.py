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

# CSS para garantir legibilidade e estilo moderno
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
    .playbook-box {
        background-color: #f8fafc;
        border-left: 4px solid #2563eb;
        padding: 16px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .playbook-script {
        font-style: italic;
        color: #0f172a;
        background-color: #ffffff;
        padding: 14px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        line-height: 1.5;
    }
    </style>
""", unsafe_allow_html=True)

def remover_acentos(texto):
    if not isinstance(texto, str):
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

def similaridade(a, b):
    return SequenceMatcher(None, remover_acentos(a), remover_acentos(b)).ratio()

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
            df_planilha = pd.DataFrame(values[1:], columns=values[0])
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
# ABA 1: ROTEIROS & PLAYBOOK DE BOLSO (TEXTOS COMPLETOS NA ÍNTEGRA)
# =================================----------------=============
with tab1:
    st.header("📖 Roteiro Completo - Sessão 1A1 High Ticket")
    st.caption("Consulte na íntegra as falas, frases de alinhamento e reframes oficiais durante a chamada.")
    
    p_tab1, p_tab2 = st.tabs(["📍 Bloco 1: Devolutiva do Raio-X", "📍 Blocos 2 e 3: Apresentação, Pitch & Objeções"])
    
    with p_tab1:
        st.title("Roteiro de Devolutiva do Raio-X (Sessões 1A1)")
        
        st.subheader("PILAR: MENTALIDADE")
        st.markdown("**Discurso Positivo (Padrão):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Olhando aqui para o seu gráfico, o primeiro ponto que se destaca é a sua Mentalidade, que deu uma nota bem alta. Isso é fundamental, porque significa que você não é uma pessoa acomodada, você tem clareza de que a sua família é prioridade e que a sua carreira não pode mais ficar parada. Você me disse que é dedicado(a), que é uma pessoa de palavra e que está disposto(a) a executar um passo a passo claro. Isso é ótimo, porque sem esse compromisso nenhum método funciona… então o seu momento de virar o jogo é agora, porque é essa sua disposição que vai impulsionar todo o resto."</div></div>', unsafe_allow_html=True)
        
        st.markdown("**Discurso Negativo (Exceção):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"A sua nota de Mentalidade ficou baixa e isso me preocupa bastante. O que essa nota revela é que as rejeições no mercado acabaram diminuindo a sua confiança e você entrou em um estado de aceitação ou hesitação. Você quer mudar de vida, mas quando chega no momento de priorizar o seu desenvolvimento e tomar decisões firmes, você acaba buscando desculpas. Sem reajustar a sua postura para uma prioridade absoluta, nenhum currículo ou LinkedIn novo vai fazer milagre por você."</div></div>', unsafe_allow_html=True)

        st.subheader("PILAR: AUMENTO SALARIAL")
        st.markdown("**Discurso Positivo (Padrão):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Aqui no pilar de Aumento Salarial, a sua pontuação também foi alta, e isso mostra que você é uma profissional com boa articulação, que sabe se relacionar bem com as pessoas dentro da empresa, criar pontes e que joga bem a dinâmica do ambiente corporativo. Só que ainda assim existe um gargalo de que não adianta você saber como pedir um aumento salarial, saber fazer o jogo político ou mapear como gerar cases de lucro, se você não consegue uma vaga para mostrar essas habilidades."</div></div>', unsafe_allow_html=True)
        
        st.markdown("**Discurso Negativo (Exceção):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Sua nota de aumento salarial foi baixa porque provavelmente você sempre enxergou o trabalho só pela parte técnica e operacional, negligenciando a sua gestão de imagem e uma articulação política, e se você não souber construir um mapa de aliados estratégicos, vai acabar sendo ignorada nas promoções e sempre ver profissionais menos qualificados subirem na sua frente."</div></div>', unsafe_allow_html=True)

        st.subheader("PILAR: CURRÍCULO")
        st.markdown("**Discurso Negativo (Padrão):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Aqui é onde o gráfico começa a mostrar os pontos de alerta: no pilar de Currículo a sua nota foi bem baixa, então a gente percebe que dos currículos que você envia, quase nenhum se transforma em entrevista, porque provavelmente o seu material está com várias descrições de tarefas genéricas, dizendo \'o que você fazia\', em vez de demonstrar \'o impacto financeiro e operacional que você gerava para as empresas\'. Então você é um(a) profissional qualificado(a), mas o seu currículo não mostra isso, e o mercado nem fica sabendo do seu real potencial porque seu currículo não é validado nem pelo robô, nem pelo recrutador."</div></div>', unsafe_allow_html=True)
        
        st.markdown("**Discurso Positivo (Exceção):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Seu currículo está bem desenhado, focado em métricas e com bom alinhamento com os algoritmos, o que justifica a sua taxa de retorno quando envia. Apenas precisamos fazer pequenos ajustes finos para cargos de maior remuneração."</div></div>', unsafe_allow_html=True)

        st.subheader("PILAR: LINKEDIN")
        st.markdown("**Discurso Negativo (Padrão):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Na parte de LinkedIn, a sua nota também foi praticamente zero. Isso significa que hoje você está invisível para os recrutadores que estão procurando profissionais do seu nível. Então o seu perfil hoje não aparece nas buscas do LinkedIn Recruiter porque faltam palavras-chave específicas e você não tem uma estratégia ativa para abordar os responsáveis pelas vagas (principalmente as ocultas)."</div></div>', unsafe_allow_html=True)
        
        st.markdown("**Discurso Positivo (Exceção):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"O seu perfil no LinkedIn já atua como um ímã de oportunidades, gerando abordagens semanais de headhunters de forma orgânica."</div></div>', unsafe_allow_html=True)

        st.subheader("PILAR: ENTREVISTAS")
        st.markdown("**Discurso Negativo (Padrão):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"O pilar de Entrevistas mostra um efeito dominó: como o seu Currículo e LinkedIn estão travados e você está invisível, não existe um volume de entrevistas, e você acaba não conseguindo treinar. Nas raras vezes em que você consegue uma entrevista, a pressão é tão grande por ser \'a única chance\' que você fica nervoso(a), dá respostas prolixas, foca no aspecto técnico e não consegue contar a sua história da melhor forma, com estratégia. Você sai da reunião sem ter certeza se mandou bem e nunca recebe um feedback assertivo sobre onde errou. Como consequência, você não consegue negociar e aceita qualquer valor, em vez de se posicionar para conquistar o salário que você realmente merece."</div></div>', unsafe_allow_html=True)
        
        st.markdown("**Discurso Positivo (Exceção):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Sua performance em conversas é excelente: você domina a condução com o gestor e consegue transmitir alta credibilidade e alinhamento cultural nas etapas finais."</div></div>', unsafe_allow_html=True)

        st.subheader("TRANSIÇÃO PARA O PITCH ANTES DA HISTÓRIA DO HERÓI RELUTANTE")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Olhando agora o seu Raio-X como um todo: fica claro que o seu problema NÃO é falta de capacidade técnica e NÃO é falta de vontade (sua mentalidade e visão de Aumento Salarial provam isso). O seu verdadeiro gargalo é a falta de um método estratégico para a sua carreira. Você está travado(a), e é por isso que sente que se esforça demais, gasta horas aplicando para vagas e recebe um retorno quase nulo.<br><br>O que nós precisamos fazer agora é reestruturar a sua comunicação para te dar visibilidade, ensinar você a contar a sua história de forma atraente para os recrutadores e gerar um fluxo maior de entrevistas para que você conquiste a sua contratação nos próximos 51 dias. Faz sentido para você?"</div></div>', unsafe_allow_html=True)

    with p_tab2:
        st.title("Roteiro dos Slides, Pitch & Tabela de Objeções")
        
        st.markdown("**Slide 1 (Transição entre raio-x e slides):**")
        st.markdown("*(Falar sobre o gráfico e perguntar se faz sentido para a pessoa)*")
        st.markdown("**Você quer mudar esse cenário?**")
        
        st.markdown("**História do Herói Relutante:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"O Ricardo por muito tempo relutou em criar um programa de acompanhamento individual personalizado, porque acreditava que isso iria tomar muito tempo dele, e nós já temos um método que ajuda muitas pessoas, mas não eram essas muitas pessoas que preocupava ele... e sim o fato de ter um monte de gente aplicando esse método sem ter o acompanhamento necessário para aumentar a taxa de aprovações em processos seletivos e, mais do que isso, ajudar as pessoas a crescer na carreira a longo prazo.<br><br>Então o Ric entendeu que acompanhar é diferente de só ensinar, e conversando com alguns alunos muitos pediam algo mais personalizado para conseguir o novo emprego mais rápido. E ouvir das pessoas que elas precisavam se recolocar urgente fez ele pensar... e se eu criasse um programa de acompanhamento personalizado, para realmente pegar as pessoas pela mão, analisar o que elas estão fazendo e para ajudar elas a fazerem o que realmente precisam fazer.<br><br>E aí ele olhou para o próprio cenário, porque ele está em vários programas de acompanhamento que ajudam ele a acelerar os resultados, então ele pensou: Por que não criar um acelerador de resultados? Então hoje nós temos isso, e quero saber: posso te mostrar o nosso programa de acompanhamento que vai te ajudar a melhorar seu LinkedIn e currículo, aumentando a taxa de aprovação nas entrevistas para no futuro você ter mais chances de conseguir um aumento salarial?<br><br>Mas olha, hoje nós já temos um grupo com um número bom de alunos, porque ao mostrarmos isso para as pessoas, várias falaram: \'nossa, era tudo isso que eu precisava!\'. Pensando nisso, nós só abrimos 4 vagas por mês para pessoas que selecionamos e achamos que o perfil faz sentido para esse grupo, certo?"</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 3:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Aqui temos alguns depoimentos de pessoas que conseguiram sua recolocação aplicando o método que usamos aqui na CRH. Nós temos lá no Youtube uma playlist com mais de 200 dedicados especialistas, mas aqui separamos algumas das histórias que podem se encaixar com o seu cenário pra poder te inspirar.<br><br>(Conteúdo do Slide)<br><br>E aí, o que achou dos depoimentos que eu te mostrei aqui?<br>*(Reforçar a história que aparece nas provas que mais se assemelha à maior dificuldade atual da lead)*"</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 43:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Vamos começar a falar dos entregáveis da CRH então.<br><br>(Conteúdo do Slide)<br><br>Nós sempre vamos te orientar em relação a qual mentoria faz mais sentido você solicitar de acordo com o seu momento de carreira e sobre qual a melhor frequência para esses encontros também."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 44:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Na CRH nós temos 4 pilares para te ajudar a conseguir seu novo emprego, começando com os entregáveis de direcionamento.<br><br>Vamos guiar você com um plano de ação claro, com alinhamento estratégico para o seu CV, LinkedIn, entender onde você quer chegar e em quanto tempo, então todo o seu posicionamento e marca pessoal é importante no pilar de direcionamento."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 49:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Alguma dúvida até aqui?<br>*(Responder as dúvidas)*<br><br>Maravilha, vamos agora passar pelos entregáveis do pilar de acompanhamento.<br>Esse acompanhamento é no sentido de \'ah, estou travado aqui porque recebi poucas entrevistas na semana, quero receber mais\', análises de carreira que vão te guiar para destravar todo o processo de busca de emprego e também crescimento de carreira."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 53:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Tranquilo até aqui?<br>*(Responder as dúvidas se tiver)*<br><br>No pilar de facilidades, você vai ter acesso a um aplicativo do Ricarreira com funcionalidades para te ajudar na busca de emprego e não vai perder tempo em todo o processo."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 54:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"No aplicativo você vai encontrar uma funcionalidade onde pode pesquisar a nomenclatura da vaga que você está buscando e filtrar por estado e cidade para encontrar as vagas disponíveis no mercado em todos os ATS.<br><br>Aqui você pode ver a descrição, o site em que a vaga foi publicada e se inscrever naquelas que mais fizerem sentido para o que você está buscando."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 55:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Depois que fizer a inscrição, todas as vagas vão aparecer aqui no seu controle de vagas, para facilitar a organização dos processos seletivos em que você está participando.<br><br>Não sei se você já passou por isso... às vezes a gente se inscreve em um monte de vagas e depois um recrutador entra em contato mas não lembramos de nada sobre a vaga, certo?<br><br>Aqui com essa funcionalidade você consegue acompanhar todas as etapas dos processos e em quais você está avançando."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 57:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Aqui a gente vai ter os grupos individuais no WhatsApp, que te mostrei nos outros entregáveis, mas também os coletivos (a comunidade do bem), para podermos tirar todas as suas dúvidas e te darmos suporte em todo esse processo."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 62:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Como eu te falei no início, depois de conseguir a sua recolocação você vai ter também um acompanhamento para te ajudarmos a aumentar seu salário na futura empresa."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 68:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"E aí, a CRH faz sentido para você?<br>*(Esperar a pessoa responder)*<br><br>De 0 a 10, o quanto você acha que tudo o que te apresentei aqui vai te ajudar a resolver a sua maior dificuldade hoje?<br>*(Se responder menos de 10, perguntar: O que falta para ser 10?)*<br>*(Quebrar as objeções antes de passar para a parte da oferta)*<br><br>Olha, como eu te falei no início, nós só temos X cadeiras disponíveis pra esse mês, então quero saber: por que uma dessas vagas deveria ser sua e não de outras pessoas que também estão interessadas?<br><br>*(Se já tiver a objeção do dinheiro "faz sentido mas depende do valor do investimento")*:<br>Certo, eu vou te apresentar as condições de pagamentos e aí eu preciso que você seja brutalmente sincero, tá? Se não fizer sentido para você financeiramente me fala aqui, porque a gente só tem X cadeiras mesmo.<br><br>Se você não conseguir pegar uma dessas cadeiras não tem problema, porque nossa equipe está falando com outras pessoas e a gente passa a cadeira para outra pessoa... Mas eu acredito que pelo raio X que a gente fez aqui, você precisa de verdade desse nível de acompanhamento, concorda?"</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 70:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Eu peguei todas as formações que estão no seu LinkedIn. Não sei se você já fez essa reflexão... mas qual foi mais ou menos o valor total que você investiu nelas?<br><br>Certo, R$XXXX investidos em carreira então. E uma curiosidade, quantos anos você tem mesmo?<br>*(Esperar resposta)*<br><br>XX anos e está buscando um salário de R$XXXX... Você acha que tem pessoas que têm menos do que XX anos que estão ganhando mais do que R$XXXX?<br>*(Esperar resposta)* E por que será?<br>*(Esperar resposta) - (Responder como fizer sentido e acrescentar):*<br><br>Olha, enquanto você não mudar a sua mentalidade e entender que não foi protagonista da sua carreira para você estar ganhando mais com XX anos, você não vai conseguir crescer na sua carreira.<br><br>E aí se a gente parar para olhar as suas formações aqui, você está desde XXXX (ano) só fazendo cursos técnicos, mas nunca investiu na sua carreira. Será que se tivesse investido na carreira nesses últimos X anos, você não estaria em outro patamar?<br>*(Esperar resposta)* E você quer mudar esse cenário?<br>*(Esperar resposta)*<br><br>Perfeito. Então, o que eu quero trazer aqui é o fato de que você nunca ter investido te prejudica nesse processo de estar crescendo na carreira ao longo de todos esses anos estagnado."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 71:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"E outra reflexão que a gente gosta de fazer sempre é a de que tempo é dinheiro, né?<br><br>Então aqui tem uma calculadora da sua pretensão salarial, que você me disse que é R$XXXX. Isso quer dizer que por ano, você quer ganhar R$XXXX, certo?<br><br>Olha, a cada semana que você passa buscando a sua recolocação sem direcionamento, acompanhamento e feedbacks que realmente vão mudar o jogo, você está perdendo R$XXXX, já parou para pensar nisso?<br><br>Pois é, e isso significa que você está perdendo esse valor por semana e R$XXXX todos os dias, deixando de ganhar os R$XXXX que fariam a diferença para você e a sua família daqui a 1 ano.<br><br>O que você acha disso?<br><br>Eu sei que isso dói, mas a gente faz esse cálculo normalmente também para ver quanto você vai ganhar, não só quanto está perdendo.<br><br>Então a gente está conversando aqui para você ganhar R$XXXX por ano. Você já parou para pensar isso? São R$XXXX.<br>*(Esperar resposta)*<br><br>E olha, o nosso objetivo é fazer você ganhar R$XXXX (pretensão) o quanto antes, e fazer você parar de perder R$XXXX toda semana.<br><br>Se você chegar na semana que vem a mais uma semana no mesmo cenário de não ter entrevista, não ser chamado, não ter perspectiva de conseguir ser contratado, são mais R$XXXX jogados fora. Você está confortável com isso?"</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 72:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Como você me disse que faz sentido tudo isso e que tem a mentalidade que estamos buscando pelo raio x que nós fizemos, eu acho que uma das cadeiras pode ser sua de fato.<br><br>Então, hoje quanto valeria se você fosse ter esse acompanhamento individual com o Ric?<br><br>(Conteúdo do slide)"</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 73:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Como eu apresentei para você aqui, a gente consegue reduzir esse valor porque temos toda uma equipe de mentores por trás.<br><br>Então você não precisa pagar R$41.000 para poder ter esse nível de acompanhamento."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 74:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Hoje o investimento para você poder estar junto com a gente, com essa equipe de mentores aqui sendo acompanhado, ele está aqui em parcelas de R$997."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 75:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"E como a gente sabe que nem todo mundo tem limite no cartão para poder já fazer esse pagamento, para você garantir a sua cadeira agora, a única coisa que você precisa é de R$500.<br><br>E aí você garante uma das duas cadeiras e só depois de uma semana o financeiro aqui da equipe vai entrar em contato com você para ver como vai levantar o restante do valor da mentoria e a melhor forma para isso."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 76:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Então ficam 12 parcelas de 955 ou então se você fizer um pagamento único, que pode ser com limite no cartão mesmo, fica no valor de 9500, mas isso tudo é só depois de uma semana."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 77:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Para agora, a única coisa que você precisa é focar nos R$500.<br><br>R$500 é um valor acessível que você pode investir agora?"</div></div>', unsafe_allow_html=True)

        st.subheader("QUEBRA DE OBJEÇÕES")

        st.markdown("**🔴 Objeção: 'Preciso pensar por conta do valor das outras parcelas, eu não tenho isso tudo agora, não estava esperando que fosse tudo isso'**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"- O que você precisa pensar?<br>Agora a única coisa que você precisa pensar são os R$ 500, que você falou que tem. Então você pode dar os R$500 da entrada, participar dos momentos das daylis, já ter o seu momento de direcionamento estratégico, conhecer a CRH por dentro e só depois de uma semana a nossa equipe vai entrar em contato com você para ver como vai ser o restante do pagamento.<br><br>- É, mas não são só os R$500. Eu estou preocupado com o pós.<br>Olha, a gente viu lá o quanto você vai ganhar por dia com o seu novo emprego, né? E por dia, você vai ganhar R$XXX.<br>Então será que não vale a pena você fazer esse investimento aqui e depois com o seu trabalho você vai pagando o valor das parcelas?<br>Sei que agora você está preocupado por essa questão de estar desempregado, mas quando você estiver empregado, essas parcelas aqui dá para pagar.<br><br>- Eu entendo, mas preciso de um tempo para pensar mesmo.<br>Mas me fala o que você quer pensar. Eu posso pensar junto com você, estou aqui para isso.<br><br>- Eu preciso avaliar mesmo, não gosto de fechar nada assim por impulso porque não sei se vou conseguir cumprir com isso depois. Posso pensar e até tal horário te dou um retorno?<br>Infelizmente eu não consigo isso porque a gente tem só essas cadeiras mesmo. Então eu tô aqui realmente aqui disponível para poder te ajudar a pensar.<br>Você me disse que é uma pessoa dedicada, não foi? Você falou que que é uma prioridade conseguir esse novo emprego.<br>A gente tem vários casos de pessoas que conseguiram emprego em menos de 15 dias, que entraram de cabeça.<br>Será que com 15 dias sendo direcionado e acompanhado de perto, o cenário já não vai melhorar para você ter mais entrevistas e conseguir pagar as parcelas com seu futuro salário?<br><br>- Mas e se eu investir esse valor e não conseguir? Como faço para pagar as parcelas?<br>Mas e se você continuar no mesmo cenário e não conseguir entrevista nesses próximos 15 dias, quanto dinheiro você vai perder? São RSXXX, certo? (Tempo é dinheiro).<br>Pelo o que a gente viu, a cada semana que passa você está perdendo R$XXXX. E você me falou que era uma prioridade e que era uma pessoa de palavra, conseguir emprego não é uma prioridade para você então?<br><br>- Sim, é uma prioridade. Mas tenho que pensar como vou pagar depois se eu não conseguir emprego.<br>Mas não precisa pensar agora. Você falou que os R$500 não são o problema. Então você pode dar a entrada de 500, participa da mentoria e nesse período de uma semana a gente até pode te ajudar a pensar na forma de pagamento.<br>A gente vai te acompanhar todos os dias, e o seu trabalho vai ser buscar trabalho. Tem gente que paga 20.000, 40.000 em um MBA, uma pós-graduação para ter só um título e ficar sem feedbacks, acompanhamento, direcionamento, sem essas ferramentas.<br>Então eu te garanto que é um investimento para a sua vida, não só para agora."</div></div>', unsafe_allow_html=True)

        st.markdown("**🔴 Objeção - Cônjuge: 'Eu não consigo fazer esse investimento sem falar com meu marido/minha esposa'**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"- Mas você não me falou que seu marido/sua esposa te apoiava?<br>- Sim, apoia. Mas não posso tomar essa decisão sem discutirmos.<br><br>Certo. Mas olha, ele(a) não entende a sua dor. Será que se o seu marido/a sua esposa olhar o seu diagnóstico que fizemos, ele(a) entende como é ficar navegando horas sem resultados? Será que ele entende o que é ter chuvas de negativas na gupy todos os dias?<br>- Não entende.<br><br>Então é óbvio que o seu marido/a sua esposa vai olhar esse valor aqui e falar: \'Tá caro\'. Porque ele(a) não entende a sua dor da forma como a gente entende.<br>A gente vai te acompanhar todos os dias, e o seu trabalho vai ser buscar trabalho. Tem gente que paga 20.000, 40.000 em um MBA, uma pós-graduação para ter só um título e ficar sem feedbacks, acompanhamento, direcionamento, sem essas ferramentas.<br>Então eu te garanto que é um investimento para a sua vida, não só para agora. E você falou que R$500 você tem... às vezes, o seu marido/a sua esposa vai preferir que você entre com R$500, conheça a mentoria por dentro e aí você vai ganhando mais confiança para poder argumentar com ele(a)."</div></div>', unsafe_allow_html=True)

        st.markdown("**Slide 78 & Garantia:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Olha, se você ficar mais uma semana sem conseguir o seu emprego, você está perdendo R$XXXX por dia.<br>Então você está me dizendo que prefere realmente tentar sozinho e ficar mais um tempo perdendo R$XXXX toda semana sem receber feedbacks, acompanhamento e direcionamento?<br>Ou você prefere dar agora uma entrada de R$500, ter a nossa ajuda e se não der certo ter seu dinheiro de volta?<br><br>- E se eu não conseguir o meu emprego nesse tempo?<br>A gente tem a garantia de um ano. *(Falar sobre a garantia do slide)*<br>Nós falamos que você vai ganhar R$XXXX por ano, certo? Será que agora você não consegue investir R$500 para poder ganhar R$XXXX por ano? Não é vantagem?<br>E se o dinheiro que você investir não retornar, a gente devolve tudo. Você tem a opção de ficar um ano sendo acompanhado por nós ou ficar mais tempo sem conseguir entrevista, sem conseguir ganhar dinheiro. Você já perdeu R$XXXX nesse tempo que está buscando.<br>E você não acha que com o nosso acompanhamento além de conseguir emprego você consegue aumentar a sua proposta salarial em R$955? O José, que eu te mostrei antes, começou a ganhar R$1.200 a mais todos os meses.<br><br>- Mas mesmo assim, eu não sei como vou pagar os R$955 na semana que vem.<br>Mas você entende que se na semana que vem você não tiver nenhuma entrevista nem nada, são menos R$XXXX? Você está falando que não tem R$1500 essa semana para investir na sua carreira, então você está confortável em perder esses R$XXXX, né?"</div></div>', unsafe_allow_html=True)

# =================================----------------=============
# ABA 2: AUDITORIAS & INDICADORES
# =================================----------------=============
with tab2:
    st.header("📊 Painel Geral de Auditorias 1A1")
    
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
        st.markdown(f'<div class="metric-card-custom"><div class="metric-card-title">🟢 Convertidos</div><div class="metric-card-value">{total_convertidos}</div><div class="metric-card-sub">{vendas_ato} Ato | {vendas_fup} FUP</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card-custom"><div class="metric-card-title">📈 Taxa de Conversão</div><div class="metric-card-value">{taxa_conversao:.1f}%</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="metric-card-custom"><div class="metric-card-title">⭐ Nota Média FHT</div><div class="metric-card-value">{media_nota:.1f} / 10</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Tabela Performance por Closer
    st.subheader("👥 Performance Geral da Equipe de Closers")
    closers_alvo = ["Fernanda", "Ricardo", "Renata"]
    df_master = st.session_state["dados_planilha"]

    dados_closers = []
    if not df_master.empty and "Closer" in df_master.columns and "Status" in df_master.columns:
        for c in closers_alvo:
            sub_df = df_master[df_master["Closer"].astype(str).str.strip().str.lower() == c.lower()]
            total_sessoes_c = len(sub_df)
            g_ato = sum(1 for s in sub_df["Status"].astype(str) if "ato" in s.lower())
            g_fup = sum(1 for s in sub_df["Status"].astype(str) if "fup" in s.lower() or "follow" in s.lower())
            tot_ganho = g_ato + g_fup
            taxa_c = (tot_ganho / total_sessoes_c * 100) if total_sessoes_c > 0 else 0.0
            
            dados_closers.append({
                "Closer": c,
                "Sessões na Planilha": total_sessoes_c,
                "Ganho (Ato)": g_ato,
                "Ganho (FUP)": g_fup,
                "Total Convertido": tot_ganho,
                "Taxa de Conversão (%)": f"{taxa_c:.1f}%"
            })
        st.dataframe(pd.DataFrame(dados_closers), use_container_width=True)
    else:
        st.info("Clique em 'Sincronizar Agenda & Tabela Master' na barra lateral para carregar a performance.")

    st.markdown("---")

    # Auditoria da Reunião
    st.subheader("📋 Auditar Reunião 1A1")
    if st.session_state["eventos_carregados"]:
        events = st.session_state["eventos_carregados"]
        opcoes_map = {}
        for e in events:
            nome = e.get('summary', 'Diagnóstico Gratuito de Carreira')
            data = e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))[:10]
            try:
                data_br = datetime.datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m")
            except:
                data_br = data
            label = f"🗓️ [{data_br}] {nome}"
            opcoes_map[label] = e

        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            evento_sel_label = st.selectbox("Selecione o Diagnóstico para Auditar:", list(opcoes_map.keys()))
            evento_obj = opcoes_map[evento_sel_label]
            nome_lead_bruto = evento_obj.get('summary', '')
            nome_lead_limpo = re.sub(r"(?i)diagnóstico\s+gratuito\s+de\s+carreira\s*[-–:]?", "", nome_lead_bruto).strip()
            descricao_evento = evento_obj.get("description", "")
            transcricao_texto = descricao_evento if descricao_evento.strip() else f"Sessão: {nome_lead_bruto}\nData: {evento_obj.get('start', {}).get('dateTime', '')}"

        status_master_auto = "Perdido"
        closer_master_auto = "Não identificado"
        objecao_master_auto = "Sem objeção registrada"
        
        if not df_master.empty and "Cliente" in df_master.columns:
            lead_norm = remover_acentos(nome_lead_limpo)
            melhor_match = None
            maior_score = 0.0

            for idx, row in df_master.iterrows():
                cliente_planilha = str(row.get("Cliente", ""))
                cliente_norm = remover_acentos(cliente_planilha)
                score = similaridade(lead_norm, cliente_norm)
                primeiro_nome_agenda = lead_norm.split()[0] if lead_norm else ""
                if primeiro_nome_agenda and (primeiro_nome_agenda in cliente_norm or cliente_norm.startswith(primeiro_nome_agenda[:3])):
                    score += 0.4

                if score > maior_score and score > 0.35:
                    maior_score = score
                    melhor_match = row

            if melhor_match is not None:
                status_master_auto = str(melhor_match.get("Status", "Perdido")).strip()
                closer_master_auto = str(melhor_match.get("Closer", "Não identificado")).strip()
                objecao_master_auto = str(melhor_match.get("Objeção", "Sem objeção registrada")).strip()

        is_venda_confirmada = "ganho" in status_master_auto.lower()

        if is_venda_confirmada:
            st.success(f"🟢 **Status na Planilha Master:** `{status_master_auto}` | **Closer:** `{closer_master_auto}`")
        else:
            st.info(f"📌 **Status na Planilha Master:** `{status_master_auto}` | **Closer:** `{closer_master_auto}` | **Objeção:** `{objecao_master_auto}`")

        with col_btn:
            st.write(" ")
            st.write(" ")
            gerar_btn = st.button("🚀 Auditar com IA", use_container_width=True)

        if gerar_btn:
            if not openai_key:
                st.error("🔑 OpenAI API Key não encontrada.")
            else:
                with st.spinner("🤖 Analisando reunião com base no Roteiro Oficial Ricarreira..."):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_key)
                        
                        prompt_sistema = f"""Você é o Auditor Sênior de Vendas da Ricarreira (programa CRH, fundado por Ricardo Batista).
Sua missão é auditar meticulosamente a chamada 1A1 com base nos ROTEIROS OFICIAIS da empresa, divididos em 3 blocos de ~20 minutos.

AVALIAÇÃO ESTRUTURAL POR BLOCOS:

📍 BLOCO 1: DIAGNÓSTICO & RAIO-X (Minuto 0 ao 20)
- Quebra-gelo & Conexão: Fez pergunta de acolhimento ("Como conheceu a Ricarreira?")?
- Acordo de Objetividade Flexível: Mencionar que a pessoa não precisa justificar todas as notas é uma boa prática para manter o controle do tempo, MAS O CLOSER TEM LIBERDADE PARA APROFUNDAR e perguntar "por quê" em notas chave quando quiser entender melhor o cenário e escavar dores.
- Raio-X dos 5 Pilares: Passou por Currículo, LinkedIn, Entrevistas (investigando IA vs. RH Humano), Aumento Salarial e Mentalidade?
- Leitura do Gráfico: Compartilhou a tela mostrando APENAS o gráfico e utilizou a narrativa padronizada conectando que Mentalidade e Desejo de Salário só geram resultado se Currículo, LinkedIn e Entrevistas estiverem destravados? Encerrou perguntando se o lead concorda e quer mudar o cenário com urgência?

📍 BLOCO 2: APRESENTAÇÃO DO PROGRAMA & SLIDES (Minuto 20 ao 40)
- História do Herói Relutante: Utilizou a copy oficial explicando por que o Ricardo relutou em criar um programa individual ("Acompanhar é diferente de só ensinar", "Ouvir que precisavam se recolocar urgente")?
- Escassez de Cadeiras: Avisou no início da apresentação que a Ricarreira abre apenas vagas/cadeiras limitadas por mês?
- Apresentação de Pilares vs. Entregáveis: Apresentou os 4 pilares antes de listar entregáveis (Direcionamento, Acompanhamento, Facilidades e Aumento Salarial)?

📍 BLOCO 3: PITCH, ANCORAGEM & QUEBRA DE OBJEÇÕES (Minuto 40 ao 60)
- Merecimento da Cadeira: Perguntou "Por que uma dessas vagas deveria ser sua e não de outras pessoas interessadas?"?
- DETECÇÃO DE CONFRONTO DE FORMAÇÕES (SLIDE 70): Discutiu o investimento prévio em formações para mostrar falta de investimento em CARREIRA/MENTALIDADE?
- DETECÇÃO DA CALCULADORA "TEMPO É DINHEIRO" (SLIDE 71): Abordou a pretensão salarial e desdobrou valores em ganho/perda anual, semanal ou diário?
- Foco na Entrada (R$ 500,00): Conduziu a oferta focando no valor acessível de R$ 500,00 para garantir a vaga agora?
- DETECÇÃO CONDICIONAL DE OBJEÇÕES: Se o lead mencionou cônjuge/família, usou o reframe oficial. Se não mencionou, NÃO COBRE esta etapa.

STATUS REGISTRADO NA PLANILHA MASTER:
- Status na Planilha: {status_master_auto}
- Closer Responsável: {closer_master_auto}
- Objeção no CRM: {objecao_master_auto}
"""

                        if is_venda_confirmada:
                            prompt_sistema += f"\n- VENDA CONVERTIDA ({status_master_auto}). NOTA ENTRE 8.0 E 10.0.\n\n### 🟢 STATUS: LEAD CONVERTIDO ({status_master_auto.upper()})\n\n**Resumo Executivo & Nota do Closer: [X.X / 10]**\n---\n- **🎯 Pontos Fortes da Sessão**\n- **🚨 Pontos de Melhoria Críticos**\n- **💡 Plano de Ação para o Próximo Treinamento**"
                        else:
                            prompt_sistema += f"\n- NÃO CONVERTIDA (Perdido). NOTA ENTRE 0.0 E 7.9.\n\n### 🔴 STATUS: NÃO CONVERTIDO\n\n**Resumo Executivo & Nota do Closer: [X.X / 10]**\n---\n- **🎯 Pontos Fortes da Sessão**\n- **🚨 Pontos de Melhoria Críticos**\n- **💡 Plano de Ação para o Próximo Treinamento**"

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": prompt_sistema},
                                {"role": "user", "content": f"Lead: {nome_lead_limpo}\nTranscrição/Dados:\n{transcricao_texto}"}
                            ],
                            temperature=0.3
                        )
                        
                        analise_ia = response.choices[0].message.content
                        match_nota = re.search(r"(\d+[\.,]?\d*)\s*/\s*10", analise_ia)
                        nota_extraida = float(match_nota.group(1).replace(",", ".")) if match_nota else (9.0 if is_venda_confirmada else 6.0)

                        st.session_state["historico_analises"].append({
                            "Data": evento_obj.get('start', {}).get('dateTime', '')[:10],
                            "Cliente": nome_lead_limpo,
                            "Closer": closer_master_auto,
                            "status_venda": status_master_auto,
                            "Objeção": objecao_master_auto if not is_venda_confirmada else "Nenhuma / Fechado",
                            "convertido": is_venda_confirmada,
                            "nota": nota_extraida,
                            "feedback_completo": analise_ia
                        })
                        st.rerun()

                    except Exception as err:
                        st.error(f"Erro na análise: {str(err)}")
    else:
        st.info("👈 Selecione o período na barra lateral e clique em 'Sincronizar Agenda & Tabela Master'.")

    st.markdown("---")

    if historico:
        st.subheader("📑 Tabela de Auditorias Realizadas")
        df_hist = pd.DataFrame(historico)
        df_exibicao = df_hist[["Data", "Cliente", "Closer", "status_venda", "Objeção", "nota"]].copy()
        df_exibicao.columns = ["Data da Sessão", "Cliente", "Closer", "Status da Venda", "Objeção Registrada", "Nota FHT"]
        st.dataframe(df_exibicao, use_container_width=True)

        with st.expander("🔍 Ver Último Feedback Completo Gerado pela IA", expanded=True):
            st.markdown(historico[-1]["feedback_completo"])

# =================================----------------=============
# ABA 3: DESEMPENHO & RANKING POR CLOSER
# =================================----------------=============
with tab3:
    st.header("👥 Painel de Gestão e Performance por Closer")
    st.caption("Acompanhamento individualizado para reuniões de feedback e desenvolvimento do time.")
    
    closer_selecionado = st.selectbox("Selecione o Closer para Análise Individual:", ["Fernanda", "Ricardo", "Renata"])
    df_master = st.session_state["dados_planilha"]
    
    if not df_master.empty and "Closer" in df_master.columns:
        df_closer_filtrado = df_master[df_master["Closer"].astype(str).str.strip().str.lower() == closer_selecionado.lower()]
        
        col_c1, col_c2, col_c3 = st.columns(3)
        tot_c = len(df_closer_filtrado)
        ganhos_c = sum(1 for s in df_closer_filtrado["Status"].astype(str) if "ganho" in s.lower())
        taxa_ind = (ganhos_c / tot_c * 100) if tot_c > 0 else 0.0
        
        with col_c1:
            st.metric(" Atendimentos no Período", f"{tot_c}")
        with col_c2:
            st.metric(" Conversões (Ato/FUP)", f"{ganhos_c}")
        with col_c3:
            st.metric(" Taxa de Conversão Individual", f"{taxa_ind:.1f}%")
            
        st.markdown("---")
        
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.subheader("🚩 Ranking de Objeções Enfrentadas")
            if "Objeção" in df_closer_filtrado.columns and not df_closer_filtrado.empty:
                df_obj = df_closer_filtrado[df_closer_filtrado["Objeção"].astype(str).str.strip() != ""]
                df_obj_counts = df_obj["Objeção"].value_counts().reset_index()
                df_obj_counts.columns = ["Objeção Registrada", "Quantidade"]
                
                if not df_obj_counts.empty:
                    st.bar_chart(df_obj_counts.set_index("Objeção Registrada"))
                else:
                    st.info("Nenhuma objeção registrada para este closer no período.")
            else:
                st.info("Sem dados de objeção para exibir.")

        with col_graf2:
            st.subheader("⭐ Evolução das Auditorias (Histórico IA)")
            hist_closer = [h for h in st.session_state["historico_analises"] if str(h.get("Closer", "")).lower() == closer_selecionado.lower()]
            if hist_closer:
                df_hc = pd.DataFrame(hist_closer)
                st.line_chart(df_hc[["Data", "nota"]].set_index("Data"))
            else:
                st.info("Nenhuma auditoria da IA gravada para este closer nesta sessão de uso.")
    else:
        st.info("Sincronize a Agenda & Tabela Master para visualizar os gráficos individuais dos closers.")
