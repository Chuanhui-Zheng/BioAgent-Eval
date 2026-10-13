"""Source-statistic selection for broad gene-list questions, not target ranking."""
import math
import re
from itertools import zip_longest
from retrieval.schema import SearchResult
from retrieval.corpus import metadata_matches


def select_association_overview(question, records, collections, filters, top_k):
    if not re.search(r"\b(?:what|which|list|top)\b.*\b(?:genes|targets)\b", question, re.I):
        return None
    if not re.search(r"associat|evidence", question, re.I):
        return None
    association = [r for r in records if r.collection in collections
                   and r.collection in {"gene_association_common", "gene_association_rare"}
                   and metadata_matches(r, filters)]
    phenotypes = {str(r.metadata.get('phenotype')) for r in association}
    mentioned = [p for p in phenotypes if re.search(r'\b' + re.escape(p) + r'\b', question, re.I)]
    if not mentioned and re.search(r'2[- ]hour glucose', question, re.I) and '2hrG' in phenotypes:
        mentioned = ['2hrG']
    if len(mentioned) != 1:
        return None
    association = [r for r in association if r.metadata.get('phenotype') == mentioned[0]]
    def value(record, key, default):
        try:
            result = float(record.metadata.get(key))
            return result if math.isfinite(result) else default
        except (ValueError, TypeError):
            return default
    common = sorted([r for r in association if r.collection == 'gene_association_common' and value(r, 'bf_common', 0) > 1],
                    key=lambda r: (-value(r, 'bf_common', 0), r.chunk_id))
    rare = sorted([r for r in association if r.collection == 'gene_association_rare' and r.metadata.get('is_significant') is True],
                  key=lambda r: (value(r, 'pValue', 1), r.chunk_id))
    # Alternate independent evidence classes; never combine incomparable scores.
    selected = [r for pair in zip_longest(common[:top_k], rare[:top_k]) for r in pair if r is not None][:top_k]
    if not selected:
        return None
    return [SearchResult(r.chunk_id, r.collection, i + 1, 0.0, 'source_statistic_overview',
                         {'selection': 'common bf_common > 1 descending; rare source significance then pValue ascending'}, r.to_dict())
            for i, r in enumerate(selected)]
