# Architecture Decision Records

## ADR-001 — Extract deterministic calculations and validate their inputs

- **Status:** Accepted
- **Context:** The fitness calculations were implemented separately in `ferramentas_ai.py` and the agent notebook. They used different assumptions, omitted input validation, and returned unstructured text.
- **Decision:** Put the calculations in `app/tools/calculations.py` as pure functions, validate the profile before computing, and expose a small immutable result object. The agent notebook delegates to this shared implementation.
- **Alternatives considered:** Keep calculations in the notebook; use a Pydantic model for validation; remove calorie estimates until a more evidence-based model exists.
- **Technical rationale:** A pure function is easy to test without loading an LLM or calling an external API. Standard-library validation avoids adding a runtime dependency for this small contract.
- **Expected benefits:** One source of truth, explicit failures for invalid profile data, repeatable unit tests, and clearer separation between calculation and agent orchestration.
- **Trade-offs and limitations:** Activity multipliers and the ±400 kcal goal adjustment are retained as rough prototype heuristics for continuity. They are not individualized nutrition advice and need evidence review before being presented as recommendations. The current equation supports only `male` and `female` constants.

## ADR-002 — Read integration settings explicitly from the environment

- **Status:** Accepted
- **Context:** API client initialization was mixed into tool modules and could fail silently when a key was missing. Different integrations do not need to be mandatory in every execution path.
- **Decision:** Add an immutable `Settings` object with explicit `from_env` validation and per-integration required flags. Importing the module does not instantiate clients or read secrets.
- **Alternatives considered:** Instantiate service clients at module import; require every API key for all use cases; add a settings framework.
- **Technical rationale:** Explicit construction makes configuration failures predictable and lets local calculations run without external credentials. The standard library is sufficient for the current settings surface.
- **Expected benefits:** Clear missing-key errors, no import-time network/client side effects, and easier dependency injection in later stages.
- **Trade-offs and limitations:** `from_env` reads process environment variables only. Loading a `.env` file remains the responsibility of the application entry point and will be addressed when that entry point is implemented.

## ADR-003 — Separate RAG ingestion from retrieval and use stable chunk identifiers

- **Status:** Accepted
- **Context:** Ingestion lived only in a notebook, the agent duplicated retriever setup, chunk IDs were generated implicitly, and the database contained 10 vectors while the recorded ingestion output showed 5 chunks.
- **Decision:** Move loading/chunking/upserting to `app/rag/ingestion.py`, embedding construction to `app/rag/embeddings.py`, and validated query setup to `app/rag/retriever.py`. Keep chunk size 1000, overlap 200, the existing Hugging Face model, the existing Chroma collection, and top-k 3 in the agent. Derive IDs from normalized source, chunk position, and text; upsert first and remove stale IDs for that source only after the upsert succeeds.
- **Alternatives considered:** Rebuild the full collection on every ingestion; preserve implicit Chroma IDs; add a separate vector database or retrieval framework.
- **Technical rationale:** Stable IDs make repeated ingestion idempotent for unchanged chunks. Updating before deleting stale chunks reduces the chance of losing the previous source if embedding/upsert fails. Isolating retrieval allows the agent to fail with an actionable error when the knowledge base is unavailable.
- **Expected benefits:** Reproducible ingestion, fewer duplicate vectors, consistent top-k configuration, independent testing, and clearer separation between offline preparation and online query.
- **Trade-offs and limitations:** This does not deduplicate historical chunks whose stored `source` metadata differs from the normalized repository-relative path. Similarity thresholds and metadata filters remain unevaluated; existing retrieval parameters are preserved until the baseline benchmark is run and reviewed.

## ADR-004 — Build the LangGraph workflow from injected dependencies

- **Status:** Accepted
- **Context:** State, model invocation, routing, graph assembly, and a second LLM instance were all defined in the agent notebook. The graph had no explicit recursion limit and its core routing could not be tested without running notebook setup.
- **Decision:** Move state to `app/agent/state.py`, model and routing nodes to `app/agent/nodes.py`, and graph assembly to `app/agent/graph.py`. Inject the model and tools when building the graph. Keep the existing model/tool loop and set a 12-step recursion limit at execution.
- **Alternatives considered:** Replace the agent with a linear chain; add more planning/validation nodes immediately; keep the entire graph in the notebook.
- **Technical rationale:** Dependency injection keeps API clients and model creation at the composition boundary, while pure routing behavior can be tested with lightweight doubles. The existing loop already expresses the required tool cycle, so additional nodes should follow an observed need.
- **Expected benefits:** Easier explanation and testing of LangGraph state/transitions, one model configuration, and bounded tool-loop execution.
- **Trade-offs and limitations:** The graph factory still requires LangGraph at runtime. The recursion limit is a safety ceiling, not proof that a generated plan is correct; LLM/API failures are not retried or persisted yet.

## ADR-005 — Add a command-line composition root for application execution

- **Status:** Accepted
- **Context:** Running the agent required executing notebook cells in the right order. Tool creation, model setup, profile input, graph invocation, and output writing were coupled to the notebook.
- **Decision:** Add `app/main.py` as a CLI, `app/runtime.py` as the composition root, prompt construction as a pure module, and lazy factories for calculation, RAG, and Tavily tools. Keep the notebook as an experimental caller of the shared runtime.
- **Alternatives considered:** Add a web API; keep notebooks as the only interface; initialize model and tool clients at module import.
- **Technical rationale:** A CLI makes the prototype runnable in scripts and containers without adding a web framework. Lazy factories make local modules importable without credentials or all optional AI packages.
- **Expected benefits:** Reproducible non-notebook execution, validated profile input, explicit configuration checks, and a testable graph invocation boundary.
- **Trade-offs and limitations:** The CLI requires both Groq and Tavily credentials and an ingested Chroma collection. There is no HTTP API, interactive chat, retry policy, or persistent conversation store.

## ADR-006 — Package runtime and test environments in separate container targets

- **Status:** Accepted
- **Context:** The host Python lacks pip/venv, so the automated tests could not run there. The application also depends on a larger AI stack and model cache that should not be confused with test dependencies.
- **Decision:** Add a Docker runtime target with the declared application dependencies and a separate test target with pytest plus the isolated source/tests. Install the official CPU PyTorch wheel because this project does not require GPU inference. Use Compose volumes for Chroma and Hugging Face cache, and a bind mount for generated plans. Exclude `.env`, the checked-in local vector index, notebooks, and docs from the runtime build context.
- **Alternatives considered:** Install system Python packages; create a single image containing runtime and test-only dependencies; use a hosted vector database or model service.
- **Technical rationale:** Container targets provide a repeatable place to install dependencies without modifying the host Python. Separating the test target keeps the lightweight deterministic suite independent of model packages.
- **Expected benefits:** Reproducible dependency setup, a path to run pytest and the CLI in an isolated environment, and avoidance of CUDA libraries in the CPU runtime image.
- **Trade-offs and limitations:** The runtime image includes Sentence Transformers and Chroma, which make it substantially larger than the test image. Model weights are downloaded at runtime and cached in a volume. The image build was smoke-tested, but a full plan generation still requires API credentials and was not run.

## ADR-007 — Use standalone LangChain integrations for Hugging Face and Chroma

- **Status:** Accepted
- **Context:** The first runtime smoke test showed LangChain 1.x and a deprecation warning that `langchain-community` is being sunset. Chroma and Hugging Face now have dedicated integration packages, and the project only needs basic UTF-8 text loading.
- **Decision:** Replace community imports for embeddings and Chroma with `langchain-huggingface` and `langchain-chroma`. Read the source text with the standard library and construct a LangChain `Document`; depend directly on `langchain-text-splitters`. Implement the retriever tool with `langchain-core`'s `@tool` around the retriever instead of relying on a legacy helper module.
- **Alternatives considered:** Keep deprecated imports and pin older LangChain versions; rely on `langchain-community`; use Chroma or Hugging Face APIs without their LangChain adapters.
- **Technical rationale:** Standalone integrations match the packages recommended by current LangChain documentation and keep document loading simple. The core tool decorator is sufficient for this single retrieval function.
- **Expected benefits:** Remove the observed community deprecation warning, reduce coupling to legacy helper paths, and make the RAG tool's behavior explicit, including empty retrieval handling.
- **Trade-offs and limitations:** The exact dependency versions are still unpinned. The integration packages remain part of the runtime's model/vector stack and are not included in the lightweight test target.

## ADR-008 — Test tool adapters with injected boundaries and offline doubles

- **Status:** Accepted
- **Context:** The calculations and graph routing had unit coverage, but the LangChain adapters for calculation, RAG, and Tavily were not directly exercised. Tests must not depend on network credentials or real API calls.
- **Decision:** Add adapter contract tests that replace the LangChain decorator and external Tavily client with small test doubles. Exercise input validation, result formatting, empty RAG results, and safe wrapping of Tavily failures.
- **Alternatives considered:** Make live API calls in the test suite; add a mocking framework; test only the underlying calculation and retriever modules.
- **Technical rationale:** The Python standard library can supply the module doubles needed for these narrow boundaries, and pytest is already the only test dependency. This keeps the suite fast and deterministic while testing the behavior the agent actually calls.
- **Expected benefits:** Tool adapter regressions are detected without spending API quota or requiring secrets, and upstream error details are not surfaced in user-facing messages.
- **Trade-offs and limitations:** The decorator and SDK are represented by test doubles, so these tests do not guarantee compatibility with every future LangChain or Tavily release. Runtime container import smoke checks cover package availability but do not exercise live services.

## ADR-009 — Add a small deterministic retrieval benchmark before tuning RAG

- **Status:** Accepted
- **Context:** The RAG configuration preserved prototype chunking and top-k values, but there was no repeatable way to observe whether known evidence appeared in retrieved results. Adding an LLM-as-judge framework would add cost and subjective behavior before a baseline exists.
- **Decision:** Add five reviewed query/evidence pairs and a dependency-free runner reporting hit-rate@k, MRR, and per-query mean retrieval latency. Keep semantic answer-quality evaluation as a separate qualitative activity.
- **Alternatives considered:** Tune chunk size/top-k from intuition; add a hosted or LLM-based evaluation framework immediately; compare only generated answers manually with no recorded metric.
- **Technical rationale:** Exact evidence occurrence is deterministic, inexpensive, and useful as a regression check for this compact corpus. MRR accounts for rank while hit rate shows whether a target is present in the top-k.
- **Expected benefits:** Establish a repeatable retrieval baseline, enable evidence-based changes later, and teach the distinction between deterministic retrieval metrics and qualitative generation quality.
- **Trade-offs and limitations:** Five cases are too few for broad quality claims. Exact string matching can miss semantically equivalent passages and does not evaluate answer grounding, safety, or plan usefulness. Latency varies with hardware and warm/cold model state.

## ADR-010 — Validate a strict structured plan contract before saving

- **Status:** Accepted
- **Context:** The agent returned unrestricted Markdown, so the CLI could save an empty, incomplete, or unexpectedly shaped plan without checking the requested session count or the presence of safety guidance.
- **Decision:** Prompt the agent for one JSON object with a fixed schema. Validate its exact fields, three ordered weeks, per-week session count, unique day numbers, bounded exercise parameters, and required safety fields using the standard library. Render validated data to Markdown in application code and refuse to write invalid output.
- **Alternatives considered:** Keep free-form Markdown and rely only on prompt wording; add a schema-validation dependency; use provider-native structured output, which would introduce provider/model-specific behavior and potentially affect tool calling.
- **Technical rationale:** JSON parsing and explicit checks are deterministic, dependency-free, easy to test, and keep presentation separate from model generation. Failing closed prevents malformed plans from being mistaken for successful files.
- **Expected benefits:** Predictable output shape, exact session-count enforcement, stable Markdown formatting, and required safety disclaimer/stop/referral fields.
- **Trade-offs and limitations:** The model may fail the contract, in which case the CLI stops without saving; no automatic repair call is made to avoid hidden extra cost and latency. Structural safety fields do not establish factual or medical safety, and content still requires human review.

## ADR-011 — Bind exercise citations to actual RAG tool results

- **Status:** Accepted
- **Context:** Structured plans required evidence fields, but free-form citations could still name nonexistent sources or fabricate source metadata.
- **Decision:** The RAG tool returns JSON records with deterministic `KB-...` IDs, source paths, and retrieved text. Each exercise must select one to three IDs. The application builds a citation registry only from internal RAG tool messages, rejects unknown IDs, and renders source/excerpts from that registry rather than trusting model-supplied metadata.
- **Alternatives considered:** Ask the LLM to write source names directly; attach every retrieved chunk to the final plan; add a citation management framework.
- **Technical rationale:** Stable IDs provide traceability with no new dependency, and membership validation prevents fabricated references from being displayed as retrieved evidence.
- **Expected benefits:** Reviewers can trace each exercise to an actual passage returned during the run; invalid or invented citation IDs fail output validation.
- **Trade-offs and limitations:** Membership proves provenance, not entailment. A model may cite a real passage that does not support a claim. Chunk text is a weak citation boundary and citations are not linked to source line numbers. Prompt text marks retrieved/web content as untrusted reference data, but this does not replace a full prompt-injection defense.

## ADR-012 — Run deterministic checks in GitHub Actions

- **Status:** Accepted
- **Context:** Tests had only been run manually in a Docker test target, so later changes could regress without a consistent repository check.
- **Decision:** Add a GitHub Actions workflow for pushes and pull requests that installs only `requirements-test.txt`, runs pytest on Python 3.12, and parses notebook JSON and Python code cells.
- **Alternatives considered:** Build the full runtime image on every pull request; add a CI framework or linter dependency; rely on local Docker commands.
- **Technical rationale:** The current tests are pure Python and offline, so CI stays fast and does not need secrets, model downloads, or API calls.
- **Expected benefits:** Automated regression checks with no external-service cost and early detection of notebook syntax errors.
- **Trade-offs and limitations:** The workflow has not run on GitHub from this workspace. It does not build the full dependency-heavy runtime image or perform live integration checks.

## ADR-013 — Emit allowlisted JSON operational logs and provider token usage

- **Status:** Accepted
- **Context:** Generation had no consistent timing or usage telemetry, but logging prompts, profiles, retrieved evidence, or credentials would create avoidable privacy and secret exposure.
- **Decision:** Use standard-library JSON logs with an allowlist of event, elapsed time, session count, configured model name, output path, error type, and provider token counts when available. Do not estimate cost without an explicit pricing source/configuration.
- **Alternatives considered:** Add an observability SDK; log full inputs/outputs for debugging; estimate price from hardcoded provider rates.
- **Technical rationale:** Minimal structured logs are machine-readable and sufficient to observe local latency and token metadata without introducing a dependency or retaining user content.
- **Expected benefits:** Comparable run timing, optional token visibility, and logs that omit request/profile/evidence content by construction.
- **Trade-offs and limitations:** Provider metadata may be absent; tokens are not currency cost. Logs are local stdout only, with no aggregation, trace IDs, or dashboards. Retries remain intentionally unconfigured to avoid duplicating potentially billable calls without an explicit policy.
