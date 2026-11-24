import pytest

from eval.calibrate import collect_scores, describe, gate_metrics, select_candidate, sweep

CASES = [{"id": "a", "answerable": True}, {"id": "b", "answerable": False}]
ROWS = [{"id": "a", "hits": [{"score": .7}, {"score": .9}]},
        {"id": "b", "hits": [{"score": .6}, {"score": .5}]}]


def test_reordered_scores():
    assert collect_scores(CASES, ROWS, "top1") == ([.7], [.6])
    assert collect_scores(CASES, ROWS, "max") == ([.9], [.6])
    positive, negative = collect_scores(CASES, ROWS, "margin")
    assert positive == pytest.approx([.2])
    assert negative == pytest.approx([.1])


def test_inclusive_gate_and_missing():
    row = gate_metrics([.8, None], [.7, None], .8)
    assert row["recall"] == .5
    assert row["refusal"] == 1
    assert describe([.8, None])["missing"] == 1


def test_candidate():
    candidate = select_candidate(sweep([.8, .9], [.6, .7]), 1)
    assert candidate["refusal"] == 1
    assert select_candidate(sweep([None], [.5]), 1) is None


def test_ids():
    with pytest.raises(ValueError, match="IDs differ"):
        collect_scores(CASES, ROWS[:1], "max")
    with pytest.raises(ValueError, match="Duplicate"):
        collect_scores(CASES, ROWS + ROWS[:1], "max")


@pytest.mark.parametrize("score", [float("nan"), float("inf"), 1.1])
def test_invalid_score(score):
    with pytest.raises(ValueError, match="Invalid cosine"):
        collect_scores(CASES, [{"id": "a", "hits": [{"score": score}]}, ROWS[1]], "max")
