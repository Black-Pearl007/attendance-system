"""Open-set identification on YOUR OWN consented classroom-style dataset.

Folder layout (one folder per person, several photos each, varied lighting / pose / distance):

    dataset/
        alice/ 01.jpg 02.jpg ...
        bob/   ...
        carol/ ...

    python -m evaluation.evaluate_local --dataset dataset --enroll-n 5 --unknown 2

* The first --enroll-n photos of each *known* person are enrolled (gallery).
* The remaining photos are probes -> should be identified as that person.
* The last --unknown people are NEVER enrolled; their photos are impostor probes -> should be rejected.

Reported for the new pipeline AND the original (Haar + raw pixels, 1-NN with a distance threshold):
    * rank-1 identification rate, false-reject rate, mis-identification rate at the default threshold
    * false-accept rate on unknown people
    * a threshold sweep (CSV) and the EER of the open-set decision

Only do this with people who gave informed consent (see docs/EVALUATION.md); keep the dataset out of git.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from app.config import Settings
from app.services.face_engine import OpenCVFaceEngine

from . import baseline
from .metrics import eer

RESULTS = Path(__file__).resolve().parent / "results"
EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def load(dataset: Path):
    people = {}
    for d in sorted(p for p in dataset.iterdir() if p.is_dir()):
        imgs = sorted(f for f in d.iterdir() if f.suffix.lower() in EXT)
        if imgs:
            people[d.name] = imgs
    return people


def sweep(known_scores, known_correct, unknown_scores, thresholds):
    """known_scores: best similarity for each known probe; known_correct: was the best match the right person."""
    rows = []
    for t in thresholds:
        accepted = known_scores >= t
        tp = np.mean(accepted & known_correct) if len(known_scores) else 0.0  # correctly identified
        mis = np.mean(accepted & ~known_correct) if len(known_scores) else 0.0  # accepted as someone else
        frr = 1.0 - np.mean(accepted) if len(known_scores) else 0.0
        far = np.mean(unknown_scores >= t) if len(unknown_scores) else 0.0
        rows.append({"threshold": float(t), "identification_rate": float(tp), "misid_rate": float(mis), "frr": float(frr), "far": float(far)})
    return rows


def run_pipeline(name, feat_fn, sim_fn, people, enroll_n, n_unknown, default_thr):
    names = list(people)
    known = names[: len(names) - n_unknown] if n_unknown else names
    unknown = names[len(names) - n_unknown :] if n_unknown else []

    gallery, probes_known, probes_unknown, fails = [], [], [], 0
    for person in known:
        for k, path in enumerate(people[person]):
            f = feat_fn(cv2.imread(str(path)))
            if f is None:
                fails += 1
                continue
            if k < enroll_n:
                gallery.append((person, f))
            else:
                probes_known.append((person, f))
    for person in unknown:
        for path in people[person]:
            f = feat_fn(cv2.imread(str(path)))
            if f is None:
                fails += 1
                continue
            probes_unknown.append((person, f))

    def best(f):
        sims = [(sim_fn(f, g), p) for p, g in gallery]
        return max(sims) if sims else (-np.inf, None)

    ks, kc = [], []
    for person, f in probes_known:
        s, p = best(f)
        ks.append(s)
        kc.append(p == person)
    us = [best(f)[0] for _, f in probes_unknown]
    ks, kc, us = np.array(ks), np.array(kc, dtype=bool), np.array(us)

    lo, hi = np.nanmin(np.r_[ks, us][np.isfinite(np.r_[ks, us])]), np.nanmax(np.r_[ks, us][np.isfinite(np.r_[ks, us])])
    thresholds = np.linspace(lo, hi, 200)
    table = sweep(ks, kc, us, thresholds)
    far_arr = np.array([r["far"] for r in table])
    tar_arr = np.array([r["identification_rate"] for r in table])
    summary = {
        "pipeline": name,
        "gallery_images": len(gallery),
        "known_probes": len(ks),
        "unknown_probes": len(us),
        "detect_failures": fails,
        "rank1_acc_ignoring_threshold": float(kc.mean()) if len(kc) else None,
    }
    if len(us):
        e, i = eer(far_arr, tar_arr)
        summary["open_set_eer"] = round(float(e), 4)
        summary["eer_threshold"] = float(thresholds[i])
        summary["at_eer_threshold"] = table[i]
    if default_thr is not None:  # only the new pipeline has a calibrated default threshold
        summary["default_threshold"] = default_thr
        summary["at_default_threshold"] = sweep(ks, kc, us, [default_thr])[0]
    return summary, table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--enroll-n", type=int, default=5)
    ap.add_argument("--unknown", type=int, default=1, help="number of people held out as impostors")
    ap.add_argument("--models-dir", type=Path, default=Settings().models_dir)
    args = ap.parse_args()

    people = load(args.dataset)
    if len(people) - args.unknown < 2:
        raise SystemExit("Need at least 2 known people plus the held-out unknown people.")
    cfg = Settings()
    engine = OpenCVFaceEngine(args.models_dir, cfg.detector_score_threshold)

    def new_feat(bgr):
        faces = engine.detect(bgr)
        return engine.embed(bgr, max(faces, key=lambda f: f.box[2] * f.box[3])) if faces else None

    RESULTS.mkdir(exist_ok=True)
    out = []
    for name, feat, sim, thr in (
        ("baseline Haar+raw-pixel (1-NN)", baseline.feature, lambda a, b: -float(np.linalg.norm(a - b)), None),
        ("new YuNet+SFace", new_feat, lambda a, b: float(a @ b), cfg.match_threshold),
    ):
        summary, table = run_pipeline(name, feat, sim, people, args.enroll_n, args.unknown, thr)
        out.append(summary)
        slug = "baseline" if name.startswith("baseline") else "new"
        with open(RESULTS / f"local_sweep_{slug}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
        print(json.dumps(summary, indent=2))
    (RESULTS / "local_results.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {RESULTS}")


if __name__ == "__main__":
    main()
