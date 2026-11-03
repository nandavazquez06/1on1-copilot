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
    if df is None or df.empty:
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
        if values and len(values) > 1:
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

# ==============================================================
# ABA 1: ROTEIROS & PLAYBOOK DE BOLSO (100% FIEL AO GOOGLE DOCS)
# ==============================================================
with tab1:
    st.header("📚 Roteiros & Playbook de Bolso")
    st.caption("Consulte na íntegra as falas, devoluções de Raio-X por notas, slides e quebras de objeção.")
    
    p_tab1, p_tab2, p_tab3 = st.tabs([
        "📍 Bloco 1: Acolhimento & Raio-X", 
        "📍 Bloco 2: Apresentação do Programa e Slides", 
        "📍 Bloco 3: Oferta & Quebra de Objeções"
    ])
    
    with p_tab1:
        st.subheader("Bloco 1: Acolhimento & Raio-X")
        
        st.markdown("**1. Quebrando o Gelo & Acolhimento**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Oi, (nome da pessoa)! Tudo bem?”<br>
            “De onde você fala?”<br><br>
            <b>Acolhimento</b><br>
            "Vi no seu LinkedIn que o seu último trabalho foi na [Empresa/Setor], né?”<br><br>
            <b>Expectativa</b><br>
            “Me conta um pouquinho de como está o seu momento atual?”<br>
            “E o que você está buscando para os próximos passos da sua carreira?"
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**2. Acordo Inicial do Raio-X**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “O objetivo desse diagnóstico é detalharmos melhor o seu cenário para eu entender as suas maiores dificuldades para conseguir emprego, e para isso eu vou te fazer algumas perguntas para você me responder com notas de 0 a 10 para avaliarmos o seu momento. Não precisa justificar o motivo da nota por enquanto, depois eu vou te mostrar um gráfico das suas respostas e nós vamos falar mais sobre isso. Eu preciso que você seja BRUTALMENTE SINCERO(A). Posso confiar na sua palavra?"
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**3. Devolutiva por Pilares e Faixa de Nota**")
        
        st.markdown("**PILAR: MENTALIDADE**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Nota 8 a 10:</b> "Olhando aqui para o seu gráfico, o primeiro ponto que se destaca é a sua Mentalidade com uma nota bem alta. Isso mostra que você não é uma pessoa acomodada, e sabe que a sua carreira não pode mais ficar parada. Você me disse que é dedicado(a), uma pessoa de palavra, e isso é ótimo, porque sem esse compromisso nenhum método funciona… então o seu momento de virar o jogo é agora, porque é essa sua disposição que vai impulsionar todo o resto."<br><br>
            <b>Nota 0 a 7:</b> "A sua nota de Mentalidade ficou baixa e isso me preocupa bastante, porque estou entendendo que as rejeições do mercado abalaram a sua confiança. Você quer mudar de vida, mas na hora de priorizar o seu desenvolvimento e tomar decisões, acaba buscando desculpas. Sem levar a sua carreira como prioridade absoluta, nenhum currículo ou LinkedIn novo vai fazer milagre por você."
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**PILAR: AUMENTO SALARIAL**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Nota 6 a 10:</b> "No pilar de Aumento Salarial, a sua pontuação também foi alta, e isso mostra que você tem uma boa articulação nas empresas, sabe se relacionar com as pessoas, criar pontes e joga bem a dinâmica do ambiente corporativo. Só que não adianta você saber como pedir um aumento salarial, fazer o jogo político ou gerar cases de lucro, se você não consegue uma vaga para mostrar essas habilidades."<br><br>
            <b>Nota 0 a 5:</b> "Sua nota de aumento salarial foi baixa porque provavelmente você sempre enxergou o trabalho só pela parte técnica e operacional, negligenciando a sua gestão de imagem e uma articulação política, e se você não souber construir um mapa de aliados estratégicos, vai acabar sendo ignorado(a) nas promoções e sempre ver profissionais menos qualificados subirem na sua frente."
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**PILAR: CURRÍCULO**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Nota 0 a 5:</b> "No pilar de currículo nós vemos os pontos de alerta para a sua recolocação: a gente percebe que dos currículos que você envia, quase nenhum se transforma em entrevista. Provavelmente o seu material está com descrições genéricas, dizendo 'o que você fazia', em vez de demonstrar 'o resultado que você gerava para as empresas'. Então você é um(a) profissional qualificado(a), mas o mercado nem fica sabendo do seu real potencial porque seu currículo não é validado nem pelo robô, nem pelo recrutador."<br><br>
            <b>Nota 6 a 10:</b> "Seu currículo está bem desenhado, focado em métricas e alinhado aos algoritmos, o que justifica a sua alta taxa de retorno. Precisamos fazer pequenos ajustes para cargos mais seniors."
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**PILAR: LINKEDIN**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Nota 0 a 5:</b> "Na parte de LinkedIn, a sua nota foi quase zero, mostrando que você está invisível para os recrutadores e que o seu perfil hoje não aparece nas buscas do LinkedIn Recruiter porque falta uma estratégia para você conseguir abordar os responsáveis pelas vagas (principalmente as ocultas)."<br><br>
            <b>Nota 6 a 10:</b> "O seu perfil no LinkedIn já atua como um ímã de oportunidades, gerando abordagens semanais de headhunters de forma orgânica."
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**PILAR: ENTREVISTAS**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Nota 0 a 5:</b> "Nas Entrevistas temos um efeito dominó: como o seu Currículo e LinkedIn estão travados e você está invisível, você faz poucas entrevistas e não consegue treinar. Nas raras vezes em que você consegue uma oportunidade, a pressão é tão grande por ser 'a única chance' que você fica nervoso(a) e não consegue contar a sua história da melhor forma. Você sai da entrevista sem ter certeza se foi bem e nunca recebe um feedback assertivo sobre onde errou. Como consequência, você não consegue negociar e aceita qualquer valor, em vez de se posicionar para conquistar o salário que você realmente merece."<br><br>
            <b>Nota 6 a 10:</b> "Sua performance em conversas é excelente: você domina a condução com o gestor e consegue transmitir alta credibilidade e alinhamento cultural nas etapas finais."
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**TRANSIÇÃO PARA O PITCH ANTES DA HISTÓRIA DO HERÓI RELUTANTE**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            "Olhando agora o seu Raio-X como um todo fica claro que o seu problema NÃO é falta de capacidade técnica e nem falta de vontade. O verdadeiro gargalo é a falta de um método estratégico para a sua carreira, porque você está travado(a) e acaba se esforçando demais, imagino que gasta horas aplicando para vagas e recebe um retorno quase nulo.<br><br>
            O que nós precisamos fazer agora é reestruturar a sua comunicação para te dar visibilidade, ensinar você a contar a sua história de forma atraente para os recrutadores e gerar mais entrevistas para que você seja contratado(a) nos próximos 51 dias. Faz sentido para você? Você quer mudar esse cenário?"
            </div>
        </div>
        """, unsafe_allow_html=True)

    with p_tab2:
        st.subheader("Bloco 2: Apresentação do Programa e Slides")
        
        st.markdown("**SLIDE 1 (HISTÓRIA DO HERÓI RELUTANTE)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            "O Ricardo por muito tempo relutou em criar um programa de acompanhamento individual personalizado, porque acreditava que isso iria tomar muito tempo dele e da nossa equipe. Isso porque nós já temos um método só com aulas gravadas que ajuda muitas pessoas, mas chegou um momento em que não eram essas muitas pessoas que preocupavam ele... e sim o fato de ter um monte de gente aplicando esse método sem ter o acompanhamento necessário para aumentar a taxa de aprovação em processos seletivos e, mais do que isso, ajudar as pessoas a crescer na carreira a longo prazo.<br><br>
            E olha, a gente sabe que acompanhar é diferente de só ensinar, e conversando com alguns alunos muitos pediam algo mais personalizado para conseguir o novo emprego mais rápido. Então ouvir das pessoas que elas precisavam se recolocar urgente fez o Ric pensar... e se eu criasse um programa de acompanhamento personalizado, para a gente realmente pegar as pessoas pela mão, analisar o que elas estão fazendo e para ajudar elas a fazerem o que realmente precisam fazer.<br><br>
            E aí ele olhou para o próprio cenário, porque ele está em vários programas de acompanhamento que ajudam ele a acelerar os resultados, então ele pensou: Por que não criar o MEU acelerador de resultados? Então hoje nós temos esse programa já com um número bom de alunos, porque quando mostramos isso para as pessoas, várias falaram: 'nossa, era isso que eu precisava!'.<br><br>
            E agora eu quero saber: posso te mostrar o nosso programa de acompanhamento que vai te ajudar a melhorar seu LinkedIn e currículo, aumentando a taxa de aprovação nas entrevistas para no futuro você ter mais chances de conseguir um aumento salarial?”
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 2 (O QUE É A CRH)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “A CRH é um programa de aceleração de carreira onde você vai receber o nosso direcionamento, acompanhamento e feedbacks personalizados durante o período de 12 meses, para conseguir empregos em até 51 dias e ter aumentos salariais nas suas futuras empresas. É um programa feito para profissionais em transição de carreira, pessoas que perderam o emprego ou que ocupam cargos operacionais e querem chegar a posições de liderança. Nesse programa, você implementa um método estruturado para conseguir o seu emprego ideal em até 51 dias, alcançar o cargo que você deseja e superar os X mil reais (pretensão salarial) mensais com aumentos estratégicos”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 3 (DEPOIMENTOS)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            "Aqui eu quero te mostrar alguns depoimentos de pessoas que conseguiram a sua recolocação aplicando o método que usamos com os alunos da CRH. No Youtube nós temos uma playlist com mais de 200 desses dedicados especialistas, mas separamos algumas das histórias para poder te inspirar e você entender melhor como ajudamos essas pessoas com o nosso acompanhamento”.<br><br>
            (Conteúdo do Slide)<br><br>
            E aí, qual desses depoimentos mais te marcou?
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 43 (4 PILARES)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Dentro da CRH nós temos 4 pilares que vão te ajudar a conseguir seu novo emprego mais rápido: Direcionamento, Acompanhamento, Ferramentas e Comunidade”
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 44 (O QUE É DIRECIONAMENTO)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “No pilar de Direcionamento, nós vamos entender onde você quer chegar e em quanto tempo, e traçar um plano de ação estratégico com tudo o que você precisa fazer para conseguir a sua recolocação dentro da meta de tempo que for estabelecida pela sua necessidade”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 45**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Então como nós vamos mapear isso? A primeira coisa é o Direcionamento Estratégico, para virar a chave de ter sempre uma tempestade de negativas para as vagas. Em uma sessão individual nós vamos avaliar o seu histórico profissional, travas, cargo e salário ideal, e você vai aprender só o necessário, sem perder tempo e dinheiro, para avançar nos processos seletivos com segurança e receber mais propostas de entrevista. Então a mentora vai te indicar quais são as aulas que você precisa assistir para melhorar o seu Currículo e LinkedIn de uma forma efetiva”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 46**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E aí, você vai ter acesso a dois cursos dentro de uma plataforma online: um de emprego, e um de aumento. Todos os alunos que conseguiram recolocação em até 51 dias tiveram acesso a esse treinamento aqui, então você vai conseguir emprego rápido com as aulas que nós vamos te indicar, sem ficar perdido(a) porque não tem direcionamento e um método estruturado que funciona”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 47**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Finalizando os ajustes das aulas no Currículo e LinkedIn, nós fazemos com você uma sessão individual para avaliar o seu novo material. Então antes de você sair se aplicando para as vagas gastando tempo sem ter resultado, nós te ajudamos a arrumar a casa para você ter uma segurança de que o Currículo e LinkedIn estão prontos para você se inscrever e conseguir gerar entrevistas”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 48**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E você se aplicando para as vagas com um currículo que dá resultado, vai começar a aparecer entrevista. E aí, o que nós vamos fazer? Te direcionar nessa etapa também. Então quando você passar para a entrevista, vai ter uma simulação individual com 2 mentores. O objetivo aqui é que você tenha feedbacks personalizados e brutalmente sinceros para aquela entrevista específica, com base na descrição da vaga e cultura da empresa, então você não vai mais ficar sem feedback”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 49 (O QUE É ACOMPANHAMENTO)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E como eu falei lá nos pilares da CRH, além de te direcionar nós te acompanhamos sempre olhando os resultados e fazendo análises da sua estratégia sempre que necessário para destravar todas as dificuldades e gargalos no seu processo de buscar emprego”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 50**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E aí, hoje quem está na nossa mentoria tem acesso a um sistema para a gente poder olhar com estratégia para cada uma das vagas em que a pessoa se candidatou e retirar os gargalos dos processos seletivos. Então nesse aplicativo que você vai ter disponível, tem uma ferramenta que te ajuda a fazer uma gestão melhor das suas vagas e você consegue acompanhar o andamento dos processos seletivos de uma forma mais organizada e controlada, e a gente te acompanha para entender se a estratégia que planejamos está dando certo, então você não fica sozinho(a)”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 51**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E nós também vamos te acompanhar com grupos no WhatsApp. Hoje todos os alunos têm acesso à nossa equipe de forma individual, para que consiga ser acompanhado em qualquer dificuldade nesse processo de empregabilidade de forma mais efetiva. Então você pode mandar áudios depois de uma entrevista contando como foi, por exemplo, e a gente vai te direcionando sobre os próximos passos, até você receber a sua proposta de emprego”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 52**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Nessa mesma linha, nós orientamos pedir 48h depois de receber a proposta da empresa para analisar. E nesse período de 48h nós aproveitamos para fazer com você um plantão de negociação salarial no WhatsApp, te acompanhando para conseguir aumentar o valor da proposta. A Gabi conseguiu negociar e aumentou R$4.500 no salário todos os meses usando esse método aqui. Então vamos supor que você recebeu uma proposta para ganhar R$XXXX (pretensão salarial da pessoa), o nosso objetivo vai ser você chegar nos R$XXXX (4.000 a mais do que a pretensão)”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 53**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E não foi só a Gabi que conseguiu isso, várias pessoas da comunidade já deram depoimentos. A Claudia aumentou 1k, a Jessica foi de 8k para 10k, e o José conseguiu aumentar 1.2k todos os meses, e seriam quase 16k que ficariam na mesa se não tivesse o plantão de negociação salarial”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 54 (O QUE SÃO FERRAMENTAS)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Além de te direcionar e acompanhar, nós vamos te dar ferramentas para você sempre evoluir no processo de empregabilidade. Então eu já te falei um pouco sobre o sistema que a gente tem aqui na CRH, que é o APP Ricarreira, com funcionalidades que vão te ajudar a otimizar seu tempo”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 55**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E aí, uma das ferramentas que você vai ter acesso é o buscador de vagas, para pesquisar a nomenclatura e filtrar por estado e cidade para encontrar as vagas disponíveis no mercado em todos os ATS. Aqui você vai poder ver as descrições, os sites em que as vagas foram publicadas e se inscrever naquelas que mais fizerem sentido para o que você está buscando”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 56**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E tem uma outra ferramenta que vai te ajudar muito principalmente nessa etapa inicial de arrumar a casa, que é o acervo de currículos campeões. Aqui você vai poder se inspirar em vários currículos de 1 página dos nossos alunos, que já foram validados e aprovados nos sites de vagas”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 57**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Além dessas ferramentas que eu dei mais ênfase aqui, você vai ter disponíveis mais de 10 ferramentas para você explorar nesse período de 1 ano. E é muito legal porque você vai ter por exemplo uma biblioteca de mensagens que vai poupar o seu tempo na hora de falar com um recrutador, com modelos prontos para adaptar ao seu cenário. E todas essas funcionalidades aqui foram criadas com esse objetivo de acelerar o processo e tornar tudo mais prático para que você consiga a sua recolocação em até 51 dias”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 58 (O QUE É COMUNIDADE)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E falando um pouco sobre o pilar de comunidade, apesar de a CRH ser uma mentoria individual, tem outras pessoas que estão buscando emprego também, e para nós é muito importante não deixar as pessoas desempregadas em casa sozinhas buscando emprego no dia a dia, sem fazer uma troca para ter ajuda e discutir o que está dando certo ou errado. Então a ideia aqui é ter sempre uma inteligência coletiva, porque o trabalho de quem está desempregado é buscar trabalho”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 59**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Então pensando nisso, nós fazemos reuniões diárias com a galera que está buscando emprego. De segunda a sexta às 9h, tem uma Daily de arrumar a casa para as pessoas que entraram no método recentemente receberem avaliação de currículo e LinkedIn todos os dias. Essas Dailys são no mesmo horário do Ricafé, reparou? O objetivo é você parar de participar das lives gratuitas, porque o conteúdo fica superficial. Agora que você vai entrar na mentoria, é realmente para focar no que nós vamos construir juntos aqui na mentoria”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 60**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E de segunda a sexta às 11h tem a Daily de empregabilidade com o Ric, que é para quem já está com a casa arrumada e tem dúvidas de aplicação, networking, entrevistas. Então a ideia é tirar essas dúvidas para destravar o momento de atacar, e essa Daily é a parte mais rica da CRH, porque o pessoal sempre traz coisas novas que estão gerando resultado para conseguir emprego rápido”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 64 (BÔNUS DE AUMENTO)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Eu foquei na parte de emprego aqui na apresentação porque é também o seu foco agora, mas de bônus você vai ter todo o acompanhamento na próxima empresa para conseguir o seu aumento.”
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 65**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Então nós vamos te acompanhar nos primeiros 30 dias de empresa com uma sessão individual e um grupo no WhatsApp para já começar a acelerar a sua carreira, analisando o cenário e mapeando aliados estratégicos que vão te ajudar a crescer de forma rápida”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 66**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E nesse mapeamento de aliados, nós vamos avaliar juntos ao longo do tempo quem devem ser as pessoas do organograma da empresa para você fazer o jogo político para garantir um aumento”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 67**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Além disso, vamos te ajudar a não deixar a sua carreira de lado fazendo sessões individuais para indicar quais CASEs você precisa construir todo mês dentro da empresa para não ficar só apagando incêndio e conseguir esse aumento rápido mostrando resultados reais”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 68**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E a ideia é inclusive usar esses CASEs para pedir o aumento lá na frente, que é quando nós vamos fazer o shark tank do aumento salarial para 2 mentores te orientarem sobre o que você precisa fazer na sua apresentação de pedido de aumento antes de você ter a conversa com a sua liderança”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 71**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E agora, (Nome da pessoa), eu queria te ouvir: a CRH faz sentido para você?”<br>
            - Esperar a pessoa responder SIM<br><br>
            “Legal! Então de 0 a 10, o quanto você diria que tudo o que eu te apresentei aqui vai te ajudar a resolver a sua maior dificuldade hoje?”<br>
            - Esperar a pessoa responder 10 (Se for menos, perguntar o que falta para ser 10).<br>
            - Quebrar as objeções antes de passar para a oferta.<br><br>
            “Maravilha. E eu acho de verdade que pelo seu momento atual, a CRH faz muito sentido para você, principalmente porque você vai receber feedback de uma forma que nunca recebeu, e isso é o que realmente vai mudar o jogo, não só para você conseguir o seu emprego, mas depois dentro da empresa também. Ninguém tem essa cultura de dar feedbacks brutalmente sinceros, e a gente tem”.<br><br>
            - Se já tiver objeção do dinheiro ("faz sentido mas depende do valor do investimento")<br><br>
            - “Certo, eu vou te apresentar as condições de pagamentos e preciso que você seja brutalmente sincero(a), tá? Se não fizer sentido para você financeiramente me fala aqui, porque a gente só tem mais X cadeiras disponíveis para esse mês”.<br><br>
            - “Se você não conseguir pegar uma dessas cadeiras não tem problema, porque nossa equipe está falando com outras pessoas e a gente passa a cadeira pra frente... Mas eu acredito que pelo raio X que a gente fez aqui, você precisa de verdade desse nível de acompanhamento, concorda? É o que vai mudar o jogo para você, né?”
            </div>
        </div>
        """, unsafe_allow_html=True)

    with p_tab3:
        st.subheader("Bloco 3: Oferta & Quebra de Objeções")
        
        st.markdown("**SLIDE 72**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Mas já que faz sentido, deixa eu te passar o investimento para ter o nosso acompanhamento”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 73 (FORMAÇÕES)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Hoje a gente fala que a CRH vale mais do que uma faculdade, pós graduação, MBA. Você lembra quanto investiu nas suas formações?”<br><br>
            - Esperar a pessoa responder o valor.<br><br>
            “Entendi. E com esses R$XXXX (valor apresentado), você teve direcionamento, acompanhamento e feedback individual? Alguém te ensinou a buscar emprego, ou conseguir um aumento salarial?”<br><br>
            - Esperar a pessoa responder NÃO.<br><br>
            “Então, a gente fala que a CRH vale mais justamente por isso, geralmente as formações não tem mesmo esse acompanhamento próximo de carreira, e nós acabamos tendo títulos para, muitas vezes, continuar invisível no mercado, não passar nas entrevistas e ficar perdendo dinheiro”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 74 (TEMPO É DINHEIRO)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Nós temos aqui inclusive a calculadora do “tempo é dinheiro”, que mostra a sua pretensão salarial de R$XXXX (pretensão salarial da pessoa). E se a gente olhar aqui, isso quer dizer que por ano você quer ganhar R$XXXX (valor da calculadora), certo?”<br><br>
            “Então, conseguindo a sua recolocação, você vai estar ganhando esse valor por ano, R$XXX por dia e R$XXXX toda semana, que é o que você merece. E da mesma forma, a cada dia que você está sem emprego são R$XXX a menos, e cada semana que você passa sem direcionamento, acompanhamento e feedbacks que vão mudar o jogo custa R$XXXX, esse valor sai do seu bolso”.<br><br>
            “Eu sei que dói fazer essa reflexão, mas esse cálculo também serve justamente para entender o que você vai ganhar investindo na sua carreira, e nós estamos vendo que são R$XXXX por ano. Então a questão aqui é: se você chegar na semana que vem sem entrevista, sem ser chamado(a), e sem uma perspectiva de ser contratado(a) você está confortável em perder mais R$XXXX?”<br><br>
            - Esperar a pessoa responder NÃO.<br><br>
            “Então é por isso que a CRH faz sentido para você. Nós vamos te ajudar a recuperar o tempo e o dinheiro que você já perdeu tentando sozinho(a) sem saber o que fazer para se recolocar”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 75 (ACOMPANHAMENTO COM RIC)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E aí, nós temos uma tabela que mostra quanto você teria que investir para ter 1 ano desse nível de acompanhamento só com o Ric. Então são 24 momentos individuais, 2 cursos (de emprego e aumento), os encontros diários e as mais de 10 ferramentas. Hoje, a mentoria vale R$51.000, se for considerar o período de 1 ano. Só que é um valor se fosse um acompanhamento só com o Ric, e nós não fazemos isso porque é impossível ele dar conta”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 76 (EQUIPE DE MENTORES)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Pensando nisso, nós conseguimos reduzir esse valor de R$51.000 com toda a nossa equipe de mentores que temos aqui por trás das entregas. Assim a gente ajuda mais pessoas com um processo mais fluido e um investimento mais acessível”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 77**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E hoje para você ter esse nível de acompanhamento aqui na CRH, nós colocamos uma taxa de pré-matrícula de R$500 para garantir a sua vaga, e no seu momento de direcionamento estratégico nós vamos dizer se você foi aprovado(a) ou não para continuar na CRH com base nesses 3 pilares e, se for, vamos combinar como você vai levantar o restante do valor da mentoria. Caso, você não seja aprovado(a), pode pedir reembolso dos R$500”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 78**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “E durante os próximos 3 dias, só com a entrada de R$500 você já vai ter acesso a 10 aulas que separamos com o passo a passo para conseguir emprego rápido, sua participação nas Dailys das 9h e 11h, mais de 10 ferramentas do APP e o seu direcionamento estratégico no momento da aprovação. Tudo o que é necessário para já começar a ver resultado. Me diz aqui, R$500 é um valor acessível para você hoje?”<br><br>
            - Esperar a pessoa responder SIM (fazer uma pausa em silêncio)
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 79**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Maravilha. Agora falando sobre o pós, o investimento fica em parcelas de 955 no recorrente, que não pega o limite total do seu cartão, é só o valor da parcela. Ou então se você preferir fazer um pagamento único (que também pode ser no cartão de crédito) fica em 9500, e isso dá uma diferença de +ou- R$2.000. Mas isso você só precisa decidir depois de conhecer melhor o método e ver como a mentoria é por dentro”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 80**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            “Agora são só os R$500. E aí?”
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### QUEBRA DE OBJEÇÃO")
        
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Lead:</b> “Preciso pensar por conta do valor das parcelas de 955 depois, eu não tenho isso tudo agora, preciso da minha reserva para sobreviver, não estava esperando que fosse tudo isso".<br><br>
            <b>Closer:</b> “O que você precisa pensar? Agora a única coisa que você precisa são os R$500, que você me falou que tem. Então você pode dar os R$500 da entrada, começar a assistir às aulas, participar das Dailys, já ter o seu momento de direcionamento estratégico, conhecer a CRH por dentro e só depois de uma semana a nossa equipe vai entrar em contato com você para ver como vai ser o restante do pagamento. E é melhor ficar pelo menos uma semana sendo acompanhado(a) ou passar mais esses dias tentando sozinho(a) sem resultado?”<br><br>
            <b>Lead:</b> "É, mas eu estou preocupado com o pós, não tenho dinheiro para pagar as parcelas".<br><br>
            <b>Closer:</b> “Entendo. Mas olha, a gente viu lá na calculadora o quanto você vai ganhar por dia com o seu novo emprego, né? E por dia, você vai ganhar R$XXX (valor da calculadora)”. Então será que não vale a pena você fazer esse investimento aqui e depois com o seu trabalho você vai pagando o valor das parcelas? Sei que agora você está preocupado(a) por estar desempregado(a), mas quando você se recolocar, essas parcelas aqui dá para pagar”.<br><br>
            <b>Lead:</b> "Eu entendo, mas preciso pensar mesmo. Não gosto de fechar nada por impulso porque não sei se vou conseguir cumprir com isso depois, e pode demorar mais de 51 dias para eu conseguir emprego. E aí, como vou pagar as parcelas depois?”<br><br>
            <b>Closer:</b> Olha, eu entendo tudo isso, mas a gente viu juntos aqui que você realmente precisa ser acompanhado(a), porque ficar tentando sozinho(a) não está dando resultado, né? Então eu estou aqui disponível para poder te ajudar a pensar e achar uma solução, pode ser?”<br><br>
            <b>Lead:</b> “Não sei, eu realmente não tenho esse dinheiro agora”.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 81 (Quebra de Objeção)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Closer:</b> “Você me disse que é uma pessoa dedicada e que é uma prioridade conseguir esse novo emprego, não foi? A gente tem vários casos de pessoas que conseguiram se recolocar em menos de 30 dias, que entraram de cabeça na CRH. Será que com 15 dias sendo direcionado e acompanhado de perto, o cenário já não vai melhorar para você ter mais entrevistas e conseguir pagar as parcelas com seu futuro salário?”<br><br>
            <b>Lead:</b> "Mas e se eu investir esse valor e não conseguir? Como faço para pagar as parcelas?"<br><br>
            <b>Closer:</b> “E se você continuar no mesmo cenário e não conseguir entrevista nesses próximos 30 dias, quanto dinheiro você vai perder? São R$XXXX (Tempo é dinheiro), certo? A gente viu que a cada semana que passa você está perdendo R$XXXX. Você me falou que tem como prioridade se recolocar e que você é uma pessoa de palavra, conseguir emprego não é uma prioridade para você então?”<br><br>
            <b>Lead:</b> "Sim, é uma prioridade. Mas também tenho que pensar em como eu vou pagar o restante depois se eu não conseguir um emprego rápido".
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**SLIDE 82 (Quebra de Objeção)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Closer:</b> “Mas não precisa pensar agora. Você falou que os R$500 não são o problema. Então você pode dar a entrada de 500, participa da mentoria e nesse período de uma semana a gente até pode te ajudar a pensar na forma de pagamento. E você vai ter uma garantia nesse 1 ano para ter o seu dinheiro de volta caso o método não funcione”.<br><br>
            “Nós vamos te acompanhar todos os dias, e o seu trabalho vai ser buscar trabalho. Tem gente que paga 20.000, 40.000 em um MBA, uma pós-graduação para ter só um título e ficar sem feedback, acompanhamento, direcionamento, sem essas ferramentas. Então eu te garanto que a CRH é um investimento para a sua vida, não só para agora”.<br><br>
            <b>Lead:</b> “Eu acredito muito nisso, mas realmente não dá para eu investir esse valor”.<br><br>
            <b>Closer:</b> “Então você prefere ficar mais uma semana tentando sozinho(a) perdendo R$XXX por dia sem receber feedback, acompanhamento e direcionamento, ou prefere dar agora uma entrada de R$500, ter a nossa ajuda e se não der certo ter seu dinheiro de volta?”<br><br>
            <b>Lead:</b> “Não é isso, a questão é que eu não tenho o valor das parcelas agora e vou ficar inadimplente se não conseguir emprego logo”.<br><br>
            <b>Closer:</b> “Mas nós falamos que você vai ganhar R$XXXX por ano, certo? Será que não é vantagem você investir R$500 agora para ganhar esses R$XXXX no ano, e se o dinheiro que você investir não retornar, a gente devolve tudo? Você tem a opção de ficar um ano sendo acompanhado(a) por nós, ou ficar mais tempo sem conseguir entrevista, sem conseguir ganhar dinheiro… e você já perdeu R$XXXX nesse tempo que está buscando”.<br><br>
            <b>Lead:</b> “Se eu tivesse dinheiro, faria muito sentido. Mas agora realmente não tenho como fazer esse investimento, não dá para eu comprometer outras coisas essenciais”.<br><br>
            <b>Closer:</b> E será que com o nosso acompanhamento além de conseguir emprego você não consegue aumentar a sua proposta salarial em R$955? O José, que eu te mostrei antes, começou a ganhar R$1.200 a mais todos os meses, não faz sentido?”<br><br>
            <b>Lead:</b> "Mas mesmo assim, eu não sei como vou pagar os R$955 na semana que vem".<br><br>
            <b>Closer:</b> Mas você entende que se na semana que vem você não tiver nenhuma entrevista são menos R$XXXX no seu bolso? Será que você não tem R$1.500 essa semana para investir na sua carreira? Então você está confortável em perder esses R$XXXX, né?”
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Quebra de objeção (Cônjuge)**")
        st.markdown("""
        <div class="playbook-box">
            <div class="playbook-script">
            <b>Lead:</b> "Eu não consigo fazer esse investimento sem falar com meu marido/minha esposa".<br><br>
            <b>Closer:</b> “Mas você não me falou que seu marido/sua esposa te apoiava? “<br><br>
            <b>Lead:</b> "Sim, apoia. Mas não posso tomar essa decisão sem discutirmos antes".<br><br>
            <b>Closer:</b> “Certo. Mas ele(a) não entende a sua dor. Será que se o seu marido/a sua esposa olhar o seu diagnóstico que fizemos, ele(a) entende como é ficar navegando horas sem resultados? Será que ele entende o que é ter chuva de negativas na gupy todos os dias?”<br><br>
            <b>Lead:</b> "Não entende".<br><br>
            <b>Closer:</b> “Então é óbvio que o seu marido/a sua esposa vai olhar esse valor e falar: "Tá caro". Porque ele(a) não entende a sua dor da forma como a gente entende. Nós vamos te acompanhar todos os dias, e o seu trabalho vai ser buscar trabalho. Tem gente que paga 20.000, 40.000 em um MBA, uma pós-graduação para ter só um título e ficar sem feedback, acompanhamento e direcionamento. Então eu garanto que é um investimento para a sua vida, não só para agora. E você falou que R$500 vocês têm… às vezes o seu marido/a sua esposa vai até preferir que você entre, conheça a mentoria por dentro, e você vai ganhando mais confiança para poder argumentar com ele(a) sobre o restante”.
            </div>
        </div>
        """, unsafe_allow_html=True)

# =================================----------------=============
# ABA 2: AUDITORIAS & INDICADORES
# =================================----------------=============
with tab2:
    st.header("📊 Painel Geral de Auditorias 1A1")
    
    historico = st.session_state["historico_analises"]
    total_periodo = len(st.session_state["eventos_carregados"])
    total_analisadas = len(historico)

    col_status = obter_coluna_case_insensitive(st.session_state["dados_planilha"], "Status")
    col_closer = obter_coluna_case_insensitive(st.session_state["dados_planilha"], "Closer")
    col_objecao = obter_coluna_case_insensitive(st.session_state["dados_planilha"], "Objeção")
    col_cliente = obter_coluna_case_insensitive(st.session_state["dados_planilha"], "Cliente")

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
    if not df_master.empty and col_closer and col_status:
        for c in closers_alvo:
            sub_df = df_master[df_master[col_closer].astype(str).str.strip().str.lower() == c.lower()]
            total_sessoes_c = len(sub_df)
            
            # Tratamento blindado contra nulos ou não-strings
            status_series = sub_df[col_status] if not sub_df.empty else pd.Series(dtype=object)
            g_ato = sum(1 for s in status_series if "ato" in str(s or "").lower())
            g_fup = sum(1 for s in status_series if "fup" in str(s or "").lower() or "follow" in str(s or "").lower())
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
        
        if not df_master.empty and col_cliente:
            lead_norm = remover_acentos(nome_lead_limpo)
            melhor_match = None
            maior_score = 0.0

            for idx, row in df_master.iterrows():
                cliente_planilha = str(row.get(col_cliente, ""))
                cliente_norm = remover_acentos(cliente_planilha)
                score = similaridade(lead_norm, cliente_norm)
                primeiro_nome_agenda = lead_norm.split()[0] if lead_norm else ""
                if primeiro_nome_agenda and (primeiro_nome_agenda in cliente_norm or cliente_norm.startswith(primeiro_nome_agenda[:3])):
                    score += 0.4

                if score > maior_score and score > 0.35:
                    maior_score = score
                    melhor_match = row

            if melhor_match is not None:
                status_master_auto = str(melhor_match.get(col_status, "Perdido")).strip() if col_status else "Perdido"
                closer_master_auto = str(melhor_match.get(col_closer, "Não identificado")).strip() if col_closer else "Não identificado"
                objecao_master_auto = str(melhor_match.get(col_objecao, "Sem objeção registrada")).strip() if col_objecao else "Sem objeção registrada"

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
                        
                        prompt_sistema = f"""Você é o Auditor Oficial de Vendas da Ricarreira (Metodologia FHT - Closer's Central).
Sua missão é auditar com rigor cirúrgico a chamada 1A1 gravada/transcrita com base no ROTEIRO OFICIAL DE DIAGNÓSTICO DE CARREIRA da empresa, estruturado em 3 blocos.

CRITÉRIOS DE AUDITORIA BASEADOS NO ROTEIRO OFICIAL:

📍 BLOCO 1: ACOLHIMENTO & RAIO-X
1. Quebra de Gelo, Acolhimento & Expectativa:
   - Fez perguntas de conexão e acolhimento sobre a última empresa/setor vista no LinkedIn?
   - Investigou o momento atual e a expectativa ("O que está buscando para os próximos passos da sua carreira?")?
2. Acordo Inicial do Raio-X:
   - Alinhou o objetivo de entender as maiores dificuldades e explicou que as perguntas serão respondidas com notas de 0 a 10?
   - Estabeleceu o acordo de NÃO justificar a nota por enquanto (para garantir fluidez e mostrar no gráfico depois)?
   - Pediu compromisso: "Preciso que você seja BRUTALMENTE SINCERO(A). Posso confiar na sua palavra?"?
3. Devolutiva por Pilares e Faixa de Nota:
   - Apresentou o gráfico e fez a devolutiva adequada à nota dada em cada pilar:
     * MENTALIDADE: Se 8-10, validou que não é acomodado(a) e família é prioridade; se 0-7, apontou o abalo na confiança pelas rejeições.
     * AUMENTO SALARIAL: Se 6-10, reforçou boa articulação, mas destacou que de nada adianta sem a vaga; se 0-5, confrontou a postura puramente técnica/operacional.
     * CURRÍCULO: Se 0-5, destacou currículo genérico focado em tarefas e não em resultados (bloqueado em ATS e recrutadores); se 6-10, validou métricas.
     * LINKEDIN: Se 0-5, frisou que está invisível para vagas ocultas e no LinkedIn Recruiter; se 6-10, validou atração orgânica.
     * ENTREVISTAS: Se 0-5, apontou o efeito dominó (pouco treino, nervosismo da "única chance", falta de feedbacks e submissão a salários baixos); se 6-10, validou condução.
4. Transição para o Pitch:
   - Concluiu com clareza: o problema NÃO é falta de capacidade técnica nem vontade, mas sim falta de método estratégico de comunicação para gerar fluxo de entrevistas nos próximos 51 dias?
   - Fez as perguntas de transição: "Faz sentido para você? Você quer mudar esse cenário?"?

📍 BLOCO 2: APRESENTAÇÃO DO PROGRAMA E SLIDES
1. Slide 1 (História do Herói Relutante):
   - Contou por que o Ricardo relutou em criar o acompanhamento ("Acompanhar é diferente de só ensinar", "Ouvir que precisavam se recolocar urgente") e apresentou como acelerador de resultados?
   - Pediu permissão para apresentar o programa?
2. Slide 2 (Definição da CRH):
   - Definiu a CRH como programa de aceleração de 12 meses com direcionamento, acompanhamento e feedbacks personalizados para empregos em até 51 dias, cargos desejados/liderança e aumento salarial?
3. Slide 3 (Depoimentos):
   - Apresentou histórias de alunos e perguntou qual depoimento mais marcou?
4. Pilares de Entregáveis (Slides 43 a 60):
   - DIREIONAMENTO: Sessão de Direcionamento Estratégico individual (virar a chave de ter sempre uma tempestade de negativas), 2 cursos online (emprego e aumento), sessão individual de validação de CV/LinkedIn e simulação de entrevista com 2 mentores?
   - ACOMPANHAMENTO: Gestão de vagas no app, suporte individual no WhatsApp e plantão de 48h de negociação salarial (cases Gabi, Claudia, Jessica, José)?
   - FERRAMENTAS: Buscador de vagas ATS no APP Ricarreira, acervo de currículos campeões de 1 página e biblioteca de mensagens?
   - COMUNIDADE: Dailies diárias às 9h (arrumar a casa) e às 11h com o Ric (empregabilidade/atacar)?
5. Bônus de Aumento Salarial (Slides 64 a 68):
   - Acompanhamento nos primeiros 30 dias na nova empresa, mapeamento de aliados estratégicos, construção de CASEs mensais de lucro e Shark Tank do Aumento Salarial com 2 mentores?
6. Slide 71 (Qualificação & Checagem):
   - Perguntou se faz sentido, pediu a nota de 0 a 10 de quanto o programa resolve a dor e tratou dúvidas/objeções antes de abrir o investimento?
   - Se houve menção precoce a dinheiro, fez o alinhamento de sinceridade brutal sobre as cadeiras limitadas?

📍 BLOCO 3: OFERTA & QUEBRA DE OBJEÇÕES
1. Slide 73 (Confronto de Formações):
   - Perguntou quanto o lead investiu em graduação/pós/MBA e confrontou se teve acompanhamento próximo, feedback individual ou se ensinaram a buscar emprego/aumento?
2. Slide 74 (Calculadora Tempo é Dinheiro):
   - Desdobrou a pretensão salarial em valor anual, diário e perda semanal por estar sem método? Confrontou: "Está confortável em perder mais R$XXXX até a semana que vem?"?
3. Ancoragem e Oferta (Slides 75 a 80):
   - Ancorou o valor de R$ 51.000 se fosse só com o Ric e explicou a redução com a equipe de mentores?
   - Apresentou a taxa de pré-matrícula de R$ 500,00 para garantir a vaga e explicou que a aprovação para continuar na mentoria ocorre no direcionamento estratégico; SE APROVADO(A), combina em até 3 dias como levantar o restante (e caso não seja aprovado, há reembolso dos R$ 500)?
   - Reforçou que durante os próximos 3 dias, a entrada de R$ 500 dá acesso a 10 aulas, Dailies das 9h e 11h, +10 ferramentas e direcionamento estratégico?
   - Verificou: "R$ 500 é um valor acessível para você hoje?"?
   - Explicou o pós: 12 parcelas de 955 no recorrente (sem tomar o limite total) ou 9.500 à vista no cartão?
4. Quebra de Objeções (Slides 81 e 82):
   - Se o lead travou nas parcelas do pós / reserva / medo de demorar mais de 51 dias: usou o ganho diário na volta ao mercado, relembrou o custo da inércia (Tempo é Dinheiro), o compromisso inicial, o acompanhamento diário e a garantia de 1 ano?
   - Se o lead mencionou cônjuge: aplicou o reframe de que o cônjuge não vive a dor das negativas na Gupy diárias, achará "caro" por desconhecer a dor e que a entrada de R$ 500 traz segurança para avaliar por dentro? (NÃO cobre cônjuge se o lead não mencionou).

DADOS DO CRM / BASE MASTER:
- Status na Planilha: {status_master_auto}
- Closer Responsável: {closer_master_auto}
- Objeção Registrada: {objecao_master_auto}

FORMATO OBRIGATÓRIO DE RESPOSTA:
Comece exatamente com o cabeçalho de status e nota:
### {"🟢 STATUS: LEAD CONVERTIDO (" + status_master_auto.upper() + ")" if is_venda_confirmada else "🔴 STATUS: NÃO CONVERTIDO"}

**Resumo Executivo & Nota do Closer: [X.X / 10]**
(Nota de 8.0 a 10.0 se Convertido/Ganho; Nota de 0.0 a 7.9 se Perdido/Não Convertido).

---
#### 1. Aderência ao Roteiro Oficial
- **Bloco 1 (Acolhimento & Raio-X):** [Análise objetiva dos acertos e desvios no acolhimento, no acordo de 0 a 10 e nas devoluções de cada pilar]
- **Bloco 2 (Apresentação do Programa & Slides):** [Análise da narrativa do herói relutante, dos 4 pilares e do bônus de aumento]
- **Bloco 3 (Oferta, Ancoragens & Objeções):** [Análise do confronto de formações, calculadora Tempo é Dinheiro, oferta de R$ 500 com alinhamento de 3 dias pós-aprovação e reframes aplicados]

#### 2. 🎯 Pontos Fortes da Condução
- [Pontos positivos onde o closer seguiu a copy oficial com maestria]

#### 3. 🚨 Pontos de Melhoria Críticos
- [Gargalos, falas omitidas, falta de firmeza ou pulo de etapas do roteiro oficial]

#### 4. 💡 Plano de Ação para o Próximo Treinamento
- [Direcionamento prático e cirúrgico para o closer ajustar no próximo atendimento]
"""

                        if is_venda_confirmada:
                            prompt_sistema += f"\n- LEAD CONVERTIDO ({status_master_auto}). NOTA FINAL OBRIGATÓRIA ENTRE 8.0 E 10.0."
                        else:
                            prompt_sistema += f"\n- LEAD NÃO CONVERTIDO ({status_master_auto}). NOTA FINAL OBRIGATÓRIA ENTRE 0.0 E 7.9."

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": prompt_sistema},
                                {"role": "user", "content": f"Lead: {nome_lead_limpo}\nTranscrição/Dados da Sessão:\n{transcricao_texto}"}
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
    
    col_closer = obter_coluna_case_insensitive(df_master, "Closer")
    col_status = obter_coluna_case_insensitive(df_master, "Status")
    col_objecao = obter_coluna_case_insensitive(df_master, "Objeção")

    if not df_master.empty and col_closer:
        df_closer_filtrado = df_master[df_master[col_closer].astype(str).str.strip().str.lower() == closer_selecionado.lower()]
        
        col_c1, col_c2, col_c3 = st.columns(3)
        tot_c = len(df_closer_filtrado)
        
        status_series = df_closer_filtrado[col_status] if col_status and not df_closer_filtrado.empty else pd.Series(dtype=object)
        ganhos_c = sum(1 for s in status_series if "ganho" in str(s or "").lower())
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
            if col_objecao and not df_closer_filtrado.empty:
                df_obj = df_closer_filtrado[df_closer_filtrado[col_objecao].astype(str).str.strip() != ""]
                df_obj_counts = df_obj[col_objecao].value_counts().reset_index()
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
