# Model evaluations

## Labeled retrieval metrics

No labeled evaluation set is present in this repository, so no model score or baseline comparison has been measured. Run `make label` after ingesting data to create the requested hand-labeled set (target: approximately 200 sequences across 8 classes), then run `make train`. The harness writes measured leave-one-out recall@k, nDCG@k, and kNN accuracy to this file. Model superiority is not claimed until those results exist.

| Model | Recall@1 | Recall@5 | Recall@10 | nDCG@10 | kNN accuracy |
|---|---:|---:|---:|---:|---:|
| Transformer InfoNCE | Not measured | Not measured | Not measured | Not measured | Not measured |
| Event-token TF-IDF | Not measured | Not measured | Not measured | Not measured | Not measured |
| Seeded random vectors | Not measured | Not measured | Not measured | Not measured | Not measured |

Evaluation uses the same labeled sequences for leave-one-out neighbor ranking. TF-IDF uses event type, zone, and outcome tokens. The random baseline uses a fixed seed for repeatability. Run records include the training seed and hyperparameters; W&B is used when configured, otherwise MLflow is used when installed.

## ONNX latency

Not measured in this environment. `make export-onnx` exports the trained 256-dimensional encoder and reports CPU p50/p95 latency for a single sequence, including the token length in the output.

## HNSW index

Not measured in this environment. `make index` embeds database sequences, sweeps `m ∈ {8,16,32}` and `ef_search ∈ {20,50,100}`, then records recall@10 and p50/p95 latency against exact cosine neighbors. The best measured recall/latency operating point is persisted as the HNSW index settings and written here.

## Search retrieval ablation

The 100-query fixture is in [search_cases.jsonl](../services/api/evals/search_cases.jsonl). Each row includes the natural-language query, expected structured filters, and a `relevant_sequence_ids` field. The fixture currently has **0/100 relevance annotations** because sequence IDs must be judged against a specific ingested corpus; the IDs cannot be inferred safely before data is loaded. After ingesting and indexing a corpus, use `make annotate-search` to review candidate sequences and attach relevance judgments. The parse regression is runnable with `make promptfoo-search`; annotate the relevant ID arrays before interpreting retrieval recall. `make eval-search` measures the API parser and retrieval branches and writes raw per-query outputs to `services/api/evals/search_results.json`.

| Retrieval mode | Recall@10 | p50 latency (ms) | p95 latency (ms) | Cost/query (USD) |
|---|---:|---:|---:|---:|
| Vector only | Not measured | Not measured | Not measured | Not measured |
| FTS only | Not measured | Not measured | Not measured | Not measured |
| Hybrid | Not measured | Not measured | Not measured | Not measured |
| Hybrid + cross-encoder rerank | Not measured | Not measured | Not measured | Not measured |

The evaluation script updates this table with measured values. Latency includes LLM parsing and query embedding for each retrieval mode, and adds cross-encoder runtime for the final mode. Cost counts the configured LLM and embedding token prices; it excludes database, Redis, and compute costs. Defaults are based on the current [GPT-4o mini pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini) and [text-embedding-3-small pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small); set environment values to match the provider account and model if they differ.

The promptfoo regression config at [promptfooconfig.yaml](../services/api/evals/promptfooconfig.yaml) checks the six filter fields against expected parses for all 100 queries. Retrieval recall remains unscored until relevant sequence IDs are labeled.

## Scout dossier benchmark

The 50-question benchmark is stored in [scout_cases.jsonl](../services/api/evals/scout_cases.jsonl). Each row includes a gold SQL query over the ingested corpus; `make scout-benchmark` executes those SQL statements in a read-only transaction to populate ground-truth values and evidence IDs, then compares the multi-agent graph with a one-shot single-agent tool-bundle baseline. Scores below are unmeasured until a corpus, API key, and cross-encoder are configured.

| Approach | Accuracy | Groundedness rate | Hallucination rate | Steps (avg) | p50 latency (ms) | p95 latency (ms) | Cost/query (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|
| LangGraph multi-agent | Not measured | Not measured | Not measured | Not measured | Not measured | Not measured | Not measured |
| Single-agent baseline | Not measured | Not measured | Not measured | Not measured | Not measured | Not measured | Not measured |

Accuracy compares a verified dossier's numeric answer with the SQL-computed scalar. Groundedness is supported claims divided by submitted claims. Hallucination rate is unsupported claims dropped by the verifier divided by submitted claims. Latency includes all tool and model work; cost uses configured API token rates and excludes database and local inference costs. `make scout-benchmark` refreshes this table and writes per-case traces to `services/api/evals/scout_results.json`.

## Product UI checks

`make e2e` runs the two Playwright product flows: command search with filter editing, pitch selection and side-by-side comparison; and dossier claim replay with the trace panel. CI runs both flows against deterministic sample mode. `make eval-gate` verifies the 100-query search fixture, Promptfoo rows, and 50 SQL-grounded dossier questions without external credentials. If CI has `OPENAI_API_KEY`, it also runs the live Promptfoo parse regression.

| UI check | Result | Method |
|---|---:|---|
| Playwright core flows | 2/2 passed | Desktop Chromium, sample data, 22-player animation and correct club/league label assertions |
| Lighthouse performance | 100/100 | Desktop Chrome, production build, `/` sample mode |
| Lighthouse accessibility | 100/100 | Desktop Chrome, production build, `/` and `/dossier?team=Arsenal` |
| Mounted-player frame sample | 16.67 ms mean; 16.70 ms p95 | 201 players active in headless Chrome for 3 seconds, rAF callback intervals |
| Search cached-cold p95 | Not measured | Requires a live API key, indexed corpus, Redis, and cache workload |

The frame timing is a local browser sample, not a device-independent performance guarantee. The product E2E suite and fixture gate do not score retrieval relevance or provider response times.
