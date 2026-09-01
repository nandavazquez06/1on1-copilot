import streamlit as st
import datetime
import json
import re
import pandas as pd
import plotly.express as px
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")

# Inicialização do banco de histórico de auditorias
if "historico_analises" not in st.session_state:
    st.session_state["historico_analises"] = []

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

# Puxa credenciais das Secrets
openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "")

# ID Padrão da Tabela Master Ricarreira
ID_PLANILHA_PADRAO = "15EByU5f2Q_vX6L2mGkZ09jTh3J3aZJ3_G5eH9Wk8E"

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

if st.sidebar.button("🔄 Sincronizar Agenda & Tabela Master"):
    try:
        if "google_credentials" in st.secrets:
            creds_dict = dict(st.secrets["google_credentials"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            SCOPES = [
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/spreadsheets.readonly'
            ]
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            
            # 1. Busca Reuniões da Agenda
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

            # 2. Busca Dados da Tabela Master no Google Sheets
            try:
                service_sheets = build('sheets', '4', credentials=credentials)
                sheet_result = service_sheets.spreadsheets().values().get(
                    spreadsheetId=ID_PLANILHA_PADRAO, range="Base_Master!A1:Z1000"
                ).execute()
                values = sheet_result.get('values', [])
                if values:
                    df = pd.DataFrame(values[1:], columns=values[0])
                    st.session_state["dados_planilha"] = df
            except Exception as e_sheet:
                st.sidebar.warning(f"Agenda sincronizada, mas não foi possível ler a Tabela Master: {str(e_sheet)}")

            st.sidebar.success(f"Encontrados {len(st.session_state['eventos_carregados'])} Diagnósticos!")
        else:
            st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets.")
    except Exception as e:
        st.sidebar.error(f"Erro ao sincronizar: {str(e)}")

# -------------------------------------------------------------
# 1. CARDS GLOBAIS DE FEEDBACK & CONVERSÃO (INCLUINDO FUP)
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
    st.metric("📅 Sessões Agendadas", f"{total_periodo}")
with col2:
    st.metric("📊 Auditadas pela IA", f"{total_analisadas}")
with col3:
    st.metric("🟢 Vendas (Ato / FUP)", f"{total_convertidos} ({vendas_ato} Ato | {vendas_fup} FUP)")
with col4:
    st.metric("📈 Taxa de Conversão", f"{taxa_conversao:.1f}%")
with col5:
    st.metric("⭐ Nota Média FHT", f"{media_nota:.1f} / 10.0")

st.markdown("---")

# -------------------------------------------------------------
# 2. SELEÇÃO DE REUNIÃO E INTEGRALIZAÇÃO DA TABELA MASTER
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
        nome_lead = evento_obj.get('summary', 'Diagnóstico Gratuito de Carreira')
        descricao_evento = evento_obj.get("description", "")
        transcricao_texto = descricao_evento if descricao_evento.strip() else f"Sessão: {nome_lead}\nData: {evento_obj.get('start', {}).get('dateTime', '')}"

    # Cruzamento automático com a Tabela Master pelo Nome do Lead
    status_master = "Perdido"
    closer_master = "Desconhecido"
    objecao_master = "Não registrada"
    
    if not df_master.empty and "Cliente" in df_master.columns:
        match = df_master[df_master["Cliente"].astype(str).str.lower().str.contains(nome_lead.lower().replace("diagnóstico gratuito de carreira -", "").strip(), na=False)]
        if not match.empty:
            status_master = match.iloc[0].get("Status", "Perdido")
            closer_master = match.iloc[0].get("Closer", "Desconhecido")
            objecao_master = match.iloc[0].get("Objeção / Obs.", match.iloc[0].get("Objeção", "Não registrada"))

    with col_btn:
        st.write(" ")
        st.write(" ")
        gerar_btn = st.button("🚀 Auditar com IA", use_container_width=True)

    st.info(f"📌 **Status Tabela Master:** `{status_master}` | **Closer:** `{closer_master}` | **Objeção Registrar:** `{objecao_master}`")

    if gerar_btn:
        if not openai_key:
            st.error("🔑 OpenAI API Key não encontrada.")
        else:
            with st.spinner("🤖 Analisando reunião e cruzando com o status da Tabela Master..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    
                    prompt_sistema = f"""Você é um auditor sênior de chamadas High Ticket da Ricarreira (programa CRH, fundado pelo especialista Ricardo).
Sua missão é auditar o desempenho do closer na sessão 1A1, utilizando a metodologia FHT (Formula High Ticket).

DADOS DA TABELA MASTER:
- Status Real da Lead: {status_master}
- Closer Responsável: {closer_master}
- Objeção Registrada no CRM: {objecao_master}

REGRAS RÍGIDAS DE NOTA & CONVERSÃO:
1. IDENTIFICAÇÃO DE STATUS:
   - Se o Status na Tabela Master for 'Ganho (Ato)' ou 'Ganho (FUP)', a nota OBRIGATORIAMENTE DEVE SER ENTRE 8.0 E 10.0.
   - Destaque no feedback se a conversão ocorreu no ato da reunião ou se foi um ganho via acompanhamento/follow-up (FUP).
   - O primeiro item da resposta DEVE SER O STATUS DA SESSÃO em destaque:
     `🟢 STATUS: LEAD CONVERTIDO (GANHO ATO)` ou `🟢 STATUS: LEAD CONVERTIDO (GANHO FUP)` ou `🔴 STATUS: NÃO CONVERTIDO`.

2. LÓGICA DE AVALIAÇÃO FHT:
   - Avalie os pilares do roteiro: Diagnóstico, Ancoragem Acadêmica & LinkedIn, Calculadora 'Tempo é Dinheiro', Ancoragem Dupla de Preço e como a objeção '{objecao_master}' foi trabalhada.

ESTRUTURA DE RESPOSTA OBRIGATÓRIA (Markdown):
### [STATUS DESTACADO]

**Resumo Executivo & Nota do Closer: [X.X / 10]**

---
- **🎯 Pontos Fortes da Sessão**
- **🚨 Pontos de Melhoria Críticos**
- **💡 Plano de Ação para o Próximo Treinamento**
"""
                    
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": f"Lead: {nome_lead}\nTranscrição/Dados:\n{transcricao_texto}"}
                        ],
                        temperature=0.3
                    )
                    
                    analise_ia = response.choices[0].message.content
                    is_convertido = "LEAD CONVERTIDO" in analise_ia
                    
                    match_nota = re.search(r"(\d+[\.,]?\d*)\s*/\s*10", analise_ia)
                    nota_extraida = float(match_nota.group(1).replace(",", ".")) if match_nota else (8.5 if is_convertido else 6.0)

                    st.session_state["historico_analises"].append({
                        "Data": evento_obj.get('start', {}).get('dateTime', '')[:10],
                        "Cliente": nome_lead,
                        "Closer": closer_master,
                        "status_venda": status_master,
                        "Status": f"🟢 {status_master}" if is_convertido else "🔴 Perdido",
                        "Objeção": objecao_master,
                        "convertido": is_convertido,
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
# 3. TABELA DE AUDITORIAS E FEEDBACK COMPLETO
# -------------------------------------------------------------
if historico:
    st.subheader("📑 Tabela de Auditorias Realizadas")
    df_hist = pd.DataFrame(historico)
    st.dataframe(df_hist[["Data", "Cliente", "Closer", "Status", "Objeção", "nota"]], use_container_width=True)

    with st.expander("🔍 Ver Último Feedback Completo Gerado pela IA", expanded=True):
        st.markdown(historico[-1]["feedback_completo"])
