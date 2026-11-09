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
- **Created:** `app/rag/evaluation.py` and `evaluation/retrieval_cases.json` with deterministic evidence hit-rate, MRR, and retrieval latency measurement.
- **Created:** `docs/evaluation.md` with the protocol, limits, and the observed real-embedding baseline (hit-rate@3 1.00, MRR 0.90, mean invocation latency 7.89 ms for five queries).
- **Modified:** CLI profile validation to reject zero training days for a plan that must contain sessions; the underlying calculation contract still accepts zero days for sedentary energy estimates.
- **Modified:** RAG contract tests to cover idempotent upsert behavior, stale chunk cleanup, old-index preservation on failed upsert, empty/missing collections, and retrieval evaluation metrics.
- **Created:** `app/agent/plan_output.py` for strict JSON contract validation and deterministic Markdown rendering, plus `tests/test_plan_output.py` for schema, completeness, bounds, and safety-field checks.
- **Modified:** `app/agent/prompts.py` to require the structured Portuguese plan and conservative safety guidance; `app/main.py` to reject invalid content before writing output.
- **Modified:** `02_Agente_Treinador_Fitness.ipynb` to use the shared prompt, validation, and Markdown renderer instead of its separate prompt and unvalidated output path.
- **Problems addressed:** duplicated calculation logic, notebook-only execution, missing profile/config validation, implicit RAG setup and IDs, unbounded tool cycles, unclear missing/empty knowledge-base errors, and lack of isolated dependency installation.
- **Output contract:** generated plans must contain exactly three ordered weeks, the requested sessions each week, bounded exercise fields, and explicit safety guidance. Validation is structural, not a medical-safety guarantee.
- **Container decision:** runtime installs CPU-only PyTorch rather than pulling CUDA libraries; the test image installs only pytest and application source/tests.
- **Integration compatibility finding:** the initial smoke test found a legacy `langchain.tools.retriever` import absent from the resolved LangChain release. The application now implements the retrieval tool explicitly with the supported core `@tool` decorator and uses standalone Chroma/Hugging Face integration packages.

### Validation performed

- `docker build --target test -t ai-fitness-coach:test -f Dockerfile .` — **48 passed** in the isolated test image.
- `docker compose -f compose.yaml config --quiet` — passed.
- Runtime image build — passed.
- Runtime import smoke check — passed for LangGraph, LangChain core/Groq, standalone Chroma/Hugging Face/text-splitter integrations, Tavily, runtime composition, and RAG tool modules.
- LangGraph compiled terminal-path and full model→tool→model cycle smoke tests with fake model/tool — passed without external service calls.
- Docker Compose ingestion — passed; current knowledge source produced **5 chunks**.
- Real retrieval benchmark over the Compose Chroma volume — **hit-rate@3 1.00**, **MRR 0.90**, **mean invocation latency 7.89 ms**, 5 queries. Model initialization is excluded from the timed calls; this is a tiny local prototype set, not a general quality claim.
- `python -m app.main --help` in the runtime image — passed and displayed the expected CLI arguments.
- Updated notebook JSON and execution cell syntax validation — passed.
- Invalid plan output test — confirmed the CLI does not create the destination file when the output contract fails.
- No live Groq or Tavily call and no full plan generation was performed; these require valid user credentials and incur external service usage. Embedding model download, ingestion, and retrieval evaluation were run in the Compose container.
