"""Direction A: Lightweight learned exposure-aware reference view selector for DA3."""

from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

from cs431.reference import reference_scores


def _minmax_col(arr: np.ndarray) -> np.ndarray:
    span = arr.max(axis=0, keepdims=True) - arr.min(axis=0, keepdims=True)
    return np.where(span > 1e-8, (arr - arr.min(axis=0, keepdims=True)) / np.where(span > 1e-8, span, 1.0), 0.0)


@torch.inference_mode()
def extract_dinov2_view_stats(model, images: list[Image.Image], process_res: int = 336) -> np.ndarray:
    """Extract per-view DINOv2 CLS token statistics right before DA3 reference selection."""
    imgs_cpu, _, _ = model._preprocess_inputs(images, None, None, process_res=process_res)
    imgs, _, _ = model._prepare_model_inputs(imgs_cpu, None, None)
    vit = model.model.backbone.pretrained
    B, S, _, H, W = imgs.shape
    x = vit.prepare_tokens_with_masks(imgs)
    pos, _ = vit._prepare_rope(B, S, H, W, x.device)
    stop_idx = max(1, vit.alt_start - 1) if vit.alt_start != -1 else 4
    for i in range(stop_idx):
        l_pos = None if (i < vit.rope_start or vit.rope is None) else pos
        x = vit.process_attention(x, vit.blocks[i], "local", pos=l_pos)

    cls = x[0, :, 0].float()  # (S, C)
    cls_norm = cls / (cls.norm(dim=-1, keepdim=True) + 1e-8)
    sim = cls_norm @ cls_norm.T  # (S, S)
    mask = ~torch.eye(S, dtype=torch.bool, device=sim.device)
    sim_off = sim.masked_select(mask).view(S, S - 1)
    sim_mean = sim_off.mean(dim=-1)
    sim_min = sim_off.min(dim=-1).values
    sim_range = sim_off.max(dim=-1).values - sim_min
    feat_norm = cls.norm(dim=-1)
    feat_var = cls_norm.var(dim=-1)
    stats = torch.stack([sim_mean, sim_min, sim_range, feat_norm, feat_var], dim=-1)
    return stats.cpu().numpy().astype(np.float32)


def extract_view_features(
    images: list[Image.Image], model=None, process_res: int = 336
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Build a (S, 14) feature matrix combining RGB exposure/overlap stats and DINOv2 CLS stats."""
    scores = reference_scores(images)
    rgb_rows = []
    log_lumas = []
    for image in images:
        gray = image.convert("L")
        gray.thumbnail((504, 504), Image.Resampling.LANCZOS)
        px = np.asarray(gray, dtype=np.float32)
        mean_l = float(px.mean() / 255.0)
        std_l = float(px.std() / 255.0)
        p10, p50, p90 = [float(v / 255.0) for v in np.percentile(px, [10, 50, 90])]
        sharp = float(np.log1p(cv2.Laplacian(px, cv2.CV_32F).var()) / 10.0)
        log_lumas.append(float(np.median(np.log1p(px))))
        rgb_rows.append([mean_l, std_l, p10, p50, p90, sharp])

    log_lumas = np.asarray(log_lumas, dtype=np.float32)
    abs_delta_log = np.abs(log_lumas - float(np.median(log_lumas)))[:, None]
    base_rgb = np.column_stack(
        [
            scores["exposure"],
            scores["exposure_bridge"],
            scores["overlap"],
            abs_delta_log[:, 0],
        ]
    ).astype(np.float32)
    rgb_extra = np.asarray(rgb_rows, dtype=np.float32)

    if model is not None:
        dino = extract_dinov2_view_stats(model, images, process_res=process_res)
        # Normalize DINOv2 stats within the view set (same convention as saddle_balanced)
        dino_norm = _minmax_col(dino)
        raw = np.concatenate([base_rgb, rgb_extra[:, [0, 1, 5]], dino_norm], axis=1)  # 4 + 3 + 5 = 12
        # Add per-set min-max normalized exposure_bridge and overlap (total 14 dims)
        norm_key = _minmax_col(np.column_stack([scores["exposure_bridge"], scores["overlap"]]))
        feats = np.concatenate([raw, norm_key], axis=1).astype(np.float32)
    else:
        norm_key = _minmax_col(np.column_stack([scores["exposure_bridge"], scores["overlap"]]))
        feats = np.concatenate([base_rgb, rgb_extra, norm_key], axis=1).astype(np.float32)
    return feats, scores


class LearnedReferenceScorer(nn.Module):
    """Permutation-equivariant set scorer predicting optimal reference view logits."""

    def __init__(self, in_dim: int = 14, hidden_dim: int = 48):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim * 3, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.15),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (S, D) or (B, S, D)
        squeeze = x.ndim == 2
        if squeeze:
            x = x.unsqueeze(0)
        mean_ctx = x.mean(dim=1, keepdim=True)
        max_ctx = x.max(dim=1, keepdim=True).values
        ctx = torch.cat([x, x - mean_ctx, x - max_ctx], dim=-1)
        logits = self.net(ctx).squeeze(-1)
        return logits.squeeze(0) if squeeze else logits


def train_reference_scorer(
    samples: list[tuple[np.ndarray, np.ndarray]],
    epochs: int = 250,
    lr: float = 3e-3,
    weight_decay: float = 2e-2,
    tau: float = 0.04,
    seed: int = 42,
) -> tuple[LearnedReferenceScorer, list[float]]:
    """Train LearnedReferenceScorer with listwise KL loss against soft F1 targets."""
    torch.manual_seed(seed)
    in_dim = samples[0][0].shape[-1]
    scorer = LearnedReferenceScorer(in_dim=in_dim, hidden_dim=48)
    opt = torch.optim.AdamW(scorer.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    xs = [torch.from_numpy(f).float() for f, _ in samples]
    targets = [F.softmax(torch.from_numpy(y).float() / tau, dim=-1) for _, y in samples]
    # Weight samples with larger F1 span more heavily (flat-F1 sets are uninformative)
    weights = [max(0.1, float(y.max() - y.min())) for _, y in samples]
    w_sum = sum(weights)
    weights = [w / w_sum for w in weights]

    history = []
    scorer.train()
    for _ in range(epochs):
        opt.zero_grad()
        total_loss = 0.0
        for x, tgt, w in zip(xs, targets, weights):
            log_p = F.log_softmax(scorer(x), dim=-1)
            loss = F.kl_div(log_p, tgt, reduction="sum")
            total_loss = total_loss + w * loss
        total_loss.backward()
        opt.step()
        sched.step()
        history.append(float(total_loss.item()))

    scorer.eval()
    return scorer, history
