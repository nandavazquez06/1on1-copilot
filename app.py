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
        background-color: #f1f5f9;
        border-left: 4px solid #2563eb;
        padding: 14px;
        border-radius: 4px;
        margin-bottom: 12px;
    }
    .playbook-script {
        font-style: italic;
        color: #1e293b;
        background-color: #ffffff;
        padding: 10px;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
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

# Sidebar - Configurações Gerais
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
    st.header("📖 Roteiro de Bolso - Sessão 1A1 High Ticket")
    st.caption("Consulte as copys exatas, frases de alinhamento e reframes oficiais durante a chamada.")
    
    p_tab1, p_tab2, p_tab3 = st.tabs(["📍 Bloco 1: Diagnóstico & Raio-X", "📍 Bloco 2: Apresentação do Programa", "📍 Bloco 3: Fechamento & Objeções"])
    
    with p_tab1:
        st.subheader("1. Acolhimento & Quebra-Gelo")
        st.markdown("""
        * **Pergunta Conexão:** *"Como você conheceu o Ricarreira?"* ou *"Já está aplicando o PRH?"*
        * **Expectativa:** *"O que você espera deste momento? O que está buscando?"*
        """)
        
        st.subheader("2. Acordo de Objetividade (Alinhamento Inicial)")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Eu vou te fazer algumas perguntas. Não precisa justificar o motivo da nota, só se eu te perguntar. Tudo bem? Mas um combinado: eu preciso que você seja BRUTALMENTE SINCERO. Posso confiar na sua palavra?"</div></div>', unsafe_allow_html=True)
        st.info("💡 *Dica:* Você tem liberdade para aprofundar se identificar uma dor importante, mas o alinhamento inicial evita que a reunião estoure os 20 minutos.")

        st.subheader("3. Estrutura dos 5 Pilares do Raio-X")
        st.markdown("""
        1. **Currículo:** Métrica de convites por 10 CVs, aprovação em Gupy, ATS e indicação.
        2. **LinkedIn:** Convites na semana, visualizações de perfil e abordagens.
        3. **Entrevistas:** Aprovações por Inteligência Artificial (IA) vs. RH Humano, entrevistas técnicas/gestor e clareza de pretensão salarial.
        4. **Aumento Salarial:** Plano claro para 6 meses, cases de lucro em 90 dias e recusa de tarefas operacionais.
        5. **Mentalidade (Escavação de Objeções):** Prioridade de novo emprego, dedicação em 51 dias, família e compromisso de palavra.
        """)
        
        st.subheader("4. Leitura do Gráfico de Radar")
        st.markdown("""
        * Compartilhe a tela exibindo **APENAS o gráfico**.
        * **Narrativa Padrão:** *"O gráfico em azul é o ideal de 10 em tudo. Em vermelho é a média DAS NOTAS QUE VOCÊ DEU. Ele mostra que você tem Mentalidade e Desejo Salarial, mas nada disso gera resultado prático enquanto Currículo, LinkedIn e Entrevistas estiverem travados."*
        * **Pergunta de Transição:** *"Faz sentido para você? Você quer mudar esse cenário urgentemente?"*
        """)

    with p_tab2:
        st.subheader("1. História do Herói Relutante (Copy Oficial)")
        st.markdown("""
        <div class="playbook-box">
        <div class="playbook-script">
        "O Ricardo por muito tempo relutou em criar um programa de acompanhamento individual personalizado, porque acreditava que isso iria tomar muito tempo dele, e nós já temos um método que ajuda muitas pessoas. Mas o que preocupava ele era ter um monte de gente aplicando o método sem ter o acompanhamento necessário para aumentar a taxa de aprovação.<br><br>
        Então o Ric entendeu que acompanhar é diferente de só ensinar. Ao ouvir das pessoas que elas precisavam se recolocar urgente, ele pensou: 'E se eu criasse um programa para realmente pegar a pessoa pela mão e ajudar a fazer o que precisa ser feito?'<br><br>
        Como ele mesmo está em programas que aceleram resultados, ele criou esse Acelerador. Hoje nós só abrimos X cadeiras por mês para pessoas que selecionamos e achamos que o perfil faz sentido. Posso te mostrar como funciona?"
        </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("2. Os 4 Pilares da Mentoria CRH")
        st.markdown("""
        * **Direcionamento (Pré-ação):** Plano de ação, ajuste estratégico de CV, LinkedIn e marca pessoal.
        * **Acompanhamento (Pós-ação):** Análise de travas em entrevistas, simulados e negociação salarial.
        * **Facilidades:** App Ricarreira, filtro ATS de vagas, Controle de Vagas e Comunidade do Bem no WhatsApp.
        * **Aumento Salarial:** Acompanhamento para crescimento na carreira pós-recolocação.
        """)

    with p_tab3:
        st.subheader("1. Ancoragens Obrigatórias do Pitch")
        st.markdown("""
        * **Confronto de Formações (Slide 70):** *"Quanto você já investiu em cursos técnicos/pós? E por que mesmo investindo R$ XXXX você continua sem o salário dos sonhos? Você nunca investiu na sua CARREIRA e Mentalidade."*
        * **Calculadora Tempo é Dinheiro (Slide 71):** *"Com pretensão de R$ XXXX/mês, por ano você busca R$ XXXX. Cada semana sem direcionamento são R$ XXXX deixados na mesa. Por dia você perde R$ XXX. Está confortável em perder isso por mais uma semana?"*
        * **Oferta na Entrada:** Foco absoluto nos **R$ 500,00 de sinal** para garantir a vaga agora (com saldo para 1 semana).
        """)

        st.subheader("2. Matadores de Objeções Específicas")
        
        st.markdown("**🔴 Objeção: 'Preciso falar com meu cônjuge / esposa / marido'**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Entendo, mas ele(a) não vive a sua dor diária de negativas na Gupy ou da busca sem retorno. É natural ele(a) achar caro se não entender a dor. Dando a entrada de R$ 500 hoje para garantir sua vaga, você entra no programa, ganha mais confiança e mostra o compromisso para depois conversarem com mais clareza."</div></div>', unsafe_allow_html=True)

        st.markdown("**🔴 Objeção: 'Preciso pensar por causa do valor das parcelas no pós'**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Agora você só precisa focar nos R$ 500 que você já tem. No novo emprego você vai ganhar R$ XXX por dia, o que paga as parcelas com folga. Ficar mais 15 dias pensando significa jogar R$ XXXX fora. Vale a pena continuar perdendo esse dinheiro?"</div></div>', unsafe_allow_html=True)

        st.markdown("**🔴 Objeção: 'E se eu investir e não conseguir o emprego?'**")
        st.markdown('<div class="playbook-box"><div class="playbook-script">"Nós temos a Garantia Condicional de 1 Ano. O risco está 100% nas nossas costas, não nas suas. Se você seguir o passo a passo e não tiver resultado, devolvemos todo o seu dinheiro."</div></div>', unsafe_allow_html=True)

# =================================----------------=============
# ABA 2: AUDITORIAS & INDICADORES (TELA ATUAL)
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
