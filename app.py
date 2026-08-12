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

# Estilização Clean
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 12px 16px;
        border-radius: 8px;
    }
    h3 {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard de Feedbacks - Sessão 1A1")
st.caption("Avaliador Inteligente com Base no Roteiro Oficial CRH & Mentoria Henrique Bento")
st.divider()

# Barra Lateral
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
    Você é um Sales Enablement Director e Auditor Comercial de Elite da Ricarreira/CRH.
    Sua missão é auditar e avaliar minuciosamente uma transcrição de Sessão 1A1 comparando-a estritamente contra o ROTEIRO OFICIAL DE VENDAS DA CRH e o MODELO DE ANÁLISE DO HENRIQUE BENTO.

    ROTEIRO E CHECKLIST TÉCNICO DA CRH PARA AUDITAR:
    1. Transição & História do Herói Relutante: Validação do gráfico do Raio-X + história da relutância do Ricardo em criar o acompanhamento (apenas 4 vagas/mês).
    2. Provas Sociais Direcionadas: Apresentação de depoimentos conectando explicitamente a história exibida com a maior dor dita pelo lead no Raio-X, ANTES de detalhar entregáveis.
    3. Passeio pelos Entregáveis (Pilares + App): Explicação do 'Mapa de Carreira' e funcionalidades do app (Busca ATS, Controle de Vagas, Banco de Currículos Aprovados e Bônus de Onboarding/Aumento).
    4. Validação da Solução (Nota 0 a 10): Pergunta 'De 0 a 10 o quanto isso te ajuda?' e tratamento direto das objeções caso a resposta seja menor que 10, antes de abrir preço.
    5. Ancoragem Dupla de Valor: 
       - Ancoragem Acadêmica: Cálculo estimado de investimentos passados no LinkedIn.
       - Calculadora 'Tempo é Dinheiro': Cálculo ostensivo da perda financeira por dia e por semana parado.
    6. Escada de Oferta e Negociação:
       - Âncora 1 (Cheio): 12x R$ 997 (Entrada R$ 500 + 12x R$ 955 ou R$ 9.500 à vista).
       - Âncora 2 (Urgência 23h59): R$ 8.500 (Entrada R$ 500 + 10x R$ 800 ou R$ 6.500 à vista).
       - Âncora 3 (Ao Vivo): R$ 5.000 (Entrada R$ 500 + 10x R$ 550 ou R$ 4.500 à vista).
       - Cartas de Fechamento: Uso da Garantia Condicional de 51 dias, Combo R$ 500 para Dailys e flexibilização de entrada.

    DIRETRIZES DE CATEGORIZAÇÃO DOS FEEDBACKS:
    - PONTOS FORTES: Momentos e trechos exatos em que o closer executou com excelência o padrão Ricarreira.
    - PONTOS DE MELHORIA (🚨 Erros Práticos): Falhas técnicas diretas, erros operacionais e desvios do roteiro executados na chamada que exigem correção imediata (ex: hesitação no fechamento, pulo da nota de 0 a 10, subexplicação da calculadora).
    - PONTOS DE ATENÇÃO (💡 Alertas & Recomendações): Cuidados preventivos, alertas estratégicos de gestão de tempo, ritmo e tom de voz para evitar objeções nas próximas sessões.

    Seja cirúrgico e aprofundado na análise do tempo de permanência e qualidade do discurso. Cite falas e omissões reais do vendedor.

    Retorne ESTRITAMENTE um objeto JSON válido no formato:
    {{
        "nota_geral": 7.5,
        "notas_criterios": {{
            "Herói Relutante & Conexão": 8.0,
            "Provas e Depoimentos": 7.0,
            "Apresentação de Entregáveis": 8.5,
            "Ancoragem (Acadêmica + Calculadora)": 6.5,
            "Escada de Preços & Negociação": 6.0,
            "Linguagem & Fechamento": 7.5
        }},
        "pontos_fortes": [
            "Trecho ou execução exata alinhada com o roteiro oficial da CRH."
        ],
        "pontos_melhoria": [
            "Erros práticos, falhas técnicas e desvios diretos do roteiro oficial que ocorreram na chamada e precisam de correção imediata."
        ],
        "pontos_atencao": [
            "Alertas preventivos, recomendações de cuidados no tom de voz, ritmo ou gestão de tempo para evitar falhas em chamadas futuras."
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
        with st.spinner("Auditando a sessão contra o Roteiro Oficial CRH e Mentoria Henrique Bento..."):
            try:
                data = analyze_session(transcript, api_key)
                
                # Resumo
                col1, col2, col3 = st.columns(3)
                col1.metric("Score Geral", f"{data['nota_geral']} / 10")
                col2.metric("Lead Analisado", lead_name)
                col3.metric("Equipe Avaliada", closers)
                
                st.divider()
                
                # Gráfico e Métricas
                st.subheader("📈 Desempenho por Pilar do Roteiro Oficial CRH")
                
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
                
                # Seção de Feedbacks
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
