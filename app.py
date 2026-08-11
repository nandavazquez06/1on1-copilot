import streamlit as st
import pandas as pd
import json
from openai import OpenAI

# Configuração da página
st.set_page_config(
    page_title="Dashboard 1A1 - Ricarreira",
    page_icon="📊",
    layout="wide"
)

# Estilização Clean (CSS sutil para organizar o layout)
st.markdown("""
<style>
    /* Remove espaçamentos exagerados no topo */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* Estilo clean para os cards de métricas */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 12px 16px;
        border-radius: 8px;
    }
    /* Deixa os títulos das caixas mais limpos */
    h3 {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Título Limpo
st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.divider()

# Barra Lateral - Entrada de Dados
with st.sidebar:
    st.header("⚙️ Configurações da Chamada")
    api_key = st.text_input("OpenAI API Key", type="password")
    
    lead_name = st.text_input("Nome do Lead", value="Mariana Mansur")
    closers = st.text_input("Avaliados / Closers", value="Fernanda Vazquez & Ricardo Batista")
    
    transcript = st.text_area("Cole a Transcrição da Sessão aqui:", height=300)
    process_btn = st.button("🚀 Gerar Análise", type="primary", use_container_width=True)

# Função de Análise
def analyze_session(text, key):
    client = OpenAI(api_key=key)
    
    prompt = f"""
    Você é um Sales Enablement Director e Coach Executivo de Vendas B2B/High-Ticket na Ricarreira.
    Analise a transcrição de uma sessão de vendas/mentoria de forma HIPER-ESPECÍFICA e CRÍTICA.
    PROIBIDO USAR FEEDBACKS GENÉRICOS OU CLICHÊS. Cite momentos e falas exatas da chamada.

    Avalie a sessão com base nestes 6 pilares comerciais (Notas de 0 a 10):
    1. Rapport e Conexão Inicial
    2. Profundidade no Raio-X / Diagnóstico
    3. Estrutura e Pitch da Oferta
    4. Ancoragem de Valor e Prova Social
    5. Tratamento de Objeções e Negociação
    6. Postura e Linguagem Comercial

    Retorne ESTRITAMENTE um objeto JSON válido no formato:
    {{
        "nota_geral": 7.5,
        "notas_criterios": {{
            "Rapport & Conexão": 8.0,
            "Diagnóstico / Raio-X": 7.0,
            "Estrutura da Oferta": 6.5,
            "Ancoragem & Prova Social": 7.0,
            "Tratamento de Objeções": 6.0,
            "Postura & Linguagem": 7.5
        }},
        "pontos_fortes": [
            "Citação ou momento exato em que o closer se destacou positivamente."
        ],
        "pontos_melhoria": [
            "Falha prática ou técnica específica identificada no diagnóstico, oferta ou fechamento."
        ],
        "pontos_atencao": [
            "Alertas estratégicos, riscos de objeção não tratada ou comportamentos a monitorar."
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

# Renderização do Dashboard
if process_btn:
    if not api_key:
        st.error("Por favor, informe a sua OpenAI API Key na barra lateral.")
    elif not transcript:
        st.warning("Por favor, insira o texto da transcrição.")
    else:
        with st.spinner("Analisando a sessão..."):
            try:
                data = analyze_session(transcript, api_key)
                
                # Resumo em Cartões Limpos
                col1, col2, col3 = st.columns(3)
                col1.metric("Score Geral", f"{data['nota_geral']} / 10")
                col2.metric("Lead Analisado", lead_name)
                col3.metric("Equipe Avaliada", closers)
                
                st.divider()
                
                # Gráfico e Métricas
                st.subheader("📈 Desempenho por Pilar Comercial")
                
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
                
                # Seção Clean de Feedbacks em 3 Colunas
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

            except Exception as e:
                st.error(f"Erro ao processar análise: {e}")
else:
    st.info("👈 Insira a API Key e a Transcrição na barra lateral para carregar a análise.")
