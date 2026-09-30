# Modeling workspace

# Sequence representation learning

The encoder maps each token's event type, 12×8 zone, outcome, and clipped/log-scaled time delta into a Transformer encoder and produces an L2-normalized 256-dimensional sequence embedding. Contrastive training uses InfoNCE with two independently augmented views per input and all other views in the minibatch as negatives. Augmentations mirror the x-axis, crop a small contiguous time window, jitter zones by one cell, and perturb time deltas.

## Workflow

1. `make label` opens a terminal labeling flow over DB sequences and writes `ml/data/labels.jsonl` (200 labels, at least 8 classes are expected for the requested evaluation).
2. `make train` reads sequence JSONL from `ml/data/sequences.jsonl`, or exports tokens from Postgres when that file is absent. It trains deterministically and evaluates `labels.jsonl` when available. Output goes under `ml/artifacts/`.
3. Evaluation compares leave-one-out retrieval recall@k, nDCG@k, and kNN accuracy for the encoder, word/character event-token TF-IDF, and a seeded random-vector baseline. `docs/EVALS.md` records measured results; the harness refuses to claim a win if an embedding baseline is worse.
4. The run is logged to W&B when `WANDB_PROJECT` is set, otherwise to a local MLflow tracking URI when MLflow is installed/configured. Metrics and config are also saved in the artifact directory.
5. The trained model is exported as ONNX and benchmarked on CPU. `make index` writes embeddings to Postgres and sweeps HNSW `m` and `ef_search`, measuring recall and query latency against exact neighbors.

Input JSONL shape: `{"id":"match:possession:phase","tokens":[{"event_type":"Pass","zone":[7,3],"outcome":"Complete","time_delta":1.2}]}`. Labeled JSONL adds `"label":"build-up"`. A blank file is not a substitute for the hand-labeled evaluation set: metrics are only published from real labels.

Install dependencies with `make ml-install`; run `make label`, `make train`, `make export-onnx`, and `make index`. Control repeatable training through `SEED`, `EPOCHS`, `BATCH_SIZE`, `LR`, and `TEMPERATURE`. Set `WANDB_PROJECT` to choose W&B; otherwise MLflow writes locally to `mlruns` when available. Training fails early if fewer than two sequences are available. Evaluation requires at least 200 labeled rows and eight classes and refuses to report results for missing IDs.
