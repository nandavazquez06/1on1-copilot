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
    /* Padronização de Títulos */
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
    
    /* Layout dos Cards de Métricas */
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
    
    /* Caixas e Fontes do Playbook de Roteiros */
    .playbook-box {
        background-color: #f8fafc;
        border-left: 4px solid #2563eb;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .playbook-script {
        font-size: 1.02rem !important; /* Tamanho confortável para leitura */
        font-style: normal;
        color: #0f172a;
        background-color: #ffffff;
        padding: 16px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        line-height: 1.65; /* Maior espaçamento entre linhas */
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
        st.markdown('<div class="playbook-box"><div class="playbook-script">"O objetivo desse diagnóstico é detalharmos melhor o seu cenário para eu entender as suas maiores dificuldades para conseguir emprego, e para isso eu vou te fazer algumas perguntas para você me responder com notas de 0 a 10 para avaliarmos o seu momento. Não precisa justificar o motivo da nota por enquanto, depois eu vou te mostrar um gráfico das suas respostas e nós vamos falar mais sobre isso. Eu preciso que você seja BRUTALMENTE SINCERO(A). Posso confiar na sua palavra?"</div></div>', unsafe_allow_html=True)

        st.subheader("3. Devolutiva por Pilares e Faixa de Nota")
        
        st.markdown("**PILAR: MENTALIDADE**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Nota 8 a 10:</b> "Olhando aqui para o seu gráfico, o primeiro ponto que se destaca é a sua Mentalidade com uma nota bem alta. Isso mostra que você não é uma pessoa acomodada, e sabe que a sua carreira não pode mais ficar parada. Você me disse que é dedicado(a), uma pessoa de palavra, e isso é ótimo, porque sem esse compromisso nenhum método funciona… então o seu momento de virar o jogo é agora, porque é essa sua disposição que vai impulsionar todo o resto."<br><br><b>Nota 0 a 7:</b> "A sua nota de Mentalidade ficou baixa e isso me preocupa bastante, porque estou entendendo que as rejeições do mercado abalaram a sua confiança. Você quer mudar de vida, mas na hora de priorizar o seu desenvolvimento e tomar decisões, acaba buscando desculpas. Sem levar a sua carreira como prioridade absoluta, nenhum currículo ou LinkedIn novo vai fazer milagre por você."</div></div>', unsafe_allow_html=True)

        st.markdown("**PILAR: AUMENTO SALARIAL**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Nota 6 a 10:</b> "No pilar de Aumento Salarial, a sua pontuação também foi alta, e isso mostra que você tem uma boa articulação nas empresas, sabe se relacionar com as pessoas, criar pontes e joga bem a dinâmica do ambiente corporativo. Só que não adianta você saber como pedir um aumento salarial, fazer o jogo político ou gerar cases de lucro, se você não consegue uma vaga para mostrar essas habilidades."<br><br><b>Nota 0 a 5:</b> "Sua nota de aumento salarial foi baixa porque provavelmente você sempre enxergou o trabalho só pela parte técnica e operacional, negligenciando a sua gestão de imagem e uma articulação política, e se você não souber construir um mapa de aliados estratégicos, vai acabar sendo ignorado(a) nas promoções e sempre ver profissionais menos qualificados subirem na sua frente."</div></div>', unsafe_allow_html=True)

        st.markdown("**PILAR: CURRÍCULO**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Nota 0 a 5:</b> "No pilar de currículo nós vemos os pontos de alerta para a sua recolocação: a gente percebe que dos currículos que você envia, quase nenhum se transforma em entrevista. Provavelmente o seu material está com descrições genéricas, dizendo \'o que você fazia\', em vez de demonstrar \'o resultado que você gerava para as empresas\'. Então você é um(a) profissional qualificado(a), mas o mercado nem fica sabendo do seu real potencial porque seu currículo não é validado nem pelo robô, nem pelo recrutador."<br><br><b>Nota 6 a 10:</b> "Seu currículo está bem desenhado, focado em métricas e alinhado aos algoritmos, o que justifica a sua alta taxa de retorno. Precisamos fazer pequenos ajustes para cargos mais seniors."</div></div>', unsafe_allow_html=True)

        st.markdown("**PILAR: LINKEDIN**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Nota 0 a 5:</b> "Na parte de LinkedIn, a sua nota foi quase zero, mostrando que você está invisível para os recrutadores e que o seu perfil hoje não aparece nas buscas do LinkedIn Recruiter porque falta uma estratégia para você conseguir abordar os responsáveis pelas vagas (principalmente as ocultas)."<br><br><b>Nota 6 a 10:</b> "O seu perfil no LinkedIn já atua como um ímã de oportunidades, gerando abordagens semanais de headhunters de forma orgânica."</div></div>', unsafe_allow_html=True)

        st.markdown("**PILAR: ENTREVISTAS**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Nota 0 a 5:</b> "Nas Entrevistas temos um efeito dominó: como o seu Currículo e LinkedIn estão travados e você está invisível, você faz poucas entrevistas e não consegue treinar. Nas raras vezes em que você consegue uma oportunidade, a pressão é tão grande por ser \'a única chance\' que você fica nervoso(a) e não consegue contar a sua história da melhor forma. Você sai da entrevista sem ter certeza se foi bem e nunca recebe um feedback assertivo sobre onde errou. Como consequência, você não consegue negociar e aceita qualquer valor, em vez de se posicionar para conquistar o salário que você realmente merece."<br><br><b>Nota 6 a 10:</b> "Sua performance em conversas é excelente: você domina a condução com o gestor e consegue transmitir alta credibilidade e alinhamento cultural nas etapas finais."</div></div>', unsafe_allow_html=True)

        st.subheader("4. Transição para o Pitch")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Olhando agora o seu Raio-X como um todo fica claro que o seu problema NÃO é falta de capacidade técnica e nem falta de vontade. O verdadeiro gargalo é a falta de um método estratégico para a sua carreira, porque você está travado(a) e acaba se esforçando demais, imagino que gasta horas aplicando para vagas e recebe um retorno quase nulo.<br><br>O que nós precisamos fazer agora é reestruturar a sua comunicação para te dar visibilidade, ensinar você a contar a sua história de forma atraente para os recrutadores e gerar mais entrevistas para que você seja contratado(a) nos próximos 51 dias. Faz sentido para você? Você quer mudar esse cenário?"</div></div>', unsafe_allow_html=True)

    with p_tab2:
        st.title("Bloco 2: Apresentação do Programa e Slides")
        
        st.markdown("**SLIDE 1 (HISTÓRIA DO HERÓI RELUTANTE)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"O Ricardo por muito tempo relutou em criar um programa de acompanhamento individual personalizado, porque acreditava que isso iria tomar muito tempo dele e da nossa equipe. Isso porque nós já temos um método só com aulas gravadas que ajuda muitas pessoas, mas chegou um momento em que não eram essas muitas pessoas que preocupavam ele... e sim o fato de ter um monte de gente aplicando esse método sem ter o acompanhamento necessário para aumentar a taxa de aprovação em processos seletivos e, mais do que isso, ajudar as pessoas a crescer na carreira a longo prazo.<br><br>E olha, a gente sabe que acompanhar é diferente de só ensinar, e conversando com alguns alunos muitos pediam algo mais personalizado para conseguir o novo emprego mais rápido. Então ouvir das pessoas que elas precisavam se recolocar urgente fez o Ric pensar... e se eu criasse um programa de acompanhamento personalizado, para a gente realmente pegar as pessoas pela mão, analisar o que elas estão fazendo e para ajudar elas a fazerem o que realmente precisam fazer.<br><br>E aí ele olhou para o próprio cenário, porque ele está em vários programas de acompanhamento que ajudam ele a acelerar os resultados, então ele pensou: Por que não criar o MEU acelerador de resultados? Então hoje nós temos esse programa já com um número bom de alunos, porque quando mostramos isso para as pessoas, várias falaram: \'nossa, era isso que eu precisava!\'.<br><br>E agora eu quero saber: posso te mostrar o nosso programa de acompanhamento que vai te ajudar a melhorar seu LinkedIn e currículo, aumentando a taxa de aprovação nas entrevistas para no futuro você ter mais chances de conseguir um aumento salarial?"</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 2 (O QUE É A CRH)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"A CRH é um programa de aceleração de carreira onde você vai receber o nosso direcionamento, acompanhamento e feedbacks personalizados durante o período de 12 meses, para conseguir empregos em até 51 dias e ter aumentos salariais nas suas futuras empresas. É um programa feito para profissionais em transição de carreira, pessoas que perderam o emprego ou que ocupam cargos operacionais e querem chegar a posições de liderança. Nesse programa, você implementa um método estruturado para conseguir o seu emprego ideal em até 51 dias, alcançar o cargo que você deseja e superar os X mil reais (pretensão salarial) mensais com aumentos estratégicos."</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 3 (DEPOIMENTOS)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Aqui eu quero te mostrar alguns depoimentos de pessoas que conseguiram a sua recolocação aplicando o método que usamos com os alunos da CRH. No Youtube nós temos uma playlist com mais de 200 desses dedicados especialistas, mas separamos algumas das histórias para poder te inspirar e você entender melhor como ajudamos essas pessoas com o nosso acompanhamento".<br><br>*(Conteúdo do Slide)*<br><br>E aí, qual desses depoimentos mais te marcou?</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 43 a 48 (Pilar: DIREIONAMENTO)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Slide 43:</b> "Dentro da CRH nós temos 4 pilares que vão te ajudar a conseguir seu novo emprego mais rápido: Direcionamento, Acompanhamento, Ferramentas e Comunidade"<br><br><b>Slide 44:</b> "No pilar de Direcionamento, nós vamos entender onde você quer chegar e em quanto tempo, e traçar um plano de ação estratégico com tudo o que você precisa fazer para conseguir a sua recolocação dentro da meta de tempo que for estabelecida pela sua necessidade".<br><br><b>Slide 45:</b> "Então como nós vamos mapear isso? A primeira coisa é o Direcionamento Estratégico, para virar a chave de sempre ter uma tempestade de negativas para as vagas. Em uma sessão individual nós vamos avaliar o seu histórico profissional, travas, cargo e salário ideal, e você vai aprender só o necessário, sem perder tempo e dinheiro, para avançar nos processos seletivos com segurança e receber mais propostas de entrevista. Então a mentora vai te indicar quais são as aulas que você precisa assistir para melhorar o seu Currículo e LinkedIn de uma forma efetiva".<br><br><b>Slide 46:</b> "E aí, você vai ter acesso a dois cursos dentro de uma plataforma online: um de emprego, e um de aumento. Todos os alunos que conseguiram recolocação em até 51 dias tiveram acesso a esse treinamento aqui, então você vai conseguir emprego rápido com as aulas que nós vamos te indicar, sem ficar perdido(a) porque não tem direcionamento e um método estruturado que funciona".<br><br><b>Slide 47:</b> "Finalizando os ajustes das aulas no Currículo e LinkedIn, nós fazemos com você uma sessão individual para avaliar o seu novo material. Então antes de você sair se aplicando para as vagas gastando tempo sem ter resultado, nós te ajudamos a arrumar a casa para você ter uma segurança de que o Currículo e LinkedIn estão prontos para você se inscrever e conseguir gerar entrevistas".<br><br><b>Slide 48:</b> "E você se aplicando para as vagas com um currículo que dá resultado, vai começar a aparecer entrevista. E aí, o que nós vamos fazer? Te direcionar nessa etapa também. Então quando você passar para a entrevista, vai ter uma simulação individual com 2 mentores. O objetivo aqui é que você tenha feedbacks personalizados e brutalmente sinceros para aquela entrevista específica, com base na descrição da vaga e cultura da empresa, então você não vai mais ficar sem feedback".</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 49 a 53 (Pilar: ACOMPANHAMENTO)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Slide 49:</b> "E como eu falei lá nos pilares da CRH, além de te direcionar nós te acompanhamos sempre olhando os resultados e fazendo análises da sua estratégia sempre que necessário para destravar todas as dificuldades e gargalos no seu processo de buscar emprego".<br><br><b>Slide 50:</b> "E aí, hoje quem está na nossa mentoria tem acesso a um sistema para a gente poder olhar com estratégia para cada uma das vagas em que a pessoa se candidatou e retirar os gargalos dos processos seletivos. Então nesse aplicativo que você vai ter disponível, tem uma ferramenta que te ajuda a fazer uma gestão melhor das suas vagas e você consegue acompanhar o andamento dos processos seletivos de uma forma mais organizada e controlada, e a gente te acompanha para entender se a estratégia que planejamos está dando certo, então você não fica sozinho(a)".<br><br><b>Slide 51:</b> "E nós também vamos te acompanhar com grupos no WhatsApp. Hoje todos os alunos têm acesso à nossa equipe de forma individual, para que consiga ser acompanhado em qualquer dificuldade nesse processo de empregabilidade de forma mais efetiva. Então você pode mandar áudios depois de uma entrevista contando como foi, por exemplo, e a gente vai te direcionando sobre os próximos passos, até você receber a sua proposta de emprego".<br><br><b>Slide 52 & 53:</b> "Nessa mesma linha, nós orientamos pedir 48h depois de receber a proposta da empresa para analisar. E nesse período de 48h nós aproveitamos para fazer com você um plantão de negociação salarial no WhatsApp, te acompanhando para conseguir aumentar o valor da proposta. A Gabi conseguiu negociar e aumentou R$4.500 no salário todos os meses usando esse método aqui. Então vamos supor que você recebeu uma proposta para ganhar R$XXXX (pretensão salarial da pessoa), o nosso objetivo vai ser você chegar nos R$XXXX (4.000 a mais do que a pretensão). E não foi só a Gabi, a Claudia aumentou 1k, a Jessica foi de 8k para 10k, e o José conseguiu aumentar 1.2k todos os meses!"</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 54 a 57 (Pilar: FERRAMENTAS)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Slide 54 & 55:</b> "Além de te direcionar e acompanhar, nós vamos te dar ferramentas para você sempre evoluir no processo de empregabilidade. Uma das ferramentas é o buscador de vagas no APP Ricarreira, para pesquisar a nomenclatura e filtrar por estado e cidade para encontrar as vagas disponíveis no mercado em todos os ATS."<br><br><b>Slide 56 & 57:</b> "Você também terá o acervo de currículos campeões para se inspirar em currículos de 1 página dos nossos alunos validados. Além disso, terá uma biblioteca de mensagens para falar com recrutadores e mais de 10 ferramentas para acelerar o processo para se recolocar em até 51 dias."</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 58 a 60 (Pilar: COMUNIDADE & DAILIES)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Slide 58:</b> "E falando um pouco sobre a comunidade, a ideia aqui é ter sempre uma inteligência coletiva, porque o trabalho de quem está desempregado é buscar trabalho."<br><br><b>Slide 59 & 60:</b> "Fazemos reuniões diárias: de segunda a sexta às 9h tem a Daily de arrumar a casa para avaliação de currículo e LinkedIn. E de segunda a sexta às 11h tem a Daily de empregabilidade com o Ric para tirar dúvidas de aplicação, networking e entrevistas. Essa Daily é a parte mais rica da CRH para conseguir emprego rápido."</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 64 a 68 (BÔNUS DE AUMENTO)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"De bônus você vai ter todo o acompanhamento na próxima empresa para conseguir o seu aumento. Acompanhamos nos primeiros 30 dias com sessão individual e grupo no WhatsApp, mapeamos os aliados estratégicos no organograma e ajudamos a construir CASEs de lucro para você apresentar no Shark Tank do Aumento Salarial antes da conversa com a sua liderança."</div></div>', unsafe_allow_html=True)

    with p_tab3:
        st.title("Bloco 3: Oferta & Quebra de Objeções")
        
        st.markdown("**SLIDE 71 a 74 (Transição, Formações & Calculadora)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Slide 71:</b> "E agora, (Nome da pessoa), eu queria te ouvir: a CRH faz sentido para você?"<br><i>- Esperar responder SIM.</i><br>"De 0 a 10, o quanto você diria que tudo o que eu te apresentei aqui vai te ajudar a resolver a sua maior dificuldade hoje?"<br><i>- Esperar responder 10 (Se menos, perguntar o que falta).</i><br><br><b>Slide 73 (Formações):</b> "Hoje a gente fala que a CRH vale mais do que uma faculdade ou pós. Você lembra quanto investiu nas suas formações? E com esses R$XXXX você teve direcionamento, acompanhamento e feedback individual? Não, né? As formações não têm esse acompanhamento de carreira e acabamos ficando invisíveis no mercado."<br><br><b>Slide 74 (Calculadora Tempo é Dinheiro):</b> "Na calculadora do \'tempo é dinheiro\', com sua pretensão de R$XXXX, por ano você quer ganhar R$XXXX, certo? A cada dia sem emprego são R$XXX a menos, e cada semana sem acompanhamento e feedback são R$XXXX saindo do seu bolso. Se chegar na semana que vem sem perspectiva, você está confortável em perder mais R$XXXX?"</div></div>', unsafe_allow_html=True)

        st.markdown("**SLIDE 75 a 80 (Apresentação da Oferta & Sinal de R$ 500)**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Slide 75 & 76:</b> "A mentoria valeria R$51.000 se fosse só com o Ric. Com toda a nossa equipe de mentores por trás, reduzimos muito esse valor."<br><br><b>Slide 77 & 78:</b> "Para você ter esse nível de acompanhamento, colocamos uma entrada de R$500 para garantir a sua vaga. Só depois de uma semana a equipe entra em contato para alinhar o restante. Nesse período você já tem acesso a tudo: +100 aulas, 10 Dailys, ferramentas e direcionamento estratégico. R$500 é um valor acessível para você hoje?"<br><br><b>Slide 79 & 80:</b> "Falando sobre o pós, ficam parcelas de 955 no recorrente (sem tomar o limite total) ou 9.500 à vista no cartão. Mas isso você só decide daqui a 1 semana. Agora são só os R$500. E aí?"</div></div>', unsafe_allow_html=True)

        st.subheader("Roteiro Completo de Quebra de Objeções")

        st.markdown("**🔴 OBJEÇÃO DE PARCELAS / PÓS / MEDO DE NÃO CONSEGUIR:**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Lead:</b> "Preciso pensar por conta do valor das parcelas de 955 depois, eu não tenho isso tudo agora, preciso da minha reserva para sobreviver..."<br><b>Closer:</b> "O que você precisa pensar? Agora a única coisa que você precisa são os R$500, que você me falou que tem. Você dá a entrada, assiste às aulas, participa das Dailys e tem seu direcionamento estratégico. É melhor ficar uma semana sendo acompanhado(a) ou passar mais esses dias tentando sozinho(a) sem resultado?"<br><br><b>Lead:</b> "É, mas estou preocupado com o pós, não tenho dinheiro para pagar as parcelas."<br><b>Closer:</b> "A gente viu na calculadora que você vai ganhar R$XXX por dia no seu novo emprego. Será que não vale a pena fazer esse investimento e com o seu trabalho ir pagando as parcelas? Quando você se recolocar, essas parcelas dá para pagar."<br><br><b>Lead:</b> "E se eu investir e não conseguir o emprego rápido?"<br><b>Closer:</b> "E se você continuar no mesmo cenário e não conseguir entrevista nos próximos 30 dias, quanto dinheiro você vai perder? São R$XXXX (Tempo é dinheiro). Você me falou que era prioridade e de palavra, conseguir emprego não é prioridade então?<br>Além disso, você não precisa pensar no restante agora. Com a entrada de R$500 a gente até te ajuda a pensar na forma de pagamento em uma semana. E você tem a garantia condicional de 1 ano para ter seu dinheiro de volta caso o método não funcione!"</div></div>', unsafe_allow_html=True)

        st.markdown("**🔴 OBJEÇÃO DE CÔNJUGE (MARIDO / ESPOSA):**")
        st.markdown('<div class="playbook-box"><div class="playbook-script"><b>Lead:</b> "Eu não consigo fazer esse investimento sem falar com meu marido/minha esposa."<br><b>Closer:</b> "Mas você não me falou que seu marido/sua esposa te apoiava?"<br><b>Lead:</b> "Sim, apoia. Mas não posso tomar essa decisão sem discutirmos antes."<br><br><b>Closer:</b> "Certo. Mas ele(a) não entende a sua dor. Será que se olhar o seu diagnóstico, ele(a) entende como é ficar navegando horas sem resultados e ter chuva de negativas na Gupy todos os dias? Não entende.<br>Então é óbvio que ele(a) vai olhar esse valor e falar: \'Tá caro\'. Porque não entende a sua dor como a gente entende. E você falou que R$500 vocês têm… às vezes seu marido/sua esposa vai até preferir que você entre, conheça a mentoria por dentro, e você vai ganhando mais confiança para argumentar com ele(a) sobre o restante."</div></div>', unsafe_allow_html=True)

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
    closers_alvo = ["Fernanda", "Ricardo", "Renata", "Thiago"]
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
- Quebra-gelo & Conexão: Fez pergunta de acolhimento ativa explorando o momento do lead/LinkedIn?
- Acordo de Objetividade Flexível: Mencionar que a pessoa não precisa justificar todas as notas é uma boa prática para manter o controle do tempo, MAS O CLOSER TEM LIBERDADE PARA APROFUNDAR e perguntar "por quê" em notas chave quando quiser entender melhor o cenário e escavar dores.
- Raio-X dos 5 Pilares: Passou por Currículo, LinkedIn, Entrevistas, Aumento Salarial e Mentalidade? Avaliou as respostas por notas (0 a 10) dando o retorno correto de acordo com a faixa?
- Leitura do Gráfico: Compartilhou a tela mostrando APENAS o gráfico e utilizou a narrativa padronizada conectando que Mentalidade e Desejo de Salário só geram resultado se Currículo, LinkedIn e Entrevistas estiverem destravados? Encerrou perguntando se o lead concorda e quer mudar o cenário com urgência?

📍 BLOCO 2: APRESENTAÇÃO DO PROGRAMA & SLIDES (Minuto 20 ao 40)
- História do Herói Relutante (Slide 1): Utilizou a copy oficial explicando por que o Ricardo relutou em criar um programa individual ("Acompanhar é diferente de só ensinar", "Ouvir que precisavam se recolocar urgente")?
- Definição do Programa (Slide 2): Apresentou a CRH como programa de aceleração de 12 meses focado em recolocação em 51 dias e aumento salarial?
- Apresentação de Pilares vs. Entregáveis (Slides 43 a 68): Apresentou os 4 pilares (Direcionamento, Acompanhamento, Ferramentas e Comunidade), detalhando as Dailies (9h e 11h), App Ricarreira, buscador de vagas ATS, acervo de currículos e bônus de aumento salarial?

📍 BLOCO 3: PITCH, ANCORAGEM & QUEBRA DE OBJEÇÕES (Minuto 40 ao 60)
- Checagem e Qualificação (Slide 71): Perguntou "De 0 a 10 o quanto tudo o que apresentei vai te ajudar a resolver sua maior dificuldade hoje?"?
- DETECÇÃO DE CONFRONTO DE FORMAÇÕES (SLIDE 73): Discutiu o investimento prévio em formações/cursos para mostrar falta de investimento em CARREIRA/MENTALIDADE?
- DETECÇÃO DA CALCULADORA "TEMPO É DINHEIRO" (SLIDE 74): Abordou a pretensão salarial e desdobrou valores em ganho/perda anual, semanal ou diário?
- Foco na Entrada de R$ 500,00 (Slides 77 e 78): Conduziu a oferta focando no valor acessível de R$ 500,00 para garantir a vaga agora (com saldo para 1 semana em parcelas de 955)?
- DETECÇÃO CONDICIONAL DE OBJEÇÕES: Se o lead mencionou parcelas do pós, reserva ou cônjuge/família, usou o reframe oficial. Se não mencionou cônjuge, NÃO COBRE esta etapa.

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
    
    closer_selecionado = st.selectbox("Selecione o Closer para Análise Individual:", ["Fernanda", "Ricardo", "Renata", "Thiago"])
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
