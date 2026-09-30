from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.neighbors import NearestNeighbors

from data import collate, load_jsonl
from model import SequenceEncoder


def text_view(row):
    return " ".join(f"{t.get('event_type','?')}@{t.get('zone',[0,0])[0]}:{t.get('zone',[0,0])[1]}:{t.get('outcome','none')}" for t in row["tokens"])


def recall_ndcg_knn(matrix: np.ndarray, labels: list[str], ks=(1, 5, 10)) -> dict[str, float]:
    sims = matrix @ matrix.T
    np.fill_diagonal(sims, -np.inf)
    order = np.argsort(-sims, axis=1)
    result = {}
    for k in ks:
        recalls, ndcgs = [], []
        for i, ranked in enumerate(order):
            relevant = np.array([labels[j] == labels[i] for j in ranked])
            total_relevant = sum(label == labels[i] for j, label in enumerate(labels) if j != i)
            hits = relevant[:k].sum()
            recalls.append(float(hits / max(1, total_relevant)))
            gains = relevant[:k].astype(float) / np.log2(np.arange(2, k + 2))
            ideal = np.sort(relevant.astype(float))[::-1][:k] / np.log2(np.arange(2, k + 2))
            ndcgs.append(float(gains.sum() / max(ideal.sum(), 1e-12)))
        result[f"recall@{k}"] = float(np.mean(recalls)); result[f"ndcg@{k}"] = float(np.mean(ndcgs))
    pred = [labels[ranked[0]] for ranked in order]
    result["knn_accuracy"] = float(accuracy_score(labels, pred))
    return result


def evaluate(model: SequenceEncoder, sequences: list[dict], labels_path: Path, output: Path) -> dict:
    labels_data = load_jsonl(labels_path)
    labeled = {str(row["id"]): str(row["label"]) for row in labels_data if row.get("label")}
    by_id = {str(row["id"]): row for row in sequences}
    missing = [key for key in labeled if key not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} labeled sequence IDs are missing from training inputs; re-export sequences")
    rows = [by_id[key] for key in labeled]
    y = list(labeled.values())
    classes = sorted(set(y))
    if len(y) < 200 or len(classes) < 8:
        raise ValueError(f"Evaluation needs ~200 labeled sequences across 8 classes; found {len(y)} across {len(classes)}")
    model.eval()
    vectors = []
    with torch.no_grad():
        for row in rows:
            batch = collate([row])
            vectors.append(model(*batch).cpu().numpy()[0])
    encoder = np.stack(vectors); rng = np.random.default_rng(17)
    tfidf = TfidfVectorizer(ngram_range=(1, 2), token_pattern=r"[^\s]+")
    sparse = tfidf.fit_transform([text_view(row) for row in rows]).toarray().astype(np.float32)
    norms = np.linalg.norm(sparse, axis=1, keepdims=True).clip(1e-12); sparse /= norms
    random_vectors = rng.normal(size=encoder.shape).astype(np.float32); random_vectors /= np.linalg.norm(random_vectors, axis=1, keepdims=True)
    all_metrics = {name: recall_ndcg_knn(matrix, y) for name, matrix in {"Transformer": encoder, "TF-IDF": sparse, "Random": random_vectors}.items()}
    output.mkdir(parents=True, exist_ok=True)
    (output / "eval.json").write_text(json.dumps({"n": len(y), "classes": classes, "metrics": all_metrics}, indent=2))
    rows_md = ["| Model | Recall@1 | Recall@5 | Recall@10 | nDCG@10 | kNN accuracy |", "|---|---:|---:|---:|---:|---:|"]
    for name, metrics in all_metrics.items():
        rows_md.append(f"| {name} | {metrics['recall@1']:.3f} | {metrics['recall@5']:.3f} | {metrics['recall@10']:.3f} | {metrics['ndcg@10']:.3f} | {metrics['knn_accuracy']:.3f} |")
    doc = Path("docs/EVALS.md")
    previous = doc.read_text() if doc.exists() else "# Model evaluations\n"
    section = "\n## Latest labeled retrieval evaluation\n\n" + f"Labeled sequences: **{len(y)}** across **{len(classes)} classes**. Leave-one-out same-class retrieval.\n\n" + "\n".join(rows_md) + "\n"
    marker = "\n## Latest labeled retrieval evaluation\n"
    previous = previous.split(marker)[0]
    doc.write_text(previous.rstrip() + "\n" + section)
    return all_metrics


if __name__ == "__main__":
    import os
    base = Path(os.getenv("ARTIFACT_DIR", "ml/artifacts"))
    checkpoint = torch.load(base / "encoder.pt", map_location="cpu", weights_only=False)
    encoder = SequenceEncoder(); encoder.load_state_dict(checkpoint["state_dict"])
    result = evaluate(encoder, load_jsonl(Path(os.getenv("SEQUENCES", "ml/data/sequences.jsonl"))), Path(os.getenv("LABELS", "ml/data/labels.jsonl")), base)
    print(json.dumps(result, indent=2))
