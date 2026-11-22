"""Score a reference view using only the input RGB images."""

from itertools import combinations

import cv2
import numpy as np
from PIL import Image


def _matches(matcher, source, target, ratio=0.80):
    return {
        pair[0].queryIdx: pair[0].trainIdx
        for pair in matcher.knnMatch(source, target, k=2)
        if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance
    }


def _coverage(points, shape):
    height, width = shape
    cells = np.clip((points / [width, height] * 4).astype(int), 0, 3)
    return len(np.unique(cells, axis=0)) / 16


def _pair_overlap(left, right, matcher):
    left_points, left_desc, left_shape = left
    right_points, right_desc, right_shape = right
    if left_desc is None or right_desc is None or len(left_desc) < 2 or len(right_desc) < 2:
        return 0.0
    forward = _matches(matcher, left_desc, right_desc)
    backward = _matches(matcher, right_desc, left_desc)
    pairs = [(i, j) for i, j in forward.items() if backward.get(j) == i]
    if len(pairs) < 8:
        return 0.0
    i, j = np.array(pairs).T
    source, target = left_points[i], right_points[j]
    matrix, mask = cv2.findFundamentalMat(source, target, cv2.FM_RANSAC, 3.0, 0.99)
    if matrix is None or mask is None:
        return 0.0
    keep = mask.ravel().astype(bool)
    if np.count_nonzero(keep) < 8:
        return 0.0
    coverage = min(_coverage(source[keep], left_shape), _coverage(target[keep], right_shape))
    return coverage * min(1.0, np.count_nonzero(keep) / 24)


def _gamma_normalize(pixels: np.ndarray, target_median: float = 110.0) -> np.ndarray:
    """Bring dark or bright views to a comparable mid-tone before local SIFT matching."""
    med = float(np.median(pixels))
    if med < 2.0 or med > 253.0:
        return pixels
    gamma = np.clip(np.log(target_median / 255.0) / np.log(med / 255.0), 0.25, 4.0)
    lut = np.clip(np.round(((np.arange(256, dtype=np.float32) / 255.0) ** gamma) * 255.0), 0, 255)
    return lut.astype(np.uint8)[pixels]


def _minmax(values: np.ndarray) -> np.ndarray:
    span = float(values.max() - values.min())
    if span < 1e-8:
        return np.zeros_like(values, dtype=float)
    return (values - values.min()) / span


def reference_scores(images: list[Image.Image]) -> dict[str, np.ndarray]:
    if len(images) < 3:
        raise ValueError("At least three views are required for reference selection.")
    sift = cv2.SIFT_create(nfeatures=2000, contrastThreshold=0.02)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    features = []
    exposure = []
    log_luma = []
    for image in images:
        gray = image.convert("L")
        gray.thumbnail((504, 504), Image.Resampling.LANCZOS)
        pixels = np.asarray(gray)
        luminance = pixels.astype(np.float32)
        shadows = np.clip((luminance - 8) / 56, 0, 1)
        highlights = np.clip((250 - luminance) / 20, 0, 1)
        exposure.append(float(np.minimum(shadows, highlights).mean()))
        log_luma.append(float(np.median(np.log1p(luminance))))
        enhanced = clahe.apply(_gamma_normalize(pixels))
        keypoints, descriptors = sift.detectAndCompute(enhanced, None)
        positions = np.array([kp.pt for kp in keypoints], dtype=np.float32)
        features.append((positions, descriptors, pixels.shape))

    overlap = np.zeros(len(images), dtype=float)
    for i, j in combinations(range(len(images)), 2):
        score = _pair_overlap(features[i], features[j], matcher)
        overlap[i] += score
        overlap[j] += score
    overlap /= len(images) - 1

    exposure = np.asarray(exposure, dtype=float)
    log_luma = np.asarray(log_luma, dtype=float)
    # Soft-saturate usable exposure so an outlier-bright view does not dominate
    # well-exposed intermediate views that photometrically bridge dark & bright frames.
    usable = np.tanh(exposure / 0.15)
    bridge = np.exp(-np.abs(log_luma - float(np.median(log_luma))) / 0.75)
    exposure_bridge = usable * bridge

    # Min-max normalize both branches so neither signal swamps the other by scale.
    combined = 0.5 * _minmax(exposure_bridge) + 0.5 * _minmax(overlap)
    return {
        "exposure": exposure,
        "exposure_bridge": exposure_bridge,
        "overlap": overlap,
        "combined": combined,
    }
