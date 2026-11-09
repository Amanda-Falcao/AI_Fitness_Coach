# Changelog

## 2026-11-09 — Migração do modelo Groq descontinuado

- **Problema observado:** a geração real de plano recebeu HTTP 404 porque o padrão `llama-3.1-8b-instant` havia sido desativado pelo Groq em 16/08/2026.
- **Alterado:** padrão de `GROQ_MODEL_NAME` para `openai/gpt-oss-20b` em `app/config/settings.py` e `.env.example`, recomendado pelo Groq como substituto.
- **Teste:** coberta a seleção do modelo padrão em `tests/test_settings.py`.
- **Limitação de validação:** nenhuma nova chamada real à API foi feita nesta alteração. O próximo smoke test deve ser executado somente com a conta no Free Plan e dentro dos limites exibidos pelo Groq.
- **Resultados compartilhados pela usuária antes da migração:** 57 testes aprovados; ingestão de 5 chunks concluída; benchmark RAG com hit-rate@3 de 1.0, MRR de 0.9 e latência média observada de 9.66 ms em 5 consultas; CLI `--help` concluída. A geração foi a única etapa que falhou, com HTTP 404.

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
- **Created:** `app/rag/citations.py` to build trusted citation registries from internal RAG tool messages; the RAG adapter now returns stable content-derived IDs with source and evidence.
- **Modified:** the RAG tool to fail when a retrieved passage lacks source metadata, and the prompt to treat retrieved/web content as untrusted reference data rather than instructions.
- **Modified:** the structured plan contract to require per-exercise RAG references, validate reference membership, and render source paths and retrieved excerpts from trusted tool records.
- **Created:** `.github/workflows/ci.yml` for Python tests and notebook syntax checks, and `evaluation/plan_review_template.md` for manual plan-quality review.
- **Created:** `app/observability.py` for allowlisted JSON logs and token usage aggregation; CLI runs now report duration, selected model, session count, token counts if supplied, and safe error type without logging prompt/profile contents.
- **Modified:** GitHub Actions to use the current major releases of the official checkout and setup-python actions, verified against their upstream release pages.
- **Problems addressed:** duplicated calculation logic, notebook-only execution, missing profile/config validation, implicit RAG setup and IDs, unbounded tool cycles, unclear missing/empty knowledge-base errors, and lack of isolated dependency installation.
- **Output contract:** generated plans must contain exactly three ordered weeks, the requested sessions each week, bounded exercise fields, and explicit safety guidance. Validation is structural, not a medical-safety guarantee.
- **Citation contract:** each exercise must refer to an ID emitted by the RAG tool in that graph run; displayed source/evidence is resolved from the tool result, though semantic entailment is not checked.
- **Container decision:** runtime installs CPU-only PyTorch rather than pulling CUDA libraries; the test image installs only pytest and application source/tests.
- **Integration compatibility finding:** the initial smoke test found a legacy `langchain.tools.retriever` import absent from the resolved LangChain release. The application now implements the retrieval tool explicitly with the supported core `@tool` decorator and uses standalone Chroma/Hugging Face integration packages.

### Validation performed

- `docker build --target test -t ai-fitness-coach:test -f Dockerfile .` — **57 passed** in the isolated test image.
- `docker compose -f compose.yaml config --quiet` — passed.
- Runtime image build — passed.
- Runtime import smoke check — passed for LangGraph, LangChain core/Groq, standalone Chroma/Hugging Face/text-splitter integrations, Tavily, runtime composition, and RAG tool modules.
- LangGraph compiled terminal-path and full model→tool→model cycle smoke tests with fake model/tool — passed without external service calls.
- Docker Compose ingestion — passed; current knowledge source produced **5 chunks**.
- Real retrieval benchmark over the Compose Chroma volume — **hit-rate@3 1.00**, **MRR 0.90**, **mean invocation latency 7.89 ms**, 5 queries. Model initialization is excluded from the timed calls; this is a tiny local prototype set, not a general quality claim.
- `python -m app.main --help` in the runtime image — passed and displayed the expected CLI arguments.
- Updated notebook JSON and execution cell syntax validation — passed.
- Invalid plan output test — confirmed the CLI does not create the destination file when the output contract fails.
- CI commands (pytest and notebook JSON/code syntax) were exercised locally in the container-equivalent environment; the hosted GitHub Actions run has not occurred from this workspace.
- Real LangChain `@tool` + LangGraph tool-cycle smoke with a fake retriever/model — passed; citation IDs resolved to the returned source/evidence and rendered into Markdown.
- No live Groq or Tavily call and no full plan generation was performed; these require valid user credentials and incur external service usage. Embedding model download, ingestion, and retrieval evaluation were run in the Compose container.
