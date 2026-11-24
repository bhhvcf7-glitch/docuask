from uuid import UUID


def reciprocal_rank_fusion(
    rankings: list[list[UUID]], *, k: int = 60
) -> list[UUID]:
    """Fuse independent rankings without mixing incompatible raw scores."""
    if k < 1:
        raise ValueError("k must be positive")
    scores: dict[UUID, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(dict.fromkeys(ranking), start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda item: (-scores[item], str(item)))
