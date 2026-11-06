# Changelog

## Unreleased — Application modularization and container runtime

- **Created:** `app/config/settings.py`, `app/tools/calculations.py`, `app/agent/`, `app/rag/`, `app/tools/`, `app/runtime.py`, and `app/main.py` to separate configuration, deterministic calculations, graph logic, RAG, integrations, and execution.
- **Created:** `Dockerfile` with separate `test` and `runtime` targets, `compose.yaml` for persistent Chroma/model/output storage, `.dockerignore`, and `requirements-test.txt`.
- **Created:** pytest suites under `tests/` for calculations, settings, agent routing, CLI/prompt contracts, RAG contracts, and tool adapters.
- **Created:** `docs/architecture.md` and ADR records in `docs/decisions.md`.
- **Modified:** `02_Agente_Treinador_Fitness.ipynb` to delegate shared calculations and runtime setup to modules; notebook retained as an experiment and stale outputs cleared.
- **Modified:** `ferramentas_ai.py` to share calculation logic and use the standalone Hugging Face/Chroma integrations.
- **Modified:** `requirements.txt` to declare the runtime integration packages; pytest is isolated in `requirements-test.txt`.
- **Modified:** `.env.example` to document environment settings without real credentials; `.gitignore` and `.dockerignore` to keep secrets and generated artifacts out of version control/build context.
- **Modified:** README installation and usage instructions to cover the CLI, RAG ingestion, Docker Compose, tests, architecture, and current limitations.
- **Problems addressed:** duplicated calculation logic, notebook-only execution, missing profile/config validation, implicit RAG setup and IDs, unbounded tool cycles, unclear missing/empty knowledge-base errors, and lack of isolated dependency installation.
- **Container decision:** runtime installs CPU-only PyTorch rather than pulling CUDA libraries; the test image installs only pytest and application source/tests.
- **Integration compatibility finding:** the initial smoke test found a legacy `langchain.tools.retriever` import absent from the resolved LangChain release. The application now implements the retrieval tool explicitly with the supported core `@tool` decorator and uses standalone Chroma/Hugging Face integration packages.

### Validation performed

- `docker build --target test -t ai-fitness-coach:test -f Dockerfile .` — **30 passed** in the isolated test image.
- `docker compose -f compose.yaml config --quiet` — passed.
- Runtime image build — passed.
- Runtime import smoke check — passed for LangGraph, LangChain core/Groq, standalone Chroma/Hugging Face/text-splitter integrations, Tavily, runtime composition, and RAG tool modules.
- `python -m app.main --help` in the runtime image — passed and displayed the expected CLI arguments.
- No live Groq or Tavily call and no full plan generation was performed; these require valid user credentials and incur external service usage. The embedding model and RAG ingestion were not run as part of these checks.
