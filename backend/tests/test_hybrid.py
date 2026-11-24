from uuid import UUID

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.sparse import lexical_terms


def test_fusion_rewards_agreement_and_deduplicates():
    a, b, c = (UUID(int=i) for i in range(1, 4))
    assert reciprocal_rank_fusion([[a, b, b], [c, b]]) == [b, a, c]
    assert reciprocal_rank_fusion([[], []]) == []
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[a]], k=0)


def test_bilingual_lexical_terms():
    assert lexical_terms("إِدارة الإدارة API api ١٢ | !") == ["ادارة", "الادارة", "api", "12"]
    assert lexical_terms("! | &") == []
    assert len(lexical_terms(" ".join(f"term{i}" for i in range(100)))) == 64
