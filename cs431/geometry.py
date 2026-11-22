"""Metrics for fixed-view, pose-free reconstruction experiments."""

import numpy as np
from scipy.spatial import cKDTree


def to_metric_poses(colmap_c2w, colmap_to_world):
    transform = np.asarray(colmap_to_world, dtype=float)
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("COLMAP-to-world transform must be a finite 4x4 matrix.")
    if not np.allclose(transform[3], [0, 0, 0, 1]):
        raise ValueError("COLMAP-to-world transform must have last row [0, 0, 0, 1].")
    block = transform[:3, :3]
    scale = np.linalg.norm(block, ord="fro") / np.sqrt(3)
    if scale <= 0:
        raise ValueError("COLMAP-to-world scale must be positive.")
    rotation = block / scale
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-4) or np.linalg.det(rotation) < 0:
        raise ValueError("COLMAP-to-world transform must have uniform scale and a proper rotation.")
    poses = colmap_c2w.copy()
    poses[:, :3, :3] = rotation @ colmap_c2w[:, :3, :3]
    poses[:, :3, 3] = colmap_c2w[:, :3, 3] @ block.T + transform[:3, 3]
    return poses


def predicted_poses(extrinsics):
    extrinsics = np.asarray(extrinsics, dtype=float)
    if extrinsics.ndim != 3 or extrinsics.shape[1:] not in ((3, 4), (4, 4)):
        raise ValueError("Expected DA3 world-to-camera extrinsics of shape (N, 3, 4) or (N, 4, 4).")
    if not np.isfinite(extrinsics).all():
        raise ValueError("Predicted camera poses contain non-finite values.")
    w2c = np.repeat(np.eye(4)[None], len(extrinsics), axis=0)
    w2c[:, :3] = extrinsics[:, :3]
    return np.linalg.inv(w2c)


def relative_pose_metrics(pred_c2w, gt_c2w):
    i, j = np.triu_indices(len(gt_c2w), k=1)
    pred = np.linalg.inv(pred_c2w[j]) @ pred_c2w[i]
    gt = np.linalg.inv(gt_c2w[j]) @ gt_c2w[i]
    pred_t, gt_t = pred[:, :3, 3], gt[:, :3, 3]
    gt_baseline = np.linalg.norm(gt_t, axis=1)
    valid = gt_baseline > 1e-8
    if not valid.any():
        raise ValueError("Ground-truth camera pairs have zero translation.")
    relative_rot = pred[:, :3, :3] @ gt[:, :3, :3].transpose(0, 2, 1)
    rotation_cos = (np.trace(relative_rot, axis1=1, axis2=2) - 1) / 2
    rotation = np.degrees(np.arccos(np.clip(rotation_cos, -1, 1)))
    denom = gt_baseline * np.linalg.norm(pred_t, axis=1)
    similarity = np.divide(
        (pred_t * gt_t).sum(axis=1), denom, out=-np.ones_like(denom), where=denom > 1e-15
    )
    translation = np.degrees(np.arccos(np.clip(similarity, -1, 1)))
    errors = np.maximum(rotation, translation)[valid]
    return {
        "auc10": float(np.clip(1 - errors / 10, 0, 1).mean()),
        "valid_pose_pairs": int(valid.sum()),
    }


def _unproject(depths, intrinsics, c2w, stride):
    _, height, width = depths.shape
    x, y = np.meshgrid(np.arange(0, width, stride), np.arange(0, height, stride))
    pixels = np.stack((x, y, np.ones_like(x)), axis=-1).reshape(-1, 3)
    points = []
    for depth, camera, pose in zip(depths, intrinsics, c2w, strict=True):
        z = depth[::stride, ::stride].reshape(-1)
        valid = np.isfinite(z) & (z > 0)
        camera_points = (pixels[valid] @ np.linalg.inv(camera).T) * z[valid, None]
        points.append(camera_points @ pose[:3, :3].T + pose[:3, 3])
    return np.concatenate(points)


def voxel_sample(points, size=0.01):
    cells = np.floor(points / size).astype(np.int64)
    _, indices, counts = np.unique(cells, axis=0, return_inverse=True, return_counts=True)
    # A centroid gives the same sample when changing the reference reorders the views.
    totals = np.column_stack([np.bincount(indices, weights=axis) for axis in points.T])
    return totals / counts[:, None]


def align_poses_sim3(pred_c2w, gt_c2w):
    """Estimate Sim(3) (R, t, s) mapping pred_c2w -> gt_c2w using both rotations and centers.

    Using camera rotations eliminates the roll ambiguity around the camera-center line
    that position-only Umeyama suffers from when views lie on a shallow arc.
    """
    pred_rot = pred_c2w[:, :3, :3]
    gt_rot = gt_c2w[:, :3, :3]
    cross_cov = np.einsum("nij,nkj->ik", gt_rot, pred_rot)
    u, _, vt = np.linalg.svd(cross_cov)
    sign = np.linalg.det(u @ vt)
    rotation = u @ np.diag([1.0, 1.0, 1.0 if sign >= 0 else -1.0]) @ vt

    pred_t = pred_c2w[:, :3, 3]
    gt_t = gt_c2w[:, :3, 3]
    pred_mean = pred_t.mean(axis=0)
    gt_mean = gt_t.mean(axis=0)
    pred_centered_rot = (pred_t - pred_mean) @ rotation.T
    gt_centered = gt_t - gt_mean
    denom = float(np.sum(pred_centered_rot**2))
    if denom <= 1e-12:
        raise ValueError("Degenerate predicted camera centers.")
    scale = float(np.sum(pred_centered_rot * gt_centered) / denom)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid predicted-to-reference scale.")
    offset = gt_mean - scale * (pred_mean @ rotation.T)
    return rotation, offset, scale


def cloud_metrics(prediction, gt_c2w_m, gt_points, threshold=0.05, stride=4):
    poses = predicted_poses(prediction.extrinsics)
    try:
        rotation, offset, scale = align_poses_sim3(poses, gt_c2w_m)
    except ValueError as error:
        return {"f1": None, "alignment_error": str(error)}
    points = _unproject(prediction.depth, prediction.intrinsics, poses, stride)
    if not len(points):
        return {"f1": 0.0, "precision": 0.0, "recall": 0.0, "scale_to_metres": float(scale)}
    points = voxel_sample(scale * (points @ rotation.T) + offset)
    d_pred_to_gt = cKDTree(gt_points).query(points, k=1)[0]
    d_gt_to_pred = cKDTree(points).query(gt_points, k=1)[0]
    precision = float((d_pred_to_gt < threshold).mean())
    recall = float((d_gt_to_pred < threshold).mean())
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    p10 = float((d_pred_to_gt < 0.10).mean())
    r10 = float((d_gt_to_pred < 0.10).mean())
    f1_10 = 2 * p10 * r10 / (p10 + r10) if p10 + r10 else 0.0
    return {
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "f1_10cm": f1_10,
        "median_pred_to_gt_m": float(np.median(d_pred_to_gt)),
        "median_gt_to_pred_m": float(np.median(d_gt_to_pred)),
        "scale_to_metres": float(scale),
    }
