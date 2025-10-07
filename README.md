# AI TREINADOR FITNESS: Agente de IA para Criação de Planilhas de Treino de Musculação com LangGraph

## 🚀 Objetivo

Este projeto demonstra um agente de IA completo utilizando a arquitetura **LangGraph** para orquestrar um fluxo de trabalho complexo, gerando planos de treino de musculação personalizados e detalhados.

## 🛠️ Requisitos Técnicos

O agente integra os seguintes componentes:
* **LLM Principal:** **Groq** (Llama 3) para raciocínio e geração de conteúdo.
* **Busca na Web:** **Tavily Search** (Ferramenta Externa).
* **Cálculos:** Funções Python nativas (**IMC** e gasto calórico).
* **RAG:** **Hugging Face Embeddings** + **ChromaDB** (Base de Conhecimento Interna).

## 📥 Instalação

1.  **Clone o Repositório:**
    ```bash
    git clone [LINK_DO_REPOSITORIO]
    cd AI_FITNESS_COACH
    ```

2.  **Crie e Ative o Ambiente Virtual (Opcional, mas recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuração de APIs:**
    * Crie um arquivo chamado **`.env`** no diretório raiz.
    * Copie o conteúdo do `.env.example` para `.env` e preencha suas chaves **`GROQ_API_KEY`** e **`TAVILY_API_KEY`**.

## ⚙️ Fluxo de Trabalho e Execução

### Passo 1: Preparação do RAG

É **obrigatório** executar este notebook primeiro para criar a base de conhecimento local.

1.  **Crie o arquivo de conhecimento:** Garanta que o arquivo **`dados/conhecimento_fitness.txt`** exista e contenha as informações de treino.
2.  **Execute o Notebook:** Abra e rode todas as células do **`01_RAG_Preparacao.ipynb`** para gerar o diretório `dados/chroma_db`.

### Passo 2: Execução do Agente

O agente LangGraph será executado, passando por todos os nós e gerando o plano final.

1.  **Execute o Notebook Principal:** Abra e rode todas as células do **`02_Agente_Treinador_Fitness.ipynb`**.
2.  **Saída:** O plano de treino final será impresso no arquivo plano_de_treino_final.md
