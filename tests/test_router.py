from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from retrieval.router import route_query


class RouterTests(unittest.TestCase):
    def test_gene_identifier(self) -> None:
        decision = route_query("Which gene is identified by ENSG00000148737?")
        self.assertEqual(decision.collections, ["gene_info"])

    def test_gene_function(self) -> None:
        decision = route_query("What is the function of TCF7L2?")
        self.assertEqual(decision.collections, ["gene_info"])

    def test_ldsc(self) -> None:
        decision = route_query("Is 2-hour insulin genetically correlated with T2D according to LDSC?")
        self.assertEqual(decision.collections, ["ldsc_genetic_correlation"])

    def test_common(self) -> None:
        decision = route_query("Common-variant evidence for ADCY5 and 2-hour glucose")
        self.assertEqual(decision.collections, ["gene_association_common"])

    def test_rare(self) -> None:
        decision = route_query("Rare-variant association for LPCAT2 and 2hrG")
        self.assertEqual(decision.collections, ["gene_association_rare"])

    def test_association_without_variant_class(self) -> None:
        decision = route_query("Gene-phenotype association of TCF7L2 with 2hrG")
        self.assertEqual(
            decision.collections,
            ["gene_association_common", "gene_association_rare"],
        )
        self.assertNotIn("gene_info", decision.collections)

    def test_ldsc_does_not_route_to_association_via_glucose(self) -> None:
        decision = route_query("Are 2-hour insulin and 2-hour glucose genetically correlated?")
        self.assertEqual(decision.collections, ["ldsc_genetic_correlation"])

    def test_unmatched(self) -> None:
        decision = route_query("What is the capital of France?")
        self.assertEqual(len(decision.collections), 4)

    def test_intent_union_for_cross_query(self) -> None:
        decision = route_query(
            "What is the function of TCF7L2 and the common-variant evidence for TCF7L2 and 2-hour glucose?"
        )
        self.assertEqual(decision.collections, ["gene_info", "gene_association_common"])


if __name__ == "__main__":
    unittest.main()
