import streamlit as st
import datetime
import json
import re
import pandas as pd
import plotly.express as px
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")

# Inicialização do histórico de auditorias
if "historico_analises" not in st.session_state:
    st.session_state["historico_analises"] = []

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente de Chamadas High Ticket | Metodologia FHT (Formula High Ticket)")

# Puxa Secrets
openai_key = st.secrets.get("openai_api_key", "")
id_agenda_secrets = st.secrets.get("google_calendar_id", "")

# Sidebar - Configurações de API e Conexão
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

if st.sidebar.button("🔄 Buscar Diagnósticos de Carreira"):
    try:
        if "google_credentials" in st.secrets:
            creds_dict = dict(st.secrets["google_credentials"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            service = build('calendar', 'v3', credentials=credentials)
            
            time_min = datetime.datetime.combine(inicio_data, datetime.time.min).isoformat() + 'Z'
            time_max = datetime.datetime.combine(fim_data, datetime.time.max).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=email_equipe,
                timeMin=time_min,
                timeMax=time_max,
                q="Diagnóstico Gratuito de Carreira",
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            events_filtrados = [
                e for e in events 
                if "diagnóstico gratuito de carreira" in e.get('summary', '').lower()
            ]
            
            if not events_filtrados:
                st.sidebar.info("Nenhum 'Diagnóstico Gratuito de Carreira' encontrado no período.")
                st.session_state["eventos_carregados"] = []
            else:
                st.session_state["eventos_carregados"] = events_filtrados
                st.sidebar.success(f"Encontrados {len(events_filtrados)} Diagnósticos no período!")
        else:
            st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets do Streamlit.")
    except Exception as e:
        st.sidebar.error(f"Erro na conexão com o Google: {str(e)}")

# -------------------------------------------------------------
# 1. CARDS GLOBAIS DE FEEDBACK & CONVERSÃO
# -------------------------------------------------------------
historico = st.session_state["historico_analises"]
total_periodo = len(st.session_state["eventos_carregados"])
total_analisadas = len(historico)
total_convertidos = sum(1 for item in historico if item.get("convertido", False))
taxa_conversao = (total_convertidos / total_analisadas * 100) if total_analisadas > 0 else 0.0
media_nota = (sum(item.get("nota", 0.0) for item in historico) / total_analisadas) if total_analisadas > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📅 Diagnósticos no Período", f"{total_periodo}")
with col2:
    st.metric("📊 Auditados pela IA", f"{total_analisadas}")
with col3:
    st.metric("🟢 Taxa de Conversão", f"{total_convertidos} ({taxa_conversao:.1f}%)")
with col4:
    st.metric("⭐ Nota Média FHT", f"{media_nota:.1f} / 10.0")

st.markdown("---")

# -------------------------------------------------------------
# 2. SELEÇÃO E AUDITORIA DE UMA REUNIÃO
# -------------------------------------------------------------
st.subheader("📋 Auditar Reunião 1A1")

if st.session_state["eventos_carregados"]:
    events = st.session_state["eventos_carregados"]
    opcoes_map = {}
    for e in events:
        nome = e.get('summary', 'Diagnóstico Gratuito de Carreira')
        data = e.get('start', {}).get('dateTime', e.get('start', {}).get('date', ''))[:10]
        try:
            d_obj = datetime.datetime.strptime(data, "%Y-%m-%d")
            data_br = d_obj.strftime("%d/%m")
        except:
            data_br = data
            
        label = f"🗓️ [{data_br}] {nome}"
        opcoes_map[label] = e

    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        evento_sel_label = st.selectbox("Selecione a Reunião para Auditar:", list(opcoes_map.keys()))
        evento_obj = opcoes_map[evento_sel_label]
        nome_lead = evento_obj.get('summary', 'Diagnóstico Gratuito de Carreira')
        descricao_evento = evento_obj.get("description", "")
        transcricao_texto = descricao_evento if descricao_evento.strip() else f"Sessão: {nome_lead}\nData: {evento_obj.get('start', {}).get('dateTime', '')}\nParticipantes: {', '.join([p.get('email', '') for p in evento_obj.get('attendees', []) if isinstance(p, dict)])}"

    with col_btn:
        st.write(" ")
        st.write(" ")
        gerar_btn = st.button("🚀 Auditar com IA", use_container_width=True)

    with st.expander("📄 Ver Detalhes / Transcrição da Reunião"):
        st.text_area("Conteúdo:", value=transcricao_texto, height=120, disabled=True)

    if gerar_btn:
        if not openai_key:
            st.error("🔑 OpenAI API Key não encontrada.")
        else:
            with st.spinner("🤖 Analisando reunião e gerando feedback FHT..."):
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
   - **LEAD CONVERTIDO (Nota 8.0 a 10.0):** Reconheça o sucesso comercial.
   - **NÃO CONVERTIDO + ROTEIRO BOM (Nota 6.5 a 8.0):** Pontue bem o processo, mas identifique os gatilhos faltantes.
   - **NÃO CONVERTIDO + ROTEIRO FRACO (Nota 0 a 6.0):** Se o closer cometeu erros de condução.

ESTRUTURA DE RESPOSTA OBRIGATÓRIA (Markdown):
### 🟢 STATUS: LEAD CONVERTIDO  *(ou 🔴 STATUS: NÃO CONVERTIDO)*

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
                            {"role": "user", "content": f"Empresa: Ricarreira\nLead/Sessão: {nome_lead}\n\nDados da Sessão:\n{transcricao_texto}"}
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
                        "Status": "🟢 Convertido" if is_convertido else "🔴 Não Convertido",
                        "convertido": is_convertido,
                        "nota": nota_extraida,
                        "feedback_completo": analise_ia
                    })

                    st.rerun()

                except Exception as err:
                    st.error(f"Erro na análise: {str(err)}")

else:
    st.info("👈 Clique em 'Buscar Diagnósticos de Carreira' na barra lateral para carregar a agenda do período.")

st.markdown("---")

# -------------------------------------------------------------
# 3. PAINEL DE PERFORMANCE DE FEEDBACKS & NOTAS
# -------------------------------------------------------------
if historico:
    st.subheader("📈 Análise Comparativa de Feedbacks FHT")
    
    col_g1, col_g2 = st.columns(2)
    
    df_hist = pd.DataFrame(historico)
    
    with col_g1:
        st.markdown("**Distribuição de Notas dos Feedbacks**")
        fig_notas = px.histogram(df_hist, x="nota", nbins=10, range_x=[0, 10], color_discrete_sequence=['#6366f1'])
        fig_notas.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="Nota FHT", yaxis_title="Quantidade de Sessões")
        st.plotly_chart(fig_notas, use_container_width=True)

    with col_g2:
        st.markdown("**Status de Conversão dos Feedbacks**")
        fig_status = px.pie(df_hist, names="Status", hole=0.5, color_discrete_sequence=['#10b981', '#ef4444'])
        fig_status.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_status, use_container_width=True)

    st.markdown("---")
    st.subheader("📑 Tabela de Auditorias Realizadas")
    st.dataframe(df_hist[["Data", "Cliente", "Status", "nota"]], use_container_width=True)

    # Exibe o relatório detalhado do último selecionado
    with st.expander("🔍 Ver Último Feedback Completo Gerado pela IA", expanded=True):
        st.markdown(historico[-1]["feedback_completo"])
