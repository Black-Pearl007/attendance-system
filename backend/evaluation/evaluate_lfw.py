"""Face-verification benchmark on LFW pairs: new pipeline vs. the original baseline.

    pip install -r requirements-eval.txt
    python -m evaluation.evaluate_lfw --subset test            # 1000 pairs (default)
    python -m evaluation.evaluate_lfw --subset test --max-pairs 300   # quick run

Outputs (in evaluation/results/):
    lfw_results.json      all metrics
    lfw_results.md        table ready to paste into the report
    lfw_roc_clean.png     ROC curves, clean images
    lfw_robustness.png    EER per degradation for both pipelines

What is measured, per pipeline and per degradation (applied to image 2 of each pair):
    * detection-failure rate (pairs where either face is not found; scored as 'reject')
    * ROC AUC, EER, TAR@FAR=1% and 10%
    * 10-fold accuracy with the threshold chosen on the other folds

Note: scikit-learn downloads LFW from the internet on first use (~230 MB).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from app.config import Settings
from app.services.face_engine import OpenCVFaceEngine

from . import baseline
from .metrics import auc, eer, kfold_accuracy, roc, tar_at_far
from .perturbations import PERTURBATIONS

RESULTS = Path(__file__).resolve().parent / "results"


def load_pairs(subset: str, max_pairs: int | None):
    from sklearn.datasets import fetch_lfw_pairs

    data = fetch_lfw_pairs(subset=subset, color=True, slice_=None, resize=1.0, funneled=True)
    pairs, labels = data.pairs, data.target
    if max_pairs and max_pairs < len(labels):
        rng = np.random.default_rng(0)
        sel = rng.choice(len(labels), size=max_pairs, replace=False)
        pairs, labels = pairs[sel], labels[sel]

    def to_bgr(a):
        a = np.asarray(a, dtype=np.float32)
        if a.max() <= 1.0:
            a = a * 255.0
        return cv2.cvtColor(a.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)

    return [(to_bgr(p[0]), to_bgr(p[1])) for p in pairs], np.asarray(labels).astype(bool)


class NewPipeline:
    def __init__(self, models_dir: Path):
        self.engine = OpenCVFaceEngine(models_dir, Settings().detector_score_threshold)

    def feature(self, bgr):
        faces = self.engine.detect(bgr)
        if not faces:
            return None
        # the largest face is the subject in LFW
        f = max(faces, key=lambda f: f.box[2] * f.box[3])
        return self.engine.embed(bgr, f)

    @staticmethod
    def score(a, b):
        return -np.inf if a is None or b is None else float(a @ b)  # cosine (unit vectors)


def evaluate(name, scorer_feature, scorer_score, pairs, labels, perturb):
    f1 = [scorer_feature(a) for a, _ in pairs]
    f2 = [scorer_feature(perturb(b)) for _, b in pairs]
    scores = np.array([scorer_score(a, b) for a, b in zip(f1, f2)])
    fail = float(np.mean([a is None or b is None for a, b in zip(f1, f2)]))
    # finite stand-in so ROC/threshold maths work: worse than every real score
    finite = scores[np.isfinite(scores)]
    floor = (finite.min() - 1.0) if len(finite) else -1.0
    s = np.where(np.isfinite(scores), scores, floor)
    thr, far, tar = roc(s, labels)
    e, _ = eer(far, tar)
    acc_mean, acc_std = kfold_accuracy(s, labels)
    return {
        "pipeline": name,
        "detect_fail_rate": round(fail, 4),
        "auc": round(auc(far, tar), 4),
        "eer": round(e, 4),
        "tar@far1%": round(tar_at_far(far, tar, 0.01), 4),
        "tar@far10%": round(tar_at_far(far, tar, 0.10), 4),
        "acc_10fold": round(acc_mean, 4),
        "acc_std": round(acc_std, 4),
        "_roc": (far.tolist(), tar.tolist()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", default="test", choices=["train", "test", "10_folds"])
    ap.add_argument("--max-pairs", type=int, default=None)
    ap.add_argument("--models-dir", type=Path, default=Settings().models_dir)
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    print("Loading LFW pairs ...")
    pairs, labels = load_pairs(args.subset, args.max_pairs)
    print(f"{len(pairs)} pairs ({labels.sum()} same / {(~labels).sum()} different)")
    new = NewPipeline(args.models_dir)

    rows, rocs = [], {}
    for pname, fn in PERTURBATIONS.items():
        for name, feat, sc in (
            ("baseline Haar+raw-pixel", baseline.feature, baseline.score),
            ("new YuNet+SFace", new.feature, new.score),
        ):
            r = evaluate(name, feat, sc, pairs, labels, fn)
            r["condition"] = pname
            rocs[(pname, name)] = r.pop("_roc")
            rows.append(r)
            print(f"{pname:10s} {name:26s} EER={r['eer']:.3f} AUC={r['auc']:.3f} fail={r['detect_fail_rate']:.3f}")

    (RESULTS / "lfw_results.json").write_text(json.dumps(rows, indent=2))
    md = ["| Condition | Pipeline | Detect-fail | AUC | EER | TAR@FAR=1% | TAR@FAR=10% | 10-fold acc |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(
            f"| {r['condition']} | {r['pipeline']} | {r['detect_fail_rate']:.1%} | {r['auc']:.3f} | {r['eer']:.3f} | "
            f"{r['tar@far1%']:.3f} | {r['tar@far10%']:.3f} | {r['acc_10fold']:.3f} ± {r['acc_std']:.3f} |"
        )
    (RESULTS / "lfw_results.md").write_text("\n".join(md) + "\n")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(5, 4.5))
        for name in ("baseline Haar+raw-pixel", "new YuNet+SFace"):
            far, tar = rocs[("clean", name)]
            plt.plot(far, tar, label=name)
        plt.plot([0, 1], [0, 1], "k:", lw=0.8)
        plt.xlabel("False accept rate")
        plt.ylabel("True accept rate")
        plt.title("LFW verification ROC (clean)")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(RESULTS / "lfw_roc_clean.png", dpi=160)
        plt.close()

        conds = list(PERTURBATIONS)
        x = np.arange(len(conds))
        plt.figure(figsize=(7, 4))
        for k, name in enumerate(("baseline Haar+raw-pixel", "new YuNet+SFace")):
            vals = [next(r["eer"] for r in rows if r["condition"] == c and r["pipeline"] == name) for c in conds]
            plt.bar(x + (k - 0.5) * 0.38, vals, 0.38, label=name)
        plt.xticks(x, conds)
        plt.ylabel("EER (lower is better)")
        plt.title("Robustness to degradations")
        plt.legend()
        plt.tight_layout()
        plt.savefig(RESULTS / "lfw_robustness.png", dpi=160)
    except ImportError:
        print("matplotlib not installed - skipped plots")
    print(f"\nWrote results to {RESULTS}")


if __name__ == "__main__":
    main()
