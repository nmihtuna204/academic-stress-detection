"""Tests for the retrieval-quality harness.

The metric maths is tested against hand-computed values rather than against the
live embedder, so these run offline and pin the definitions themselves. If a
formula silently changes, these fail rather than the reported numbers quietly
shifting.
"""

import pytest

from app.eval.retrieval_eval import (
    Query,
    QueryOutcome,
    aggregate,
    load_queryset,
)


def make_outcome(retrieved: list[str], relevant: list[str], **kwargs) -> QueryOutcome:
    query = Query(
        id=kwargs.pop("id", 1),
        query=kwargs.pop("query", "q"),
        relevant=set(relevant),
        style=kwargs.pop("style", "natural"),
        lang=kwargs.pop("lang", "en"),
    )
    return QueryOutcome(query=query, retrieved=retrieved)


class TestQueryOutcomeMetrics:
    def test_first_relevant_rank_is_one_based(self):
        outcome = make_outcome(["a", "b", "c"], ["b"])
        assert outcome.first_relevant_rank() == 2

    def test_first_relevant_rank_none_when_missed(self):
        assert make_outcome(["a", "b"], ["z"]).first_relevant_rank() is None

    def test_recall_counts_fraction_of_relevant_found(self):
        outcome = make_outcome(["a", "b", "c"], ["a", "z"])
        assert outcome.recall_at(3) == pytest.approx(0.5)
        assert outcome.recall_at(1) == pytest.approx(0.5)

    def test_recall_is_one_when_all_relevant_retrieved(self):
        assert make_outcome(["a", "b"], ["a", "b"]).recall_at(2) == pytest.approx(1.0)

    def test_precision_divides_by_k_not_by_hits(self):
        outcome = make_outcome(["a", "b", "c", "d"], ["a"])
        assert outcome.precision_at(4) == pytest.approx(0.25)
        assert outcome.precision_at(1) == pytest.approx(1.0)

    def test_ndcg_is_one_for_ideal_ordering(self):
        assert make_outcome(["a", "b"], ["a", "b"]).ndcg_at(2) == pytest.approx(1.0)

    def test_ndcg_penalises_a_relevant_hit_placed_lower(self):
        """One hit at rank 2 instead of rank 1: DCG = 1/log2(3), IDCG = 1."""
        outcome = make_outcome(["x", "a"], ["a"])
        assert outcome.ndcg_at(2) == pytest.approx(1 / 1.5849625, abs=1e-6)

    def test_ndcg_zero_when_nothing_relevant_retrieved(self):
        assert make_outcome(["x", "y"], ["a"]).ndcg_at(2) == pytest.approx(0.0)


class TestAggregate:
    def test_mrr_treats_a_complete_miss_as_zero(self):
        """A missed query must drag MRR down, not be silently dropped."""
        outcomes = [
            make_outcome(["a"], ["a"], id=1),  # rank 1 -> 1.0
            make_outcome(["x", "y"], ["z"], id=2),  # miss -> 0.0
        ]
        assert aggregate(outcomes, ks=(1,))["mrr"] == pytest.approx(0.5)

    def test_misses_at_production_k_are_listed(self):
        outcomes = [
            make_outcome(["a"], ["a"], id=1),
            make_outcome(["x"], ["z"], id=2),
        ]
        stats = aggregate(outcomes, ks=(1,))
        assert [o.query.id for o in stats["misses_at_production_k"]] == [2]

    def test_empty_relevant_set_does_not_divide_by_zero(self):
        assert make_outcome(["a"], []).recall_at(1) == 0.0


class TestQuerysetFile:
    """The committed query set is research source data; guard its integrity."""

    def test_loads_and_is_well_formed(self):
        queries = load_queryset()
        assert len(queries) >= 50
        assert all(q.relevant for q in queries), "every query needs a relevance label"
        assert all(q.query.strip() for q in queries)

    def test_ids_are_unique(self):
        ids = [q.id for q in load_queryset()]
        assert len(ids) == len(set(ids))

    def test_labels_point_at_real_chunks(self):
        """A typo in a chunk id would silently score as a permanent miss."""
        from app.rag.ingest import load_knowledge_chunks

        real_ids = {c.chunk_id for c in load_knowledge_chunks()}
        for query in load_queryset():
            unknown = query.relevant - real_ids
            assert not unknown, f"query #{query.id} references unknown chunks: {unknown}"

    def test_covers_the_production_query_shape(self):
        """`build_rag_query()` emits keyword bags, so the set must score them."""
        styles = {q.style for q in load_queryset()}
        assert "keywords" in styles
        assert "natural" in styles

    def test_every_chunk_is_labelled_relevant_somewhere(self):
        from app.rag.ingest import load_knowledge_chunks

        labelled = set()
        for query in load_queryset():
            labelled |= query.relevant
        missing = {c.chunk_id for c in load_knowledge_chunks()} - labelled
        assert not missing, f"corpus chunks with no query exercising them: {missing}"


class TestQueryConstruction:
    """The retrieval query shape was chosen by measurement; pin what was chosen.

    `app/eval/retrieval_eval.py` measured, on the queries the construction
    actually alters, MRR 0.509 for the old shape against 0.839 for the current
    one. These tests stop that being silently undone.
    """

    def test_legacy_construction_discarded_the_sentence(self):
        """The old shape, kept only so the harness can show the before/after."""
        from app.eval.retrieval_eval import as_legacy_query

        produced = as_legacy_query(
            "I am overwhelmed by deadlines and cannot sleep at night before exams"
        )
        assert "overwhelmed" in produced
        assert "deadline" in produced
        assert "I am" not in produced

    def test_legacy_fell_back_to_raw_text_when_no_keyword_matched(self):
        from app.eval.retrieval_eval import as_legacy_query

        text = "the weather is lovely today and I went out with friends"
        assert as_legacy_query(text) == text

    def test_current_construction_keeps_the_sentence_and_adds_keywords(self):
        from app.api.services import build_rag_query
        from app.schemas.models import EmotionResult

        text = "I am overwhelmed by deadlines and cannot sleep"
        emotion = EmotionResult(
            emotion_label="x",
            emotion_scores={},
            sentiment_polarity="negative",
            stress_keywords=["overwhelmed", "deadline"],
        )
        produced = build_rag_query(text, emotion, None)
        assert produced.startswith(text), "the student's sentence must lead the query"
        assert "overwhelmed" in produced and "deadline" in produced

    def test_questionnaire_label_is_not_appended_to_a_text_query(self):
        """Appending it measurably hurt every variant tested."""
        from app.api.services import build_rag_query
        from app.schemas.enums import StressLevel
        from app.schemas.models import QuestionnaireResult

        questionnaire = QuestionnaireResult(ground_truth_label=StressLevel.HIGH)
        produced = build_rag_query("I cannot sleep before exams", None, questionnaire)
        assert "student with" not in produced
        assert produced == "I cannot sleep before exams"

    def test_questionnaire_only_still_uses_the_label(self):
        """No free text is unmeasured territory, so that branch is unchanged."""
        from app.api.services import build_rag_query
        from app.schemas.enums import StressLevel
        from app.schemas.models import QuestionnaireResult

        questionnaire = QuestionnaireResult(ground_truth_label=StressLevel.HIGH)
        assert build_rag_query(None, None, questionnaire) == "student with High stress"

    def test_no_signal_at_all_falls_back_to_a_generic_query(self):
        from app.api.services import build_rag_query

        assert "coping strategies" in build_rag_query(None, None, None)

    def test_blank_text_is_treated_as_no_text(self):
        from app.api.services import build_rag_query

        assert "coping strategies" in build_rag_query("   ", None, None)

    def test_harness_mirrors_the_real_helper(self):
        """`as_production_query` calls the real helper, so they cannot drift."""
        from app.api.services import build_rag_query
        from app.eval.retrieval_eval import as_production_query
        from app.nlp.lexicon import find_stress_keywords
        from app.schemas.models import EmotionResult

        text = "I am overwhelmed by deadlines and cannot sleep"
        emotion = EmotionResult(
            emotion_label="eval",
            emotion_scores={},
            sentiment_polarity="neutral",
            stress_keywords=find_stress_keywords(text),
        )
        assert as_production_query(text) == build_rag_query(text, emotion, None)


class TestQueryConstructionComparison:
    def test_pairs_only_natural_queries_and_reports_both_arms(self, monkeypatch):
        from app.eval import retrieval_eval
        from app.rag.retriever import RetrievedDoc

        # "as written" hits; the keyword-reduced form misses.
        def fake_retrieve(query, k):
            hit = "overwhelmed" not in query or "I am" in query
            chunk = "a" if hit else "z"
            return [RetrievedDoc(text="t", source="s", heading="h", distance=0.1, chunk_id=chunk)]

        monkeypatch.setattr(retrieval_eval, "retrieve", fake_retrieve)
        queries = [
            Query(
                id=1,
                query="I am overwhelmed by deadlines",
                relevant={"a"},
                style="natural",
                lang="en",
            ),
            Query(id=2, query="kw bag", relevant={"a"}, style="keywords", lang="en"),
        ]
        comparison = retrieval_eval.compare_query_construction(queries, ks=(1,))

        # The keyword-style query is excluded: it is already in production form.
        assert comparison["n_paired"] == 1
        assert comparison["n_reduced_to_keywords"] == 1
        assert comparison["as_written"]["recall_at"][1] == pytest.approx(1.0)
        # The old construction dropped the sentence and missed.
        assert comparison["as_legacy"]["recall_at"][1] == pytest.approx(0.0)
        # The current one keeps the sentence, so it hits again.
        assert comparison["as_current"]["recall_at"][1] == pytest.approx(1.0)

    def test_untransformed_queries_are_excluded_from_the_affected_subset(self, monkeypatch):
        from app.eval import retrieval_eval
        from app.rag.retriever import RetrievedDoc

        monkeypatch.setattr(
            retrieval_eval,
            "retrieve",
            lambda query, k: [RetrievedDoc(text="t", source="s", heading="h", distance=0.1, chunk_id="a")],
        )
        # No lexicon keyword in this sentence, so production sends it unchanged.
        queries = [
            Query(id=1, query="I read a book in the park", relevant={"a"}, style="natural", lang="en")
        ]
        comparison = retrieval_eval.compare_query_construction(queries, ks=(1,))
        assert comparison["n_reduced_to_keywords"] == 0
        assert "affected_as_written" not in comparison


class TestEvaluateWiring:
    def test_evaluate_uses_the_retriever_and_breaks_down_by_style(self, monkeypatch):
        """End-to-end shape check with retrieval stubbed, so it runs offline."""
        from app.eval import retrieval_eval
        from app.rag.retriever import RetrievedDoc

        monkeypatch.setattr(
            retrieval_eval,
            "retrieve",
            lambda query, k: [RetrievedDoc(text="t", source="s", heading="h", distance=0.1, chunk_id="a")],
        )
        queries = [
            Query(id=1, query="q1", relevant={"a"}, style="natural", lang="en"),
            Query(id=2, query="q2", relevant={"b"}, style="keywords", lang="vi"),
        ]
        results = retrieval_eval.evaluate(queries, ks=(1,))
        assert results["overall"]["n_queries"] == 2
        assert results["by_style"]["natural"]["recall_at"][1] == pytest.approx(1.0)
        assert results["by_style"]["keywords"]["recall_at"][1] == pytest.approx(0.0)
        assert results["by_lang"]["vi"]["mrr"] == pytest.approx(0.0)
        # "b" was labelled relevant but never retrieved.
        assert results["never_surfaced"] == ["b"]

    def test_report_lists_every_miss_verbatim(self, monkeypatch):
        from app.eval import retrieval_eval

        monkeypatch.setattr(retrieval_eval, "retrieve", lambda query, k: [])
        queries = [Query(id=7, query="a missed question", relevant={"a"}, style="natural", lang="en")]
        report = retrieval_eval.format_report(retrieval_eval.evaluate(queries, ks=(1,)))
        assert "a missed question" in report
        assert "#7" in report
