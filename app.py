import streamlit as st
import datetime
import json
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks Ricarreira - Sessão 1A1", page_icon="📊", layout="wide")

# Inicialização do banco de dados temporário/histórico de análises
if "historico_analises" not in st.session_state:
    st.session_state["historico_analises"] = []

st.title("📊 Dashboard Executivo de Feedbacks - Sessão 1A1 (Ricarreira)")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

# Puxa configurações automáticas das Secrets
openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "")

# Sidebar - Configurações
st.sidebar.header("⚙️ Configurações do App")
if openai_key:
    st.sidebar.success("🔑 OpenAI API Key conectada!")
else:
    openai_key = st.sidebar.text_input("OpenAI API Key (Manual)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("📅 Agenda do Google Workspace")

email_equipe = st.sidebar.text_input("ID da Agenda da Equipe:", value=id_agenda_secrets)

transcricao_texto = ""
nome_lead = ""

if "eventos_carregados" not in st.session_state:
    st.session_state["eventos_carregados"] = []

if st.sidebar.button("🔄 Buscar Sessões na Agenda Real"):
    try:
        if "google_credentials" in st.secrets:
            creds_dict = dict(st.secrets["google_credentials"])
            
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
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
    
    transcricao_texto = descricao_evento if descricao_evento.strip() else f"Sessão: {nome_lead}\nData: {evento_obj.get('start', {}).get('dateTime', '')}\nParticipantes: {', '.join([p.get('email', '') for p in evento_obj.get('attendees', []) if isinstance(p, dict)])}"
    
    st.sidebar.write("---")
    st.sidebar.markdown(f"**Lead Selecionado:** {nome_lead}")

# -------------------------------------------------------------
# SEÇÃO DE KPIS COMERCIAIS NO TOPO
# -------------------------------------------------------------
historico = st.session_state["historico_analises"]
total_analisadas = len(historico)
total_convertidos = sum(1 for item in historico if item["convertido"])
taxa_conversao = (total_convertidos / total_analisadas * 100) if total_analisadas > 0 else 0.0
media_nota = (sum(item["nota"] for item in historico) / total_analisadas) if total_analisadas > 0 else 0.0

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📊 Total de Chamadas Analisadas", f"{total_analisadas}")
with col2:
    st.metric("🟢 Leads Convertidos (Taxa)", f"{total_convertidos} ({taxa_conversao:.1f}%)")
with col3:
    st.metric("⭐ Média de Performance (FHT)", f"{media_nota:.1f} / 10.0")

st.markdown("---")

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
                            {"role": "user", "content": f"Empresa: Ricarreira\nLead: {nome_lead}\n\nTranscrição/Dados da Sessão:\n{transcricao_texto}"}
                        ],
                        temperature=0.3
                    )
                    
                    analise_ia = response.choices[0].message.content
                    
                    # Extração automática da nota e status para os métricas do topo
                    is_convertido = "LEAD CONVERTIDO" in analise_ia
                    match_nota = re.search(r"(\d+[\.,]?\d*)\s*/\s*10", analise_ia)
                    nota_extraida = float(match_nota.group(1).replace(",", ".")) if match_nota else 7.0

                    # Salva no histórico e força atualização dos KPIs
                    st.session_state["historico_analises"].append({
                        "lead": nome_lead,
                        "convertido": is_convertido,
                        "nota": nota_extraida
                    })

                    st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()

                except Exception as err:
                    st.error(f"Erro ao chamar a OpenAI API: {str(err)}")

# Exibe o resultado da última análise realizada se houver
if historico:
    st.markdown("---")
    st.subheader(f"📊 Último Diagnóstico Gerado ({historico[-1]['lead']})")
    if historico[-1]["convertido"]:
        st.success(f"🟢 LEAD CONVERTIDO | Nota Atribuída: {historico[-1]['nota']}/10.0")
    else:
        st.error(f"🔴 NÃO CONVERTIDO | Nota Atribuída: {historico[-1]['nota']}/10.0")

else:
    st.info("👈 Selecione uma sessão na barra lateral e clique em 'Gerar Análise de Performance com IA' para começar.")
