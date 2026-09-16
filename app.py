import streamlit as st
import datetime
import json
import re
import unicodedata
import pandas as pd
from difflib import SequenceMatcher
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")

# CSS para garantir que os cards e textos fiquem 100% legíveis sem cortes
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
    </style>
""", unsafe_allow_html=True)

def remover_acentos(texto):
    if not isinstance(texto, str):
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower().strip()

def similaridade(a, b):
    return SequenceMatcher(None, remover_acentos(a), remover_acentos(b)).ratio()

if "historico_analises" not in st.session_state:
    st.session_state["historico_analises"] = []

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "")
ID_PLANILHA_REAL = "1LsWvNf3XBmmNnICtP2BLKl3-NN7yAIF2WV0pgqw3onU"

# Sidebar
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
            creds_dict = dict(st.secrets["google_credentials"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = str(creds_dict["private_key"]).replace("\\n", "\n")
            
            SCOPES = [
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/spreadsheets.readonly'
            ]
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            
            # Agenda
            service_cal = build('calendar', 'v3', credentials=credentials)
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
            
            st.session_state["eventos_carregados"] = [
                e for e in events if "diagnóstico gratuito de carreira" in e.get('summary', '').lower()
            ]

            # Planilha Master
            try:
                service_sheets = build('sheets', 'v4', credentials=credentials)
                sheet_result = service_sheets.spreadsheets().values().get(
                    spreadsheetId=ID_PLANILHA_REAL, range="Base_Master!A1:AA1000"
                ).execute()
                values = sheet_result.get('values', [])
                if values:
                    df = pd.DataFrame(values[1:], columns=values[0])
                    st.session_state["dados_planilha"] = df
            except Exception as e_sheet:
                st.sidebar.warning(f"Agenda OK, erro planilha: {str(e_sheet)}")

            st.sidebar.success(f"Encontrados {len(st.session_state['eventos_carregados'])} Diagnósticos!")
        else:
            st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets.")
    except Exception as e:
        st.sidebar.error(f"Erro ao sincronizar: {str(e)}")

# -------------------------------------------------------------
# 1. CARDS DE DESEMPENHO E CONVERSÃO
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# 2. AUDITORIA DA REUNIÃO (COM NOVO PROMPT OFICIAL)
# -------------------------------------------------------------
st.subheader("📋 Auditar Reunião 1A1")

if st.session_state["eventos_carregados"]:
    events = st.session_state["eventos_carregados"]
    df_master = st.session_state["dados_planilha"]
    
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
    
    # Busca por Similaridade
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
            with st.spinner("🤖 Analisando reunião com base no Roteiro Oficial Ricarreira (Blocos 1, 2 e 3)..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    
                    # PROMPT INTEGRADO COM OS ROTEIROS OFICIAIS DOS 3 BLOCOS
                    prompt_sistema = f"""Você é o Auditor Sênior de Vendas da Ricarreira (programa CRH, fundado por Ricardo Batista).
Sua missão é auditar meticulosamente a chamada 1A1 com base nos ROTEIROS OFICIAIS da empresa, divididos em 3 blocos bem definidos de 20 minutos.

AVALIAÇÃO ESTRUTURAL POR BLOCOS:

📍 BLOCO 1: DIAGNÓSTICO & RAIO-X (Minuto 0 ao 20)
- Quebra-gelo & Acordo Inicial: Fez pergunta de conexão ("Como conheceu a Ricarreira?") e alinhou OBRIGATORIAMENTE para o lead NÃO justificar as notas de 0 a 10 (mantendo a reunião fluida e sem esticar demais)?
- Raio-X dos 5 Pilares: Passou objetivamente por Currículo, LinkedIn, Entrevistas (investigando aprovações em Inteligência Artificial vs. RH Humano), Aumento Salarial e Mentalidade?
- Escavação de Objeções: No pilar de Mentalidade, perguntou o "porquê" das notas menores que 10 para cavar travas de tempo, família e dedicação em 51 dias?
- Leitura do Gráfico: Compartilhou a tela mostrando APENAS o gráfico e utilizou a narrativa padronizada conectando que Mentalidade e Desejo de Salário só geram resultado se Currículo, LinkedIn e Entrevistas estiverem destravados? Encerrou perguntando se o lead concorda e quer mudar o cenário com urgência?

📍 BLOCO 2: APRESENTAÇÃO DO PROGRAMA & SLIDES (Minuto 20 ao 40)
- História do Herói Relutante: Utilizou a copy oficial explicando por que o Ricardo relutou em criar um programa individual ("Acompanhar é diferente de só ensinar", "Ouvir que precisavam se recolocar urgente", "Criar um acelerador de resultados")?
- Escassez de Cadeiras: Avisou no início da apresentação que a Ricarreira abre apenas vagas/cadeiras limitadas por mês para manter a qualidade do grupo?
- Apresentação de Pilares vs. Entregáveis: Apresentou os 4 pilares antes de listar entregáveis? (Direcionamento = pré-ação/marca pessoal; Acompanhamento = pós-ação/trava de entrevistas; Facilidades = App Ricarreira, filtro ATS, Controle de Vagas e Comunidade do Bem; Aumento Salarial = crescimento pós-recolocação).
- Perguntas de Checagem: Fez as pausas de alinhamento ao longo dos slides ("Faz sentido?", "De 0 a 10 quanto tudo o que apresentei vai te ajudar na sua maior dificuldade hoje?")?

📍 BLOCO 3: PITCH, ANCORAGEM & QUEBRA DE OBJEÇÕES (Minuto 40 ao 60)
- Merecimento da Cadeira: Perguntou "Por que uma dessas vagas deveria ser sua e não de outras pessoas interessadas?" para fazer o lead se vender para o programa?
- Confronto de Formações (Slide 70): Ancorou confrontando os milhares de reais gastos em formações/cursos técnicos ao longo dos anos vs. zero investimento em carreira e postura de protagonista?
- Calculadora Tempo é Dinheiro (Slide 71): Calculou a dor semanal e diária ("A cada semana sem direcionamento você perde R$ XXXX/semana e R$ XXX/dia deixando de ganhar sua pretensão")?
- Foco Exclusivo na Entrada (R$ 500,00): Conduziu a oferta focando no valor acessível de R$ 500,00 para garantir a vaga agora, deixando o restante para alinhar em 1 semana?
- Contorno Técnico de Objeções Específicas:
  * "Preocupado com o pós/parcelas": Usou a lógica de retorno diário do novo emprego e o investimento na vida?
  * "Preciso de um tempo para pensar": Lembrou do compromisso de ser uma pessoa dedicada e de palavra, mostrando o dinheiro perdido em mais 15 dias parado?
  * "Preciso falar com cônjuge": Usou o reframe de que o parceiro(a) não entende a dor da busca (negativas na Gupy) e sugeriu dar os R$ 500 para ter mais confiança ao conversar?
  * "E se não conseguir o emprego": Apresentou a Garantia Condicional de 1 Ano (colocando o risco nas costas da Ricarreira)?

STATUS REGISTRADO NA PLANILHA MASTER:
- Status na Planilha: {status_master_auto}
- Closer Responsável: {closer_master_auto}
- Objeção no CRM: {objecao_master_auto}

REGRAS RÍGIDAS DE NOTA & RESPOSTA:
"""

                    if is_venda_confirmada:
                        prompt_sistema += f"""
- Esta sessão foi uma VENDA CONVERTIDA ({status_master_auto}).
- A NOTA FINAL OBRIGATORIAMENTE DEVE SER ENTRE 8.0 E 10.0.
- Se for 'Ganho (FUP)', elogie a execução do roteiro FHT e o acompanhamento que sustentou o fechamento pós-sessão.

ESTRUTURA DE RESPOSTA OBRIGATÓRIA (Markdown):
### 🟢 STATUS: LEAD CONVERTIDO ({status_master_auto.upper()})

**Resumo Executivo & Nota do Closer: [X.X / 10]**
*(Avaliação geral da performance conectando o fechamento com o cumprimento dos roteiros oficiais dos 3 blocos)*

---
- **🎯 Pontos Fortes da Sessão** *(Ex: Acordo inicial de objetividade, copy fluida do Herói Relutante, ancoragem Tempo é Dinheiro, foco na entrada de R$ 500)*
- **🚨 Pontos de Melhoria Críticos** *(Detalhes sutis onde o closer pode elevar ainda mais o padrão de execução)*
- **💡 Plano de Ação para o Próximo Treinamento** *(Orientações de postura e fixação de roteiro)*
"""
                    else:
                        prompt_sistema += f"""
- Esta sessão está registrada como NÃO CONVERTIDA (Perdido).
- A NOTA FINAL DEVE SER ENTRE 0.0 E 7.9, apontando onde o closer desviou do roteiro dos 3 blocos ou falhou no contorno da objeção '{objecao_master_auto}'.

ESTRUTURA DE RESPOSTA OBRIGATÓRIA (Markdown):
### 🔴 STATUS: NÃO CONVERTIDO

**Resumo Executivo & Nota do Closer: [X.X / 10]**
*(Diagnóstico cirúrgico de onde a venda foi perdida e quais roteiros foram ignorados)*

---
- **🎯 Pontos Fortes da Sessão** *(Empatia, acolhimento ou bom preenchimento inicial do Raio-X)*
- **🚨 Pontos de Melhoria Críticos** *(Onde falhou: justificativas no Raio-X, ausência do Herói Relutante, falta de confronto nas formações, cálculo do Tempo é Dinheiro ou vacilo no contorno da objeção de dinheiro/cônjuge)*
- **💡 Plano de Ação para o Próximo Treinamento** *(Treinamento prático e simulação exata para contornar a objeção '{objecao_master_auto}')*
"""
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": f"Lead: {nome_lead_limpo}\nTranscrição/Dados:\n{transcricao_texto}"}
                        ],
                        temperature=0.3
                    )
                    
                    analise_ia = response.choices[0].message.content
                    is_convertido_final = is_venda_confirmada
                    
                    match_nota = re.search(r"(\d+[\.,]?\d*)\s*/\s*10", analise_ia)
                    nota_extraida = float(match_nota.group(1).replace(",", ".")) if match_nota else (9.0 if is_convertido_final else 6.0)

                    st.session_state["historico_analises"].append({
                        "Data": evento_obj.get('start', {}).get('dateTime', '')[:10],
                        "Cliente": nome_lead_limpo,
                        "Closer": closer_master_auto,
                        "status_venda": status_master_auto,
                        "Objeção": objecao_master_auto if not is_venda_confirmada else "Nenhuma / Fechado",
                        "convertido": is_convertido_final,
                        "nota": nota_extraida,
                        "feedback_completo": analise_ia
                    })

                    st.rerun()

                except Exception as err:
                    st.error(f"Erro na análise: {str(err)}")

else:
    st.info("👈 Selecione o período na barra lateral e clique em 'Sincronizar Agenda & Tabela Master'.")

st.markdown("---")

# -------------------------------------------------------------
# 3. TABELA DE AUDITORIAS REALIZADAS
# -------------------------------------------------------------
if historico:
    st.subheader("📑 Tabela de Auditorias Realizadas")
    df_hist = pd.DataFrame(historico)
    
    df_exibicao = df_hist[["Data", "Cliente", "Closer", "status_venda", "Objeção", "nota"]].copy()
    df_exibicao.columns = ["Data da Sessão", "Cliente", "Closer", "Status da Venda", "Objeção Registrada", "Nota FHT"]
    
    st.dataframe(df_exibicao, use_container_width=True)

    with st.expander("🔍 Ver Último Feedback Completo Gerado pela IA", expanded=True):
        st.markdown(historico[-1]["feedback_completo"])
