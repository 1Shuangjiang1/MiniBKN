from minibkn.evaluation import build_200_case_dataset, score_rankings


def test_benchmark_has_200_cases_and_scores_rankings() -> None:
    cases = build_200_case_dataset()
    assert len(cases) == 200
    assert len({case.id for case in cases}) == 200

    rankings = [[case.expected_document_id, "other"] for case in cases]
    metrics = score_rankings(cases, rankings)
    assert metrics == {
        "cases": 200,
        "hit_rate_at_1": 1.0,
        "hit_rate_at_3": 1.0,
        "mean_reciprocal_rank": 1.0,
        "context_precision_proxy": 1.0,
    }
