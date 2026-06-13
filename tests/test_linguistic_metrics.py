"""Tests for the optional linguistic metrics layer.

Tests that require spaCy or textstat are guarded with pytest.importorskip
so the suite stays green in environments without the linguistic extra.
"""

import pytest


class TestReadability:
    def test_readability_range(self):
        textstat = pytest.importorskip("textstat")
        pytest.importorskip("spacy")
        from specguard.linguistic import compute_linguistic_metrics

        texts = [
            "The cat sat on the mat.",
            "CVA6 shall implement the RV64GC ISA in compliance with the RISC-V specification.",
            "TBD.",
        ]
        for text in texts:
            m = compute_linguistic_metrics("T", text)
            # textstat returns raw formula values; very simple text can exceed 100,
            # very complex text can go below 0 — both are correct by definition.
            import math
            assert math.isfinite(m.flesch_reading_ease), (
                f"Flesch RE is not finite for: {text!r}"
            )

    def test_fk_grade_nonnegative(self):
        pytest.importorskip("textstat")
        pytest.importorskip("spacy")
        from specguard.linguistic import compute_linguistic_metrics

        m = compute_linguistic_metrics(
            "T",
            "CVA6 shall support the RV64GC ISA including all mandatory extensions.",
        )
        assert m.flesch_kincaid_grade >= 0.0


class TestSyntacticComplexity:
    def test_mdl_known_sentence(self):
        pytest.importorskip("spacy")
        pytest.importorskip("textstat")
        from specguard.linguistic import compute_linguistic_metrics
        from specguard.linguistic._spacy_loader import load_nlp

        nlp = load_nlp()
        m = compute_linguistic_metrics("T", "The cat sat on the mat.", nlp=nlp)
        assert 1.0 <= m.mean_dependency_length <= 2.5, (
            f"MDL {m.mean_dependency_length} outside expected [1.0, 2.5] "
            "for 'The cat sat on the mat.'"
        )
        assert m.max_dependency_length >= 1

    def test_mdl_finite(self):
        pytest.importorskip("spacy")
        pytest.importorskip("textstat")
        from specguard.linguistic import compute_linguistic_metrics

        m = compute_linguistic_metrics(
            "ISA-10",
            "CV64A6 shall support RV64I base instruction set architecture.",
        )
        assert m.mean_dependency_length >= 0.0
        assert m.max_dependency_length >= 0


class TestLexicalDensity:
    def test_lexical_density_range(self):
        pytest.importorskip("spacy")
        pytest.importorskip("textstat")
        from specguard.linguistic import compute_linguistic_metrics

        texts = [
            "The cat sat on the mat.",
            "CVA6 shall support the M extension for integer multiplication and division.",
            "TBD: performance target to be determined.",
        ]
        for text in texts:
            m = compute_linguistic_metrics("T", text)
            assert 0.0 <= m.lexical_density <= 1.0, (
                f"Lexical density {m.lexical_density} out of [0, 1] for: {text!r}"
            )


class TestEdgeCases:
    def test_empty_text_no_exception(self):
        pytest.importorskip("spacy")
        pytest.importorskip("textstat")
        from specguard.linguistic import compute_linguistic_metrics

        m = compute_linguistic_metrics("EMPTY", "")
        assert m.requirement_id == "EMPTY"
        assert m.flesch_reading_ease == 0.0
        assert m.flesch_kincaid_grade == 0.0
        assert m.mean_dependency_length == 0.0
        assert m.max_dependency_length == 0
        assert m.token_count == 0
        assert m.sentence_count == 0
        assert m.mean_sentence_length == 0.0
        assert m.lexical_density == 0.0

    def test_compute_with_preloaded_nlp(self):
        pytest.importorskip("spacy")
        pytest.importorskip("textstat")
        from specguard.linguistic import compute_linguistic_metrics
        from specguard.linguistic._spacy_loader import load_nlp

        nlp = load_nlp()
        # Two calls with the same nlp object — both must succeed
        m1 = compute_linguistic_metrics("T1", "CVA6 shall support RV64I.", nlp=nlp)
        m2 = compute_linguistic_metrics("T2", "The cache shall be configurable.", nlp=nlp)
        assert m1.token_count > 0
        assert m2.token_count > 0
        # Preloaded nlp object is the same reference as the cached one
        from specguard.linguistic._spacy_loader import _NLP_CACHE, _MODEL_NAME
        assert nlp is _NLP_CACHE[_MODEL_NAME]


class TestExtendedPipelineGracefulDegradation:
    def test_missing_extra_graceful(self):
        """Extended pipeline returns linguistic=None when the extra is absent.

        Skipped when both textstat and spacy are installed (the graceful
        degradation path cannot be exercised in that environment).
        """
        try:
            import textstat  # noqa: F401
            import spacy  # noqa: F401
            pytest.skip("linguistic extra is installed; degradation path not testable")
        except ImportError:
            pass

        from specguard.core.extended_pipeline import assess_requirement_extended
        result = assess_requirement_extended(
            "T1",
            "CVA6 shall support RV64I base instruction set architecture.",
        )
        assert result.linguistic is None
        assert result.base is not None
        assert result.gate_decision in ("PASS", "WARN", "FAIL")
