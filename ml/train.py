from __future__ import annotations

import json
import os
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from data import augment, collate, export_db, load_jsonl
from model import SequenceEncoder


def batch_forward(model, batch, device):
    event, zone, outcome, delta, mask = (x.to(device) for x in batch)
    return model(event, zone, outcome, delta, mask)


def train() -> None:
    seed = int(os.getenv("SEED", "17"))
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    source = Path(os.getenv("SEQUENCES", "ml/data/sequences.jsonl"))
    if not source.exists():
        export_db(source)
    sequences = load_jsonl(source)
    if len(sequences) < 2:
        raise SystemExit(f"Need at least 2 sequences to train; found {len(sequences)} in {source}")
    output = Path(os.getenv("ARTIFACT_DIR", "ml/artifacts")); output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SequenceEncoder().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(os.getenv("LR", "0.0003")), weight_decay=0.01)
    rng = random.Random(seed)
    epochs, batch_size, temperature = int(os.getenv("EPOCHS", "20")), int(os.getenv("BATCH_SIZE", "64")), float(os.getenv("TEMPERATURE", "0.1"))
    metrics = {}
    for epoch in range(epochs):
        rng.shuffle(sequences)
        model.train(); losses = []
        for offset in range(0, len(sequences), batch_size):
            anchor = sequences[offset:offset + batch_size]
            if len(anchor) < 2:
                continue
            view1 = [augment(s, rng) for s in anchor]
            view2 = [augment(s, rng) for s in anchor]
            z1 = batch_forward(model, collate(view1), device); z2 = batch_forward(model, collate(view2), device)
            z = torch.cat((z1, z2))
            logits = (z @ z.T) / temperature
            logits.fill_diagonal_(-torch.inf)
            count = len(anchor)
            target = torch.cat((torch.arange(count, 2 * count), torch.arange(count))).to(device)
            loss = F.cross_entropy(logits, target)
            optimizer.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); optimizer.step()
            losses.append(float(loss.detach().cpu()))
        metrics[f"epoch_{epoch + 1}_loss"] = float(np.mean(losses)) if losses else float("nan")
        print(f"epoch {epoch + 1}/{epochs} loss={metrics[f'epoch_{epoch + 1}_loss']:.5f}")
    model.eval()
    torch.save({"state_dict": model.state_dict(), "seed": seed, "dim": 256}, output / "encoder.pt")
    config = {"seed": seed, "epochs": epochs, "batch_size": batch_size, "temperature": temperature, "sequences": len(sequences), "embedding_dim": 256, "loss": metrics}
    (output / "run.json").write_text(json.dumps(config, indent=2))
    tracked = False
    if os.getenv("WANDB_PROJECT"):
        try:
            import wandb
            with wandb.init(project=os.environ["WANDB_PROJECT"], config=config) as run:
                run.log({"train/final_loss": metrics.get(f"epoch_{epochs}_loss")})
                run.save(str(output / "encoder.pt"))
            tracked = True
        except ImportError:
            print("wandb is unavailable; trying MLflow.")
    if not tracked:
        try:
            import mlflow
            mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns"))
            with mlflow.start_run():
                mlflow.log_params({k: v for k, v in config.items() if k != "loss"})
                mlflow.log_metrics({f"loss/{k}": v for k, v in metrics.items() if np.isfinite(v)})
                mlflow.log_artifact(str(output / "encoder.pt"))
            tracked = True
        except ImportError:
            print("Neither W&B nor MLflow is installed; run metadata is saved in run.json.")
    labels = Path(os.getenv("LABELS", "ml/data/labels.jsonl"))
    if labels.exists() and labels.stat().st_size:
        from evaluate import evaluate
        evaluate(model, sequences, labels, output)
    else:
        print(f"No labeled evaluation set at {labels}; run `make label` before publishing metrics.")


if __name__ == "__main__":
    train()
