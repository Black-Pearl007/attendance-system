"""Verification metrics shared by the evaluation scripts (numpy only)."""
from __future__ import annotations

import numpy as np


def roc(scores: np.ndarray, labels: np.ndarray):
    """ROC for 'same person' (label 1) detection; higher score = more similar.
    Returns (thresholds, FAR, TAR) with FAR = false accept rate, TAR = true accept rate."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    order = np.argsort(-scores, kind="stable")
    s, y = scores[order], labels[order]
    tps = np.cumsum(y)
    fps = np.cumsum(~y)
    # keep only the last index of each distinct score
    distinct = np.r_[np.where(np.diff(s))[0], len(s) - 1]
    tar = np.r_[0.0, tps[distinct] / max(y.sum(), 1)]
    far = np.r_[0.0, fps[distinct] / max((~y).sum(), 1)]
    thr = np.r_[np.inf, s[distinct]]
    return thr, far, tar


def auc(far: np.ndarray, tar: np.ndarray) -> float:
    return float(np.trapezoid(tar, far)) if hasattr(np, "trapezoid") else float(np.trapz(tar, far))


def eer(far: np.ndarray, tar: np.ndarray) -> tuple[float, int]:
    """Equal error rate (FAR == FRR). Returns (eer, index into roc arrays)."""
    frr = 1.0 - tar
    i = int(np.argmin(np.abs(far - frr)))
    return float((far[i] + frr[i]) / 2.0), i


def tar_at_far(far: np.ndarray, tar: np.ndarray, target_far: float) -> float:
    ok = np.where(far <= target_far)[0]
    return float(tar[ok[-1]]) if len(ok) else 0.0


def best_threshold(scores: np.ndarray, labels: np.ndarray) -> float:
    """Threshold maximising accuracy on the given pairs."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    cands = np.unique(scores[np.isfinite(scores)])
    if len(cands) == 0:
        return 0.0
    accs = [((scores >= t) == labels).mean() for t in cands]
    return float(cands[int(np.argmax(accs))])


def kfold_accuracy(scores: np.ndarray, labels: np.ndarray, folds: int = 10, seed: int = 0) -> tuple[float, float]:
    """Mean/std accuracy with the threshold chosen on the other folds (no test leakage)."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    rng = np.random.default_rng(seed)
    idx = np.arange(len(scores))
    parts: list[np.ndarray] = [[] for _ in range(folds)]  # type: ignore[assignment]
    for lab in (True, False):  # stratified split
        sel = rng.permutation(idx[labels == lab])
        for k, chunk in enumerate(np.array_split(sel, folds)):
            parts[k] = np.r_[parts[k], chunk].astype(int)
    accs = []
    for k in range(folds):
        test = parts[k]
        train = np.concatenate([parts[j] for j in range(folds) if j != k]).astype(int)
        thr = best_threshold(scores[train], labels[train])
        accs.append(((scores[test] >= thr) == labels[test]).mean())
    return float(np.mean(accs)), float(np.std(accs))
