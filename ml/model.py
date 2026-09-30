from __future__ import annotations

import hashlib
import math
from typing import Any

import torch
from torch import nn


def bucket(value: str, size: int) -> int:
    return int(hashlib.blake2b(value.encode(), digest_size=8).hexdigest(), 16) % size + 1


def encode_tokens(tokens: list[dict[str, Any]], max_len: int = 128) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    tokens = tokens[:max_len]
    event = [bucket(str(t.get("event_type", "Unknown")), 512) for t in tokens]
    outcome = [bucket(str(t.get("outcome", "none")), 128) for t in tokens]
    zone = []
    delta = []
    for token in tokens:
        xy = token.get("zone", [0, 0])
        x = min(11, max(0, int(xy[0])))
        y = min(7, max(0, int(xy[1])))
        zone.append(y * 12 + x + 1)
        delta.append(math.log1p(max(0.0, min(60.0, float(token.get("time_delta", 0))))) / math.log(61))
    if not event:
        event, outcome, zone, delta = [0], [0], [0], [0.0]
    return (torch.tensor(event), torch.tensor(zone), torch.tensor(outcome), torch.tensor(delta, dtype=torch.float32))


class SequenceEncoder(nn.Module):
    def __init__(self, dim: int = 256, max_len: int = 128, layers: int = 4, heads: int = 8):
        super().__init__()
        self.event = nn.Embedding(513, dim, padding_idx=0)
        self.zone = nn.Embedding(97, dim, padding_idx=0)
        self.outcome = nn.Embedding(129, dim, padding_idx=0)
        self.time = nn.Linear(1, dim)
        self.position = nn.Embedding(max_len, dim)
        layer = nn.TransformerEncoderLayer(dim, heads, dim * 4, dropout=0.1, batch_first=True, norm_first=True)
        self.transformer = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(dim)

    def forward(self, event: torch.Tensor, zone: torch.Tensor, outcome: torch.Tensor, delta: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        positions = torch.arange(event.shape[1], device=event.device).unsqueeze(0)
        x = self.event(event) + self.zone(zone) + self.outcome(outcome) + self.time(delta.unsqueeze(-1)) + self.position(positions)
        x = self.transformer(x, src_key_padding_mask=~mask)
        pooled = (x * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp(min=1)
        return nn.functional.normalize(self.norm(pooled), dim=-1)
