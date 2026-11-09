# Changelog

## 2026-11-09 — Migração do modelo Groq descontinuado

- **Problema observado:** a geração real de plano recebeu HTTP 404 porque o padrão `llama-3.1-8b-instant` havia sido desativado pelo Groq em 16/08/2026.
- **Alterado:** padrão de `GROQ_MODEL_NAME` para `openai/gpt-oss-20b` em `app/config/settings.py` e `.env.example`, recomendado pelo Groq como substituto.
- **Teste:** coberta a seleção do modelo padrão em `tests/test_settings.py`.
- **Limitação de validação:** nenhuma nova chamada real à API foi feita nesta alteração. O próximo smoke test deve ser executado somente com a conta no Free Plan e dentro dos limites exibidos pelo Groq.
- **Resultados compartilhados pela usuária antes da migração:** 57 testes aprovados; ingestão de 5 chunks concluída; benchmark RAG com hit-rate@3 de 1.0, MRR de 0.9 e latência média observada de 9.66 ms em 5 consultas; CLI `--help` concluída. A geração foi a única etapa que falhou, com HTTP 404.

## 2026-11-09 — Ajuste de chamadas GPT-OSS e limite de taxa

- **Problema observado:** na geração real, o Groq respondeu com sucesso a várias chamadas, retornou HTTP 429 em outra chamada e o SDK repetiu a solicitação automaticamente após 31 segundos. A execução terminou sem conteúdo JSON válido e não salvou o plano.
- **Alterado:** configurar GPT-OSS com `reasoning_effort="low"`, omitir o campo de raciocínio separado da resposta e definir `max_retries=0` para que erros de limite não iniciem chamadas repetidas ocultas.
- **Teste criado:** verificar a configuração do modelo com um cliente simulado, sem acesso a rede ou chaves válidas.
- **Limitação:** o log compartilhado não contém metadados de término/resposta suficientes para determinar por que o conteúdo final veio vazio. A nova configuração reduz esforço de raciocínio e chamadas repetidas automáticas, mas a próxima execução gratuita ainda precisa confirmar a resposta final do modelo.
- **Segurança de saída:** a validação existente recusou corretamente o conteúdo inválido e nenhum plano incompleto foi salvo.

## 2026-11-09 — Redução de uso do plano gratuito

- **Evidência:** o painel da usuária mostrou 7 requisições e 23.9K tokens (19.2K de entrada, 4.7K de saída); o limite visível para `openai/gpt-oss-20b` era 8K tokens por minuto. O excesso de TPM, não o total de requisições diárias, é compatível com o `429` observado.
- **Alterado:** calcular métricas do perfil localmente antes de chamar o agente; a ferramenta de cálculo deixa de consumir um ciclo do LLM.
- **Alterado:** Tavily passa a ser opcional pela flag `--web-search`; sem ela, o runtime não exige a chave nem cria/chama a integração.
- **Alterado:** reduzir o prompt removendo o exemplo JSON expandido para cada sessão; solicitar exatamente três exercícios por sessão e validar esse limite; reduzir o recursion limit padrão para quatro etapas.
- **Testes adicionados/ajustados:** cobrem as métricas no perfil, prompt compacto, limite de exercícios, uso opcional do Tavily, configuração do runtime e mensagem específica para `429`.
- **Validação executada:** imagem pytest recompilada — **61 testes aprovados**; imagem runtime recompilada; `--help` mostra a opção `--web-search`; construção local do cliente LangChain/Groq com as opções reduzidas passou sem fazer chamada externa.
- **Limitação:** alterações de tokens precisam ser medidas no próximo uso real. Um plano de quatro dias por semana ainda pode exceder TPM/TPD dependendo dos limites atuais e do tamanho real do contexto/saída. Nenhuma geração externa foi feita durante esta mudança.

## 2026-11-09 — Structured Outputs na etapa final do agente

- **Problema observado:** duas execuções receberam HTTP 200 do Groq, mas a resposta terminou dentro de uma string JSON e foi recusada pelo validador; nenhum plano foi gravado por essas tentativas.
- **Resultado da nova tentativa:** JSON Mode produziu JSON válido, mas faltaram `coach_analysis` e `safety`; novamente nenhum arquivo foi salvo.
- **Diagnóstico:** o plano com 12 sessões ultrapassou a conclusão padrão documentada de 1024 tokens, e arrays sem tamanho fixo permitiam respostas com menos semanas/sessões. Um schema aninhado também foi recusado pelo endpoint.
- **Alterado:** o modelo com ferramentas continua responsável por chamar o RAG; após o retorno, uma instância sem ferramentas usa Structured Outputs com JSON Schema estrito e `max_completion_tokens=4096`. Cada sessão é obrigatória em uma chave plana numerada, seus três exercícios também são campos obrigatórios e a resposta é normalizada para listas antes da validação existente.
- **Testes adicionados:** cobrem os campos obrigatórios do schema estrito, sua configuração no cliente e a seleção do modelo final depois do RAG, sem chamadas externas.
- **Validação:** container runtime reconstruído; configuração do cliente verificada localmente; **64 testes passaram**. Geração real concluída com duas chamadas Groq HTTP 200, 12 sessões, duração de 4.22 s, 5,785 tokens de entrada e 2,408 de saída. Plano salvo em `outputs/plano_de_treino_final.md`; nenhum Tavily foi chamado.

## 2026-11-09 — Remoção de artefatos e código legado

- **Removido:** o plano duplicado na raiz, o notebook de instalação, o notebook RAG antigo com integrações legadas, `ferramentas_ai.py`, a ferramenta de cálculo que não participa do runtime, e o banco Chroma binário versionado.
- **Mantido:** `02_Agente_Treinador_Fitness.ipynb` para experimentação; `dados/conhecimento_fitness.txt` como fonte versionada que recria o índice; o plano atual em `outputs/`.
- **Atualizado:** README e arquitetura para descrever a geração com schema estrito, ingestão reproduzível e apenas o notebook mantido. O teste isolado da ferramenta de cálculo obsoleta também foi removido.
- **Validação:** `docker build --target test -t ai-fitness-coach:test .` — **63 testes passaram**; JSON e células Python do notebook mantido válidos; `git diff --check` sem problemas.

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

## 2026-11-09 — Improve generated-plan progression, split, and evidence use

- **Modified:** `app/agent/prompts.py` to require a conditional three-week progression, the Upper A/Lower A/Upper B/Lower B order for four-day plans, and exercise-specific evidence/cues where retrieved.
- **Modified:** `app/agent/plan_output.py` to add required per-week progression fields, render them in Markdown, validate the four-day split, and prefer a returned reference that names a planned exercise.
- **Modified:** `dados/conhecimento_fitness.txt` to clarify the progression rule, scope citations, and replace rigid or vague execution claims with concise cues; no new external evidence claims were added.
- **Modified:** tests for progression fields, the four-day split, and preference for a returned exercise-specific citation.
- **Modified:** README, architecture documentation, and ADR-016 to describe the updated contract and its lexical validation limits.
- **API behavior:** No extra model call or new runtime dependency was added.
- **Re-ingestion:** The source text changed, so run the existing RAG ingestion command before the next plan generation to refresh the Chroma chunks.
