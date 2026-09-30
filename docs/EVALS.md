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
