# AI Fitness Coach

O AI Fitness Coach gera um plano de treinamento de força de três semanas a partir do perfil do usuário. A aplicação combina um LLM hospedado no Groq, um ciclo de ferramentas orquestrado pelo LangGraph, cálculos determinísticos do perfil, uma base local de conhecimento sobre treinamento com Chroma e pesquisa na web com Tavily.

Este projeto é um protótipo para portfólio de engenharia. Os planos gerados não são aconselhamento médico, e as estimativas de calorias são aproximadas.

## Funcionalidades

- Ciclo de chamadas ao modelo e ferramentas com LangGraph e limite de recursão.
- Validação do perfil e estimativas determinísticas de IMC e gasto energético.
- Geração aumentada por recuperação (RAG) sobre uma base local de textos de treinamento, com embeddings do Hugging Face e Chroma.
- Citações por exercício vinculadas a trechos realmente retornados pela ferramenta RAG interna.
- Pesquisa com Tavily para informações gerais atualizadas sobre treinamento.
- Contrato de saída JSON que exige exatamente três semanas e o número de sessões solicitado; a saída é validada antes da renderização determinística em Markdown.
- Campos obrigatórios de aviso de segurança, condições para interromper o treino e orientação para buscar ajuda profissional.
- Interface de linha de comando e notebook mantido para experimentação.
- Imagem Docker de execução e imagem isolada para testes com pytest.
- Workflow do GitHub Actions para testes e verificação da sintaxe dos notebooks.
- Logs JSON com duração da geração e uso de tokens informado pelo provedor, quando disponível.

## Arquitetura

```mermaid
flowchart LR
    CLI[Perfil na CLI] --> Prompt[Prompt do plano]
    Prompt --> Graph[Agente LangGraph]
    Graph -->|chamadas de ferramentas| Tools[Cálculos / RAG / Tavily]
    Tools --> Graph
    Graph -->|resposta final| Output[Plano em Markdown]
    Source[Texto de conhecimento sobre treinamento] --> Ingest[Divisão em trechos e geração de embeddings]
    Ingest --> Chroma[(Chroma)]
    Chroma --> Tools
```

Consulte a [documentação da arquitetura](docs/architecture.md) para conhecer as responsabilidades dos módulos e os fluxos de execução, e as [decisões de arquitetura](docs/decisions.md) para consultar os ADRs.
O protocolo e os resultados de referência do benchmark de recuperação estão em [avaliação do RAG](docs/evaluation.md).
Use o [roteiro de revisão dos planos](evaluation/plan_review_template.md) para registrar avaliações qualitativas de fundamentação, precisão das citações, comunicação de segurança, consistência e legibilidade.

## Requisitos

Recomendamos Docker Engine com o plugin Docker Compose. A imagem de execução usa Python 3.12 e instala a versão de PyTorch para CPU. Também é possível executar a aplicação em um ambiente local com Python 3.12 após instalar `requirements.txt`; o pytest está declarado separadamente em `requirements-test.txt`.

## Configuração

Copie `.env.example` para `.env` e informe as chaves de API:

```dotenv
GROQ_API_KEY=sua_chave_groq
TAVILY_API_KEY=sua_chave_tavily
```

As configurações opcionais são `CHROMA_PERSIST_DIRECTORY`, `EMBEDDING_MODEL_NAME` e `GROQ_MODEL_NAME`. Mantenha `.env` privado: ele é excluído do Git e do contexto de build do Docker.

## Compilar e executar com Docker Compose

Compile a imagem de execução:

```bash
docker compose build fitness-coach
```

Ingestione ou atualize a base de conhecimento. Na primeira execução, o modelo de embeddings será baixado e o processo poderá levar alguns minutos:

```bash
docker compose run --rm --entrypoint python fitness-coach -m app.rag.ingestion
```

Execute o benchmark determinístico de recuperação, que usa um conjunto pequeno de evidências revisadas manualmente:

```bash
docker compose run --rm --entrypoint python fitness-coach -m app.rag.evaluation
```

O benchmark informa hit-rate@k, mean reciprocal rank (MRR) e latência média de recuperação na máquina atual. Essas métricas verificam trechos de evidência específicos; elas não demonstram fidelidade semântica dos planos gerados.

Gere um plano:

```bash
docker compose run --rm --entrypoint python fitness-coach \
  -m app.main \
  --age 28 \
  --weight-kg 70 \
  --height-cm 170 \
  --gender female \
  --frequency 4 \
  --goal hipertrofia
```

O plano será salvo no host em `outputs/plano_de_treino_final.md`. O Compose mantém os dados do Chroma e os arquivos do modelo Hugging Face em volumes nomeados.

O LLM recebe instruções para retornar JSON estruturado. A aplicação rejeita respostas malformadas ou incompletas em vez de salvar um plano parcial e converte respostas válidas em Markdown. Essa validação estrutural não comprova segurança médica nem correção factual; revise os planos antes de utilizá-los.
Cada citação de exercício precisa apontar para um ID estável `KB-...` presente nas mensagens reais da ferramenta RAG. As fontes e os trechos exibidos são obtidos desses registros. Isso verifica a presença e a proveniência da citação, mas não se o texto citado sustenta logicamente a afirmação.

Os logs da geração são emitidos como linhas JSON. Incluem duração e número de sessões e, quando os metadados da resposta do provedor fornecem essa informação, o uso de tokens. Prompts, valores do perfil do usuário, trechos recuperados e credenciais não são registrados. A aplicação não estima o custo monetário.

## Executar localmente sem Docker

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env      # depois, adicione chaves de API válidas
python -m app.rag.ingestion
python -m app.main --age 28 --weight-kg 70 --height-cm 170 \
  --gender female --frequency 4 --goal hipertrofia
```

A CLI exige credenciais do Groq e Tavily e uma coleção Chroma já alimentada. O download dos modelos de linguagem e de embeddings requer acesso à rede.

## Executar os testes

Os testes usam substitutos (mocks/fakes) nas fronteiras com modelos e ferramentas e não chamam o Groq ou Tavily nem baixam um modelo de embeddings.

```bash
docker build --target test -t ai-fitness-coach:test .
```

Ou, em um ambiente local com as dependências de teste instaladas:

```bash
python -m pip install -r requirements-test.txt
python -m pytest -q
```

A mesma suíte determinística e a verificação da sintaxe dos notebooks são executadas pelo GitHub Actions em pushes e pull requests.

## Notebooks

- `01_RAG_Preparacao.ipynb` documenta o experimento original de RAG.
- `02_Agente_Treinador_Fitness.ipynb` continua como ponto de entrada experimental do agente e delega a configuração compartilhada de execução para `app/`.

A CLI é o ponto de entrada reproduzível da aplicação; os notebooks são destinados à exploração.

## Limitações conhecidas

- O benchmark de cinco consultas mede atualmente a recuperação de trechos específicos; relevância semântica e fidelidade das respostas ainda não foram medidas. O top-k permanece em 3 e não há limiar de similaridade.
- A proveniência das citações é validada, mas a relação de implicação entre a evidência e cada afirmação ainda não é avaliada automaticamente.
- Não há novas tentativas automáticas de chamadas à API, acompanhamento de custos por requisição nem rastros persistentes do agente.
- Os cálculos de condicionamento físico e gasto energético são heurísticas simplificadas e não devem ser usados como orientação clínica ou nutricional.
- A validação da saída verifica a estrutura e a presença de campos de segurança, mas não avalia semanticamente a segurança dos exercícios ou sua adequação médica.
- Registros existentes no Chroma com metadados de origem antigos podem coexistir com registros criados pela nova rotina de ingestão.

## Próximas melhorias

- Ampliar o conjunto de evidências do benchmark e revisar os resultados da recuperação com embeddings reais antes de ajustar o chunking ou o top-k.
- Aplicar o roteiro de revisão a várias gerações reais e sintetizar as observações antes de ajustar prompts ou recuperação.
- Adicionar métricas de latência e uso de tokens e avaliar a fidelidade das respostas em relação às evidências recuperadas.
- Fixar as versões das dependências de execução e atualizá-las periodicamente.
