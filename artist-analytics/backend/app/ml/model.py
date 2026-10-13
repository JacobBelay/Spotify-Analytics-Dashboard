"""PyTorch forecaster conditioned on "circumstances" (events).

A GRU reads the last 56 days (values + which events were active). An MLP then
combines that summary with the *planned* events for the next 56 days and the
weekday pattern, and predicts a mean and a spread for each future day.

Because the planned events are an input, the same trained model answers
"what happens if we drop a single on the 3rd and land a playlist on the 10th?"
— you just change the future-events input and compare against the baseline.
"""

from __future__ import annotations

import torch
from torch import nn

from .features import H, K, L, S


class ScenarioForecaster(nn.Module):
    def __init__(self, hidden: int = 64):
        super().__init__()
        self.encoder = nn.GRU(input_size=1 + K, hidden_size=hidden, num_layers=2, batch_first=True, dropout=0.1)
        self.future_proj = nn.Sequential(nn.Flatten(), nn.Linear(H * (K + 7), 128), nn.GELU())
        self.head = nn.Sequential(
            nn.Linear(hidden + 128 + S, 256),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(256, 2 * H),
        )

    def forward(self, past: torch.Tensor, future: torch.Tensor, static: torch.Tensor):
        _, h = self.encoder(past)                  # h: [layers, B, hidden]
        z = torch.cat([h[-1], self.future_proj(future), static], dim=-1)
        out = self.head(z)
        mean, log_var = out[:, :H], out[:, H:].clamp(-8, 4)
        return mean, log_var


def masked_gaussian_nll(mean, log_var, target, mask):
    nll = 0.5 * (log_var + (target - mean) ** 2 / log_var.exp())
    return (nll * mask).sum() / mask.sum().clamp(min=1)


CONFIG = {"L": L, "H": H, "K": K, "S": S, "hidden": 64}
