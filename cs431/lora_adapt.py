"""Direction B: Parameter-efficient Exposure-Consistency LoRA for Depth Anything 3."""

from __future__ import annotations

import math
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


class LoRALinear(nn.Module):
    """Drop-in LoRA wrapper around nn.Linear with fast toggle for teacher/student mode."""

    def __init__(self, base: nn.Linear, rank: int = 4, alpha: float = 8.0):
        super().__init__()
        self.base = base
        self.rank = rank
        self.scale = alpha / rank
        self.enabled = True
        for p in self.base.parameters():
            p.requires_grad_(False)
        device = base.weight.device
        dtype = base.weight.dtype
        self.lora_a = nn.Parameter(torch.empty(rank, base.in_features, device=device, dtype=dtype))
        self.lora_b = nn.Parameter(torch.zeros(base.out_features, rank, device=device, dtype=dtype))
        nn.init.kaiming_uniform_(self.lora_a, a=math.sqrt(5))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.base(x)
        if self.enabled:
            a = self.lora_a.to(dtype=x.dtype)
            b = self.lora_b.to(dtype=x.dtype)
            delta = F.linear(F.linear(x, a), b)
            out = out + self.scale * delta
        return out


def attach_lora_to_da3(
    model, rank: int = 4, alpha: float = 8.0, start_block: int = 6
) -> list[nn.Parameter]:
    """Freeze all DA3 parameters and attach LoRA to qkv/proj of the last transformer blocks."""
    for p in model.parameters():
        p.requires_grad_(False)

    vit = model.model.backbone.pretrained
    trainable = []
    for idx in range(start_block, len(vit.blocks)):
        attn = vit.blocks[idx].attn
        for attr in ("qkv", "proj"):
            layer = getattr(attn, attr)
            if isinstance(layer, nn.Linear):
                wrapped = LoRALinear(layer, rank=rank, alpha=alpha)
                setattr(attn, attr, wrapped)
                trainable.extend([wrapped.lora_a, wrapped.lora_b])
    return trainable


def set_lora_enabled(model, enabled: bool) -> None:
    for mod in model.modules():
        if isinstance(mod, LoRALinear):
            mod.enabled = enabled


def save_lora_weights(model, path: Path) -> None:
    state = {
        name: param.detach().cpu()
        for name, param in model.named_parameters()
        if "lora_a" in name or "lora_b" in name
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, path)


def load_lora_weights(model, path: Path) -> None:
    state = torch.load(path, map_location="cpu")
    own = dict(model.named_parameters())
    for name, tensor in state.items():
        if name in own:
            own[name].data.copy_(tensor.to(own[name].device, own[name].dtype))


def _grad_loss(log_s: torch.Tensor, log_t: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    dx_s = log_s[..., :, 1:] - log_s[..., :, :-1]
    dx_t = log_t[..., :, 1:] - log_t[..., :, :-1]
    wx = weight[..., :, 1:] * weight[..., :, :-1]
    dy_s = log_s[..., 1:, :] - log_s[..., :-1, :]
    dy_t = log_t[..., 1:, :] - log_t[..., :-1, :]
    wy = weight[..., 1:, :] * weight[..., :-1, :]
    lx = (wx * (dx_s - dx_t).abs()).sum() / (wx.sum() + 1e-6)
    ly = (wy * (dy_s - dy_t).abs()).sum() / (wy.sum() + 1e-6)
    return lx + ly


def exposure_consistency_loss(pred_s: dict, pred_t: dict) -> tuple[torch.Tensor, dict[str, float]]:
    """Self-supervised cross-exposure distillation loss (scale-invariant depth + pose)."""
    d_s = pred_s["depth"].float().clamp(min=1e-4)
    d_t = pred_t["depth"].detach().float().clamp(min=1e-4)
    conf = pred_t.get("depth_conf")
    if conf is not None:
        w = (conf.detach().float() > 1.0).float()
        if w.sum() < 100:
            w = torch.ones_like(d_t)
    else:
        w = torch.ones_like(d_t)

    log_s = torch.log(d_s)
    log_t = torch.log(d_t)
    diff = log_s - log_t
    # Per-batch scale-invariant shift
    mean_diff = (w * diff).sum() / (w.sum() + 1e-6)
    silog = (w * (diff - mean_diff) ** 2).sum() / (w.sum() + 1e-6)
    grad = _grad_loss(log_s, log_t, w)

    loss_pose = torch.tensor(0.0, device=d_s.device)
    if "extrinsics" in pred_s and "extrinsics" in pred_t:
        ext_s = pred_s["extrinsics"].float()
        ext_t = pred_t["extrinsics"].detach().float()
        loss_pose = F.smooth_l1_loss(ext_s, ext_t, beta=0.05)

    total = silog + 0.5 * grad + 0.5 * loss_pose
    return total, {
        "total": float(total.item()),
        "silog": float(silog.item()),
        "grad": float(grad.item()),
        "pose": float(loss_pose.item()),
    }
