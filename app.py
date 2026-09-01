import streamlit as st
import datetime
import json
import re
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

st.set_page_config(page_title="Dashboard de Feedbacks - Sessão 1A1", page_icon="📊", layout="wide")

# Estilização CSS customizada para evitar cortes no layout
st.markdown("""
    <style>
    /* Estilo dos cards de métricas para não cortar textos */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: #31333F !important;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

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

            # 2. Busca Dados da Planilha Lendo Múltiplas Abas
            try:
                service_sheets = build('sheets', 'v4', credentials=credentials)
                
                sheet_metadata = service_sheets.spreadsheets().get(spreadsheetId=ID_PLANILHA_REAL).execute()
                sheets = sheet_metadata.get('sheets', [])
                nome_aba = sheets[0].get("properties", {}).get("title", "Base_Master") if sheets else "Base_Master"
                
                sheet_result = service_sheets.spreadsheets().values().get(
                    spreadsheetId=ID_PLANILHA_REAL, range=f"'{nome_aba}'!A1:Z1000"
                ).execute()
                
                values = sheet_result.get('values', [])
                if values:
                    df = pd.DataFrame(values[1:], columns=values[0])
                    st.session_state["dados_planilha"] = df
            except Exception as e_sheet:
                st.sidebar.warning(f"Agenda OK, erro na planilha: {str(e_sheet)}")

            st.sidebar.success(f"Encontrados {len(st.session_state['eventos_carregados'])} Diagnósticos!")
        else:
            st.sidebar.error("Seção [google_credentials] não encontrada nas Secrets.")
    except Exception as e:
        st.sidebar.error(f"Erro ao sincronizar: {str(e)}")

# -------------------------------------------------------------
# 1. CARDS GLOBAIS DE FEEDBACK & CONVERSÃO (SEM CORTES)
# -------------------------------------------------------------
historico = st.session_state["historico_analises"]
total_periodo = len(st.session_state["eventos_carregados"])
total_analisadas = len(historico)
vendas_ato = sum(1 for item in historico if "Ato" in str(item.get("status_venda", "")))
vendas_fup = sum(1 for item in historico if "FUP" in str(item.get("status_venda", "")))
total_convertidos = sum(1 for item in historico if item.get("convertido", False))
taxa_conversao = (total_convertidos / total_analisadas * 100) if total_analisadas > 0 else 0.0
media_nota = (sum(item.get("nota", 0.0) for item in historico) / total_analisadas) if total_analisadas > 0 else 0.0

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("📅 Sessões Agendadas", f"{total_periodo}")
with col2:
    st.metric("📊 Auditadas pela IA", f"{total_analisadas}")
with col3:
    st.metric("🟢 Convertidos (Ato / FUP)", f"{total_convertidos} ({vendas_ato} Ato | {vendas_fup} FUP)")
with col4:
    st.metric("📈 Taxa de Conversão", f"{taxa_conversao:.1f}%")
with col5:
    st.metric("⭐ Nota Média FHT", f"{media_nota:.1f} / 10.0")

st.markdown("---")

# -------------------------------------------------------------
# 2. SELEÇÃO DE REUNIÃO E CRUZAMENTO COM TABELA MASTER
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
    closer_master_auto = "Ricardo"
    objecao_master_auto = "Não registrada"
    
    if not df_master.empty:
        col_cliente = [c for c in df_master.columns if "cliente" in c.lower() or "lead" in c.lower() or "nome" in c.lower()]
        nome_col = col_cliente[0] if col_cliente else df_master.columns[0]
        
        # Busca focado nos nomes da lead (ex: 'Ana Duran')
        partes_nome = nome_lead_limpo.lower().split()
        primeiro_nome = partes_nome[0] if partes_nome else ""
        
        match = df_master[df_master[nome_col].astype(str).str.lower().str.contains(primeiro_nome, na=False)] if primeiro_nome else pd.DataFrame()
        
        # Se houver mais de uma palavra no nome (ex: Ana Duran), tenta refinar a busca
        if len(match) > 1 and len(partes_nome) > 1:
            match_refinado = match[match[nome_col].astype(str).str.lower().str.contains(partes_nome[1], na=False)]
            if not match_refinado.empty:
                match = match_refinado

        if not match.empty:
            col_status = [c for c in df_master.columns if "status" in c.lower()]
            col_closer = [c for c in df_master.columns if "closer" in c.lower()]
            col_obj = [c for c in df_master.columns if "objeção" in c.lower() or "obs" in c.lower()]
            
            status_master_auto = match.iloc[0].get(col_status[0], "Perdido") if col_status else "Perdido"
            closer_master_auto = match.iloc[0].get(col_closer[0], "Ricardo") if col_closer else "Ricardo"
            objecao_master_auto = match.iloc[0].get(col_obj[0], "Não registrada") if col_obj else "Não registrada"

    # Define o índice padrão correto baseado no que veio da planilha
    status_str_lower = str(status_master_auto).lower()
    if "fup" in status_str_lower:
        idx_padrao = 1
    elif "ato" in status_str_lower or "ganho" in status_str_lower:
        idx_padrao = 0
    else:
        idx_padrao = 2

    # Campos de Confirmação Visuais
    col_st1, col_st2, col_st3 = st.columns(3)
    with col_st1:
        status_final = st.selectbox(
            "Status da Venda (Master):",
            ["Ganho (Ato)", "Ganho (FUP)", "Perdido / Não Convertido"],
            index=idx_padrao
        )
    with col_st2:
        closer_final = st.text_input("Closer Responsável:", value=closer_master_auto if str(closer_master_auto) != "None" else "Ricardo")
    with col_st3:
        objecao_final = st.text_input("Objeção do Lead:", value=objecao_master_auto if str(objecao_master_auto) != "None" else "Nenhuma / Fechado")

    is_venda_confirmada = "ganho" in str(status_final).lower()

    with col_btn:
        st.write(" ")
        st.write(" ")
        gerar_btn = st.button("🚀 Auditar com IA", use_container_width=True)

    if gerar_btn:
        if not openai_key:
            st.error("🔑 OpenAI API Key não encontrada.")
        else:
            with st.spinner("🤖 Analisando reunião com regras estritas de conversão..."):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=openai_key)
                    
                    if is_venda_confirmada:
                        prompt_sistema = f"""Você é um auditor sênior de chamadas High Ticket da Ricarreira (programa CRH, fundado por Ricardo).
Sua missão é auditar o desempenho do closer na sessão 1A1, utilizando a metodologia FHT.

ATENÇÃO: ESTA CHAMADA FOI UMA VENDA CONVERTIDA! ({status_final})
- Closer Responsável: {closer_final}
- Status Registrado: {status_final}

REGRAS ABSOLUTAS:
1. O primeiro item da sua resposta DEVE SER O STATUS DESTACADO:
   `🟢 STATUS: LEAD CONVERTIDO ({status_final.upper()})`

2. A nota final OBRIGATORIAMENTE DEVE SER ENTRE 8.0 E 10.0 (ex: 9.0/10). 
   Se for 'Ganho (FUP)', elogie a condução que manteve o lead engajado até o fechamento no acompanhamento.

ESTRUTURA DE RESPOSTA OBRIGATÓRIA (Markdown):
### 🟢 STATUS: LEAD CONVERTIDO ({status_final.upper()})

**Resumo Executivo & Nota do Closer: [X.X / 10]**

---
- **🎯 Pontos Fortes da Sessão**
- **🚨 Pontos de Melhoria Críticos**
- **💡 Plano de Ação para o Próximo Treinamento**
"""
                    else:
                        prompt_sistema = f"""Você é um auditor sênior de chamadas High Ticket da Ricarreira (programa CRH).
Sua missão é auditar a chamada com a metodologia FHT.

DADOS REGISTRADOS:
- Status Real: {status_final}
- Closer: {closer_final}
- Objeção: {objecao_final}

ESTRUTURA DE RESPOSTA OBRIGATÓRIA:
### 🔴 STATUS: NÃO CONVERTIDO

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
                        "Closer": closer_final,
                        "status_venda": status_final,
                        "Status": f"🟢 {status_final}" if is_convertido_final else "🔴 Perdido",
                        "Objeção": objecao_final,
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
# 3. TABELA DE AUDITORIAS (LAYOUT LIMPO E FORMATADO)
# -------------------------------------------------------------
if historico:
    st.subheader("📑 Tabela de Auditorias Realizadas")
    df_hist = pd.DataFrame(historico)
    
    # Renomeia colunas para exibição amigável
    df_exibicao = df_hist[["Data", "Cliente", "Closer", "status_venda", "Objeção", "nota"]].copy()
    df_exibicao.columns = ["Data", "Cliente", "Closer", "Status da Venda", "Objeção", "Nota FHT"]
    
    st.dataframe(df_exibicao, use_container_width=True)

    with st.expander("🔍 Ver Último Feedback Completo Gerado pela IA", expanded=True):
        st.markdown(historico[-1]["feedback_completo"])
