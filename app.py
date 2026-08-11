import streamlit as st
import pandas as pd
import json
from openai import OpenAI

# Configuração da página
st.set_page_config(
    page_title="1on1 Sales Copilot - Ricarreira",
    page_icon="📊",
    layout="wide"
)

# Estilização CSS para visual profissional
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Avaliação - Sessão 1A1 & Closing Calls")
st.caption("Avaliador Inteligente de Performance Comercial - Ricarreira")

# Lateral - Configurações
with st.sidebar:
    st.header("⚙️ Configurações da Chamada")
    api_key = st.text_input("OpenAI API Key", type="password")
    
    lead_name = st.text_input("Nome do Lead", value="Mariana Mansur")
    closers = st.text_input("Avaliados / Closers", value="Fernanda Vazquez & Ricardo Batista")
    
    transcript = st.text_area("Cole a Transcrição da Sessão aqui:", height=300)
    process_btn = st.button("🚀 Gerar Dashboard de Feedback", type="primary")

# Função de Análise usando OpenAI
def analyze_session(text, key):
    client = OpenAI(api_key=key)
    
    prompt = f"""
    Você é um Sales Enablement Manager especializado em mentorias e vendas B2B de alto ticket.
    Analise a transcrição abaixo com base nos 5 pilares do processo comercial da Ricarreira (Notas de 0 a 10):
    1. Rapport e Conexão Inicial (criação de vínculo pessoal/contextual)
    2. Profundidade no Raio-X / Diagnóstico (investigação do 'porquê' das notas baixas)
    3. Ancoragem de Valor e Prova Social (uso de depoimentos/ROI sem poluição visual)
    4. Tratamento de Objeções (isolamento de dúvidas e negociação de preço)
    5. Postura e Linguagem Comercial (firmeza, sem hesitações como 'eu acho')

    Retorne ESTRITAMENTE um objeto JSON válido (sem texto antes ou depois) no formato:
    {{
        "nota_geral": 7.8,
        "notas_criterios": {{
            "Rapport & Conexão": 8.5,
            "Diagnóstico / Raio-X": 7.5,
            "Ancoragem & Prova Social": 7.0,
            "Tratamento de Objeções": 6.5,
            "Postura & Linguagem": 8.0
        }},
        "pontos_fortes": [
            "Excelente abertura e rapport contextual.",
            "Boa condução na identificação do canal de entrada do lead."
        ],
        "oportunidades_melhoria": [
            "Aprofundar nos porquês das notas baixas do Raio-X antes de apresentar a solução.",
            "Substituir o envio disperso de materiais pelo Mapa de Carreira de 51 dias."
        ],
        "plano_de_acao": [
            "Usar a pergunta de isolamento: 'Fora a questão do investimento, há algo mais que nos impede de começar?'",
            "Segmentar a entrega de bônus conforme o perfil do cliente (empregado x desempregado)."
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

# Construção do Dashboard
if process_btn:
    if not api_key:
        st.error("Por favor, informe a sua OpenAI API Key na barra lateral.")
    elif not transcript:
        st.warning("Por favor, insira o texto da transcrição.")
    else:
        with st.spinner("Analisando a sessão e processando as métricas..."):
            try:
                data = analyze_session(transcript, api_key)
                
                st.success("Análise concluída!")
                st.divider()
                
                # Resumo Geral em Cartões
                col1, col2, col3 = st.columns(3)
                col1.metric("Score Geral da Chamada", f"{data['nota_geral']} / 10")
                col2.metric("Lead Analisado", lead_name)
                col3.metric("Equipe Avaliada", closers)
                
                st.divider()
                
                # Gráfico e Notas
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
                
                # Feedbacks Qualitativos
                c_fortes, c_melhorias, c_plano = st.columns(3)
                
                with c_fortes:
                    st.subheader("🎯 Pontos Fortes")
                    for pf in data["pontos_fortes"]:
                        st.success(f"• {pf}")
                        
                with c_melhorias:
                    st.subheader("🚨 Oportunidades")
                    for om in data["oportunidades_melhoria"]:
                        st.warning(f"• {om}")
                        
                with c_plano:
                    st.subheader("💡 Plano de Ação")
                    for pa in data["plano_de_acao"]:
                        st.info(f"• {pa}")

            except Exception as e:
                st.error(f"Erro ao processar análise: {e}")
else:
    st.info("👈 Insira os dados na barra lateral e clique em 'Gerar Dashboard de Feedback' para iniciar.")
