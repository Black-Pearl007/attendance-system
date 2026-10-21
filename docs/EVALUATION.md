# Evaluation protocol and result templates

This document is the skeleton of the "Results" chapter for the project report / master's application.
**No numbers are filled in on purpose** — run the scripts and paste your own measurements.
Never quote results you did not produce.

## 1. Research questions
1. Does replacing Haar + raw-pixel KNN with DNN detection + embedding matching improve verification accuracy?
2. How do both pipelines degrade under lighting, blur, distance, noise and occlusion?
3. Can the system reject people who are not enrolled (open-set), which the original KNN cannot do?
4. Does the head-turn liveness check stop simple presentation attacks, and where does it fail?

## 2. Experiment A — LFW verification benchmark (public data)
```bash
cd backend
pip install -r requirements-eval.txt
python -m evaluation.evaluate_lfw --subset test
```
* Data: Labeled Faces in the Wild pairs (1000 pairs in the `test` split, downloaded by scikit-learn on first run).
* Pipelines: **baseline** = original PT2 method (Haar cascade → first face → 50×50 → raw pixels → Euclidean distance); **new** = YuNet → SFace → cosine similarity.
* Conditions: `clean, dark, bright, blur, low_res, noise, occlusion` (applied to the second image of each pair; see `evaluation/perturbations.py`).
* Metrics: detection-failure rate (counted as a rejected pair, never silently dropped), ROC AUC, **EER**, TAR@FAR = 1 % / 10 %, 10-fold accuracy with the threshold chosen on the other folds.
* Outputs: `evaluation/results/lfw_results.md|json`, `lfw_roc_clean.png`, `lfw_robustness.png`.

Result table (paste from `lfw_results.md`):

| Condition | Pipeline | Detect-fail | AUC | EER | TAR@FAR=1% | TAR@FAR=10% | 10-fold acc |
|---|---|---|---|---|---|---|---|
| clean | baseline | | | | | | |
| clean | new | | | | | | |
| … | | | | | | | |

Discussion prompts: where does the baseline collapse first (lighting? occlusion?), what is the cost of the new pipeline (latency per frame), and is the default threshold 0.363 appropriate for your target FAR?

## 3. Experiment B — classroom-style open-set test (your own data)
Collect **with written consent** 8–15 volunteers, 10+ photos each (different days if possible, lighting, distance, head pose, glasses on/off). Keep this dataset **out of git** and delete it when the study ends.

```
dataset/
  alice/01.jpg 02.jpg …
  bob/…
```
```bash
python -m evaluation.evaluate_local --dataset dataset --enroll-n 5 --unknown 2
```
First 5 photos of each known person are enrolled; the rest are probes; the last `--unknown` people are never enrolled and act as impostors. The script reports identification rate, false-reject, mis-identification and **false-accept on unknown people** for both pipelines, plus a threshold sweep CSV (`local_sweep_*.csv`).

| Pipeline | Identification rate | False reject | Mis-ID | FAR on unknown | Open-set EER |
|---|---|---|---|---|---|
| baseline | | | | | |
| new | | | | | |

Report per-subgroup results if your sample allows (lighting, glasses, distance) and be explicit about the sample size and its limits.

## 4. Experiment C — presentation-attack (spoofing) test
Procedure (with the volunteer's consent, own devices only):
1. Enrol a volunteer normally.
2. Attacks, 20 attempts each, camera ~1 m away, **liveness ON** and again **liveness OFF** (`LIVENESS_REQUIRED=false`):
   * A. printed colour photo (flat)
   * B. printed photo, tilted/rotated by hand to imitate a head turn
   * C. photo displayed on a phone screen
   * D. video of the volunteer turning their head, played on a phone/tablet
3. Count attempts that result in the volunteer being marked present = **attack success rate**. Also run 20 genuine attempts to measure the **genuine rejection rate** (usability cost).

| Attack | Liveness OFF success | Liveness ON success |
|---|---|---|
| A. printed photo | | |
| B. tilted photo | | |
| C. phone screen photo | | |
| D. replayed head-turn video | | |
| Genuine user rejected | | |

Expect D (and possibly B) to succeed — report it honestly as a limitation and propose a passive anti-spoofing model as future work.

## 5. Efficiency
Measure median / p95 latency of `POST /api/recognition/{id}/frame` for 1, 3 and 6 faces on your CPU (browser dev tools → Network, or a short script). Report CPU model and frame width (default capture is 800 px).

## 6. Threats to validity (include in the report)
* LFW is mostly frontal celebrity photos; it over-represents some demographics.
* Small, self-collected datasets give wide confidence intervals; report n.
* The baseline is re-implemented from the PT2 code path (Haar → first face → 50×50 raw pixels); say so.
* SFace's 0.363 threshold comes from its authors' benchmark; your camera and population may need a different operating point.

## 7. Suggested report outline
1. Introduction & motivation (limitations of PT2)
2. Related work (face detection, embeddings, liveness, biometric privacy / GDPR)
3. System design (architecture diagram, data model, API)
4. Methods (pipeline, quality gate, open-set matching, tracking & liveness)
5. Experiments A–C and results
6. Privacy, ethics and limitations
7. Conclusion and future work (passive anti-spoofing, on-device inference, fairness audit)
