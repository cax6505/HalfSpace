from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import torch

from data import collate, load_jsonl
from model import SequenceEncoder


class OnnxWrapper(torch.nn.Module):
    def __init__(self, model): super().__init__(); self.model = model
    def forward(self, event, zone, outcome, delta, mask): return self.model(event, zone, outcome, delta, mask)


def main():
    base = Path(os.getenv("ARTIFACT_DIR", "ml/artifacts")); sequences = load_jsonl(Path(os.getenv("SEQUENCES", "ml/data/sequences.jsonl")))
    checkpoint = torch.load(base / "encoder.pt", map_location="cpu", weights_only=False)
    model = SequenceEncoder().eval(); model.load_state_dict(checkpoint["state_dict"])
    example = collate(sequences[:1]); names = ["event", "zone", "outcome", "delta", "mask"]
    torch.onnx.export(OnnxWrapper(model), example, str(base / "encoder.onnx"), input_names=names, output_names=["embedding"], dynamic_axes={n: {0: "batch", 1: "tokens"} for n in names}, opset_version=17, dynamo=False)
    import onnxruntime as ort
    session = ort.InferenceSession(str(base / "encoder.onnx"), providers=["CPUExecutionProvider"])
    feed = {inp.name: tensor.numpy() for inp, tensor in zip(session.get_inputs(), example)}
    for _ in range(10): session.run(None, feed)
    timings=[]
    for _ in range(100):
        start=time.perf_counter(); session.run(None, feed); timings.append((time.perf_counter()-start)*1000)
    print(f"ONNX CPU latency (batch=1, n_tokens={example[0].shape[1]}): p50={np.percentile(timings,50):.3f}ms p95={np.percentile(timings,95):.3f}ms")


if __name__ == "__main__": main()
