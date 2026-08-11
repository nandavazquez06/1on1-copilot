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

# Estilização CSS
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
    process_btn = st.button("🚀 Gerar Dashboard Detalhado", type="primary")

# Função de Análise Hiper-Específica
def analyze_session(text, key):
    client = OpenAI(api_key=key)
    
    prompt = f"""
    Você é um Sales Enablement Director e Coach Executivo de Vendas B2B/High-Ticket na Ricarreira.
    Sua tarefa é analisar a transcrição de uma sessão de vendas/mentoria de forma HIPER-ESPECÍFICA e CRÍTICA.
    PROIBIDO USAR FEEDBACKS GENÉRICOS OU CLICHÊS. Toda crítica ou elogio DEVE obrigatoriamente citar momentos, falas ou fatos ocorridos na chamada.

    Avalie a sessão com base nestes 6 pilares comerciais (Notas de 0 a 10):
    1. Rapport e Conexão Inicial: Conexão sincera, quebra de gelo usando contexto real (ex: cidade, conexões em comum).
    2. Profundidade no Raio-X / Diagnóstico: Investigação dos "porquês" por trás das notas baixas dadas pelo lead, fazendo-o verbalizar a dor.
    3. Estrutura e Pitch da Oferta: Clareza na solução. Vendeu o "Mapa/Caminho" de execução em vez de poluir a tela com excesso de aulas/módulos. Segmentou bônus para o perfil exato (empregado vs desempregado).
    4. Ancoragem de Valor e Prova Social: Uso de comparações de preço (ex: pós-graduação/MBA vs ROI prático) e exibição de casos reais/depoimentos.
    5. Tratamento de Objeções e Negociação: Isolamento real de objeções de dinheiro/tempo, postura no fechamento e negociação de entrada/parcelamento sem queimar o valor do produto.
    6. Postura e Linguagem Comercial: Firmeza, autoridade, ausência de vícios de hesitação ("eu acho", "talvez", "se você quiser").

    Retorne ESTRITAMENTE um objeto JSON válido no formato abaixo:
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
            "[Cite um momento específico ou fala exata do vendedor que funcionou muito bem]",
            "[Cite outra evidência concreta identificada na transcrição]"
        ],
        "oportunidades_melhoria_oferta": [
            "Análise detalhada do Pitch da Oferta: O que especificamente faltou ao apresentar os entregáveis, o valor ou o mapa da mentoria?",
            "Erro/Incoerência técnica detectada: Apontar falha no diagnóstico, ancoragem ou condução da chamada.",
            "Linguagem e Condução: Ajustes práticos de comunicação do closer."
        ],
        "plano_de_acao_fechamento": [
            "Script/Frase exata a ser utilizada na próxima call ao apresentar a oferta.",
            "Ação prática para o próximo tratamento de objeção de investimento/garantia.",
            "Ajuste estrutural para a próxima sessão de vendas."
        ]
    }}

    Transcrição para Análise OBRIGATÓRIA:
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
        with st.spinner("Analisando minutagem e falas da sessão..."):
            try:
                data = analyze_session(transcript, api_key)
                
                st.success("Análise detalhada concluída!")
                st.divider()
                
                # Resumo
                col1, col2, col3 = st.columns(3)
                col1.metric("Score Geral da Chamada", f"{data['nota_geral']} / 10")
                col2.metric("Lead Analisado", lead_name)
                col3.metric("Equipe Avaliada", closers)
                
                st.divider()
                
                # Gráficos e Notas
                st.subheader("📈 Avaliação por Pilar Comercial & Oferta")
                
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
                
                # Feedbacks Qualitativos Específicos
                c_fortes, c_melhorias, c_plano = st.columns(3)
                
                with c_fortes:
                    st.subheader("🎯 Pontos Fortes (Fatos Reais)")
                    for pf in data["pontos_fortes"]:
                        st.success(f"• {pf}")
                        
                with c_melhorias:
                    st.subheader("🚨 Diagnóstico Crítico da Oferta")
                    for om in data["oportunidades_melhoria_oferta"]:
                        st.warning(f"• {om}")
                        
                with c_plano:
                    st.subheader("💡 Script & Plano de Ação")
                    for pa in data["plano_de_acao_fechamento"]:
                        st.info(f"• {pa}")

            except Exception as e:
                st.error(f"Erro ao processar análise: {e}")
else:
    st.info("👈 Insira a API Key e a Transcrição na barra lateral para gerar a análise cirúrgica.")
