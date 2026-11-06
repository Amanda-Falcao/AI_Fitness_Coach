import os
from typing import List, Dict, Any
from langchain_core.tools import tool
from tavily import TavilyClient
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.tools.calculations import calculate_fitness_metrics

# --- CONFIGURAÇÃO ---
try:
    TAVILY_CLIENT = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
except:
    pass

# --- FERRAMENTA 1: CÁLCULOS METABÓLICOS ---

@tool
def calcular_metricas(weight_kg: float, height_cm: float, age_years: int, gender: str) -> str:
    """
    Calcula o IMC e a TMB (Taxa Metabólica Basal) para dar uma base nutricional ao plano.
    
    Argumentos: weight_kg (float), height_cm (float), age_years (int), gender (str).
    """
    metrics = calculate_fitness_metrics(
        age_years=age_years,
        weight_kg=weight_kg,
        height_cm=height_cm,
        sex=gender,
        training_days_per_week=0,
        goal="maintenance",
    )
    return (
        f"Reference calculations (estimates): BMI = {metrics.bmi:.2f} | "
        f"BMR = {metrics.basal_metabolic_rate_kcal} kcal/day."
    )


# --- FERRAMENTA 2: BUSCA NA WEB (Tavily) ---

@tool
def busca_na_web(query: str) -> str:
    """
    Busca informações ATUAIS na web sobre melhores divisões de treino, 
    tendências fitness, ou práticas de musculação.
    
    Use SOMENTE para buscar informações externas e gerais.
    """
    try:
        results = TAVILY_CLIENT.search(query=query, search_depth="basic")
        snippets = [f"Resultado da Web: {r['content']}" for r in results['results'][:3]]
        return "\n\n".join(snippets)
    except Exception:
        return "Busca na Web não encontrou resultados relevantes."


# --- FUNÇÕES DE RAG PARA O NOTEBOOK ---

def get_rag_retriever(chroma_path: str, embedding_model):
    """Inicializa e retorna o retriever RAG, usando ChromaDB."""
    try:
        db = Chroma(persist_directory=chroma_path, embedding_function=embedding_model)
        return db.as_retriever(k=5)
    except Exception as e:
        print(f"AVISO: Erro ao carregar DB Chroma: {e}")
        return None

def criar_rag_tool(retriever_instance):
    """Cria a Tool RAG a partir do retriever, injetando o nome e a descrição."""
    
    # Valida se o retriever foi carregado corretamente
    if retriever_instance is None:
        @tool
        def recuperar_detalhes_exercicio_falha(query: str) -> str:
            """Base de conhecimento interna sobre exercícios, técnicas, séries e repetições ideais (RAG)."""
            return "AVISO RAG: A base de conhecimento não foi carregada. As informações podem ser menos precisas."
        return recuperar_detalhes_exercicio_falha

    # Se o retriever estiver OK, cria a Tool oficial
    @tool
    def recuperar_detalhes_exercicio(query: str) -> str:
        """Search the internal knowledge base for exercises, techniques, sets, and repetitions."""
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
        documents = retriever_instance.invoke(query.strip())
        if not documents:
            return "No relevant knowledge documents were found."
        return "\n\n".join(document.page_content for document in documents)

    return recuperar_detalhes_exercicio
