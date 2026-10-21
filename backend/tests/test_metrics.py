import numpy as np

from evaluation.metrics import auc, eer, kfold_accuracy, roc, tar_at_far


def test_perfect_separation():
    scores = np.array([0.9, 0.8, 0.7, 0.2, 0.1, 0.0])
    labels = np.array([1, 1, 1, 0, 0, 0])
    _, far, tar = roc(scores, labels)
    assert auc(far, tar) == 1.0
    assert eer(far, tar)[0] == 0.0
    assert tar_at_far(far, tar, 0.0) == 1.0
    mean, _ = kfold_accuracy(np.tile(scores, 5), np.tile(labels, 5), folds=5)
    assert mean == 1.0


def test_random_scores_are_near_chance():
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 2, 4000)
    _, far, tar = roc(rng.normal(size=4000), labels)
    assert abs(auc(far, tar) - 0.5) < 0.05
    assert abs(eer(far, tar)[0] - 0.5) < 0.05


def test_inverted_scores_give_zero_auc():
    scores = np.array([0.1, 0.2, 0.9, 0.8])
    labels = np.array([1, 1, 0, 0])
    _, far, tar = roc(scores, labels)
    assert auc(far, tar) == 0.0


def test_baseline_returns_none_without_face():
    from evaluation import baseline

    blank = np.full((200, 200, 3), 120, dtype=np.uint8)
    assert baseline.feature(blank) is None
    assert baseline.score(None, np.zeros(3)) == -np.inf
