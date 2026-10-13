import numpy as np
import pytest
from scipy.stats import hypergeom
from analysis.statistics import (
    benjamini_hochberg,
    parse_matrix,
    parse_associations,
    parse_gmt,
    enrichment,
    factorize,
    bayesian_factorize,
)


def test_enrichment_uses_measured_background_and_all_tested_terms():
    result = enrichment(
        ["A", "B"],
        ["A", "B", "C", "D", "E"],
        {"hit": {"A", "B"}, "nohit": {"D"}, "outside": {"Z"}},
    )
    assert result["tested_terms"] == 2
    row = result["results"][0]
    assert row["p_value"] == pytest.approx(hypergeom.sf(1, 5, 2, 2))
    assert row["q_value"] == pytest.approx(0.2)
    assert row["overlap"] == ["A", "B"]


def test_bh_is_monotonic_in_sorted_p_and_preserves_order():
    p = [0.2, 0.01, 0.02, 1]
    q = benjamini_hochberg(p)
    assert q == pytest.approx([0.2666666667, 0.04, 0.04, 1])
    assert benjamini_hochberg([]) == []


def test_enrichment_rejects_selected_gene_outside_background():
    with pytest.raises(ValueError, match="background"):
        enrichment(["X"], ["A"], {"set": {"X", "A"}})


def test_nonoverlap_terms_affect_multiple_testing():
    first = enrichment(["A"], ["A", "B", "C", "D"], {"hit": {"A"}})["results"][0][
        "q_value"
    ]
    second = enrichment(["A"], ["A", "B", "C", "D"], {"hit": {"A"}, "other": {"B"}})[
        "results"
    ][0]["q_value"]
    assert second == pytest.approx(first * 2)


@pytest.mark.parametrize(
    "text",
    ["gene,T1,T1\nA,1,2\n", "gene,T1\nA,nan\n", "gene,T1\nA,1\nA,2\n", "gene,T1\nA,\n"],
)
def test_matrix_rejects_bad_labels_or_values(text):
    with pytest.raises(ValueError):
        parse_matrix(text)


def test_factorization_reconstructs_rank_one_and_is_reproducible():
    x = np.outer([1, 2, 3], [2, 3])
    w, h, diag = factorize(x, 1, 200, 46)
    w2, h2, _ = factorize(x, 1, 200, 46)
    assert np.all(w >= 0) and np.all(h >= 0)
    assert np.allclose(w @ h, x, rtol=0.001)
    assert np.allclose(w, w2) and np.allclose(h, h2)
    assert diag["relative_error"] < 0.001


def test_nmf_rejects_negative_values_and_bad_components():
    with pytest.raises(ValueError, match="nonnegative"):
        factorize(np.array([[1.0, -1.0]]), 1)
    with pytest.raises(ValueError, match="Component"):
        factorize(np.ones((2, 2)), 3)


def test_bayesian_sampler_has_seeded_nonnegative_posterior_intervals():
    x = np.array([[3.0, 0.2], [0.3, 3.0], [2.0, 1.0]])
    w, h, d = bayesian_factorize(x, 2, 100, 46)
    w2, h2, d2 = bayesian_factorize(x, 2, 100, 46)
    assert np.all(w >= 0) and np.all(h >= 0) and np.isfinite(d["relative_error"])
    assert np.allclose(w, w2) and np.allclose(h, h2)
    assert np.array(d["posterior_w_low"]).shape == w.shape
    assert np.all(np.array(d["posterior_w_low"]) <= np.array(d["posterior_w_high"]))
    assert d["posterior_draws"] > 0 and d["convergence_assessed"] is False


def test_association_z_uses_effect_not_component_weight():
    rows = parse_associations("gene,phenotype,beta,stdErr,pValue\nA,T1,-.4,.1,.001\n")
    assert rows[0]["z"] == pytest.approx(-4)
    assert rows[0]["direction"] == "negative association"


@pytest.mark.parametrize(
    "row", ["A,T1,.4,-.1,4,.001", "A,T1,.4,.1,-4,.001", "A,T1,.4,.1,4,2"]
)
def test_associations_reject_inconsistent_or_invalid_statistics(row):
    with pytest.raises(ValueError):
        parse_associations("gene,phenotype,beta,stdErr,z,pValue\n" + row + "\n")


def test_gmt_duplicates_are_rejected_and_symbols_deduplicated():
    assert parse_gmt("set\tdescription\ta\tA\tB\n") == {"set": {"A", "B"}}
    with pytest.raises(ValueError):
        parse_gmt("set\tdesc\tA\nset\tdesc\tB\n")
