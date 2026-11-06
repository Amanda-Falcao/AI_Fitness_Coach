# AI Fitness Coach

AI Fitness Coach generates a three-week strength-training plan from a user's profile. It combines a Groq-hosted LLM, a LangGraph tool loop, deterministic profile calculations, a Chroma-backed fitness knowledge base, and Tavily web search.

The project is an engineering portfolio prototype. The generated plan is not medical advice, and the calorie figures are rough estimates.

## Features

- LangGraph model/tool cycle with a bounded recursion limit.
- Profile validation and deterministic BMI and energy estimates.
- Retrieval-augmented generation over the local fitness knowledge text, using Hugging Face embeddings and Chroma.
- Tavily search for current general fitness information.
- CLI entry point and notebook retained for experimentation.
- Docker runtime and isolated pytest image target.

## Architecture

```mermaid
flowchart LR
    CLI[CLI profile] --> Prompt[Plan prompt]
    Prompt --> Graph[LangGraph agent]
    Graph -->|tool calls| Tools[Calculation / RAG / Tavily]
    Tools --> Graph
    Graph -->|final response| Output[Markdown plan]
    Source[Fitness knowledge text] --> Ingest[Chunk and embed]
    Ingest --> Chroma[(Chroma)]
    Chroma --> Tools
```

See [architecture](docs/architecture.md) for module responsibilities and execution flows, and [architecture decisions](docs/decisions.md) for the ADRs.

## Requirements

Docker Engine with the Docker Compose plugin is the recommended setup. The runtime image uses Python 3.12 and installs the CPU-only PyTorch wheel. A local Python 3.12 environment can also run the app after installing `requirements.txt`; pytest is declared separately in `requirements-test.txt`.

## Configuration

Copy `.env.example` to `.env` and provide API keys:

```dotenv
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
```

The optional settings are `CHROMA_PERSIST_DIRECTORY`, `EMBEDDING_MODEL_NAME`, and `GROQ_MODEL_NAME`. Keep `.env` private; it is excluded from Git and the Docker build context.

## Build and run with Docker Compose

Build the runtime image:

```bash
docker compose build fitness-coach
```

Ingest or refresh the knowledge base. The first run downloads the embedding model and may take several minutes:

```bash
docker compose run --rm --entrypoint python fitness-coach -m app.rag.ingestion
```

Generate a plan:

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

The plan is written to `outputs/plano_de_treino_final.md` on the host. Compose persists Chroma data and Hugging Face model files in named volumes.

## Run locally without Docker

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env      # then add valid API keys
python -m app.rag.ingestion
python -m app.main --age 28 --weight-kg 70 --height-cm 170 \
  --gender female --frequency 4 --goal hipertrofia
```

The CLI requires both Groq and Tavily credentials and an ingested Chroma collection. Model and embedding downloads require network access.

## Run tests

Tests use doubles for model/tool boundaries and do not call Groq, Tavily, or download an embedding model.

```bash
docker build --target test -t ai-fitness-coach:test .
```

Or in a local environment with test dependencies installed:

```bash
python -m pip install -r requirements-test.txt
python -m pytest -q
```

## Notebooks

- `01_RAG_Preparacao.ipynb` documents the original RAG experiment.
- `02_Agente_Treinador_Fitness.ipynb` remains an experimental agent entry point and delegates shared runtime setup to `app/`.

The CLI is the reproducible application entry point; notebooks are for exploration.

## Known limitations

- Retrieval quality has not yet been measured on a labeled query set; top-k remains 3 and no similarity threshold is applied.
- Retrieved passages are not cited in the final generated plan.
- API retries, request-level cost tracking, and persistent agent traces are not implemented.
- Fitness and energy calculations are simplified heuristics and should not be used as clinical or dietary guidance.
- Existing Chroma records with legacy source metadata may remain alongside records created by the new ingestion routine.

## Future work

- Create a small reviewed retrieval evaluation set and measure retrieval quality before tuning chunking or top-k.
- Add structured output validation and safety checks for exercise recommendations.
- Add latency/token usage telemetry and evaluate response faithfulness against retrieved evidence.
- Pin and periodically update runtime dependency versions.
