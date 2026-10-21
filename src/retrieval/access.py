"""Explicit simulated workspaces, not user authentication."""
from contextvars import ContextVar
from retrieval.router import SUPPORTED_COLLECTIONS

WORKSPACES = {
    "all": {"label": "Current client evidence", "collections": tuple(c for c in SUPPORTED_COLLECTIONS if c != "ldsc_partitioned_heritability")},
    "annotations": {"label": "Annotations and expression", "collections": ("gene_info", "gtex_tissue_expression")},
    "genetics": {"label": "Genetic association evidence", "collections": tuple(c for c in SUPPORTED_COLLECTIONS if c not in {"gene_info", "gtex_tissue_expression", "ldsc_partitioned_heritability"})},
}
workspace_id = ContextVar("workspace_id", default="all")

def allowed_collections():
    return WORKSPACES[workspace_id.get()]["collections"]

def path_is_allowed(path: str) -> bool:
    requirements = {
        "/api/genes": {"gene_info"},
        "/api/analysis/expression": {"gtex_tissue_expression"},
        "/api/analysis/gwas": {"variant_association_clumped"},
        "/api/analysis/references": {"variant_association_clumped", "gene_association_wes"},
        "/api/analysis/annotations": {"gene_info"},
        "/api/analysis/compare": {"gene_info"},
        "/api/analysis/matrix/client-example": {"gene_association_common", "gene_association_rare"},
        "/api/analysis/matrix/corpus": {"gene_association_common", "gene_association_rare"},
        "/api/analysis/catalog": set(SUPPORTED_COLLECTIONS),
        "/api/analysis/evaluate": set(SUPPORTED_COLLECTIONS),
    }
    for prefix, required in requirements.items():
        if path == prefix or path.startswith(prefix + "/"):
            return required.issubset(allowed_collections())
    return True
