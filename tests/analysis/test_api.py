import gzip
import json
import pytest
import zstandard
from fastapi import FastAPI
from fastapi.testclient import TestClient
from chunking.phenotype_glossary import PhenotypeGlossary
from analysis.data import DataStore
from analysis.routes import create_router
from augmentation.builder import ContextBuilder
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.service import RetrieverService
from tests.helpers import FakeBackend, result


@pytest.fixture
def raw_root(tmp_path):
    raw = tmp_path / "data/raw"
    (raw / "gwas_genengine/EU").mkdir(parents=True)
    with gzip.open(raw / "gwas_genengine/EU/2hrFFA.sumstats.tsv.gz", "wt") as f:
        f.write(
            "phenotype\tchromosome\tposition\tvarId\tpValue\tbeta\tstdErr\tn\treference\talt\n2hrFFA\t1\t10\t1:10:A:T\t0.01\t0.2\t0.1\t20\tA\tT\n2hrFFA\t1\t20\t1:20:A:G\t0.5\t-0.1\t0.2\t20\tA\tG\n2hrFFA\t2\t30\t2:30:A:G\t2\t0.1\t0.2\t20\tA\tG\n"
        )
    expr = raw / "gtx_tissue_expression"
    expr.mkdir()
    (expr / "ALL_GENES_GTEx_RNAseq.csv").write_text(
        "tissue,Liver,gene\ncount,4,A\n50%,2,A\nmean,3,A\n"
    )
    (expr / "ALL_GENES_GTEx_Proteomics.csv").write_text(
        "value,tissue_specificity,tissue,gene\n-1,0,Liver,A\n2,1,Liver,A\n"
    )
    association = raw / "metaanalysis/ancestry-specific/2hrG/ancestry=EU"
    association.mkdir(parents=True)
    (association / "data.json.zst").write_bytes(
        zstandard.ZstdCompressor().compress(
            (
                json.dumps(
                    {
                        "phenotype": "2hrG",
                        "chromosome": "10",
                        "position": 100,
                        "varId": "10:100:A:T",
                        "pValue": 0,
                        "beta": 1,
                        "stdErr": 0.2,
                    }
                )
                + "\n"
            ).encode()
        )
    )
    return tmp_path


@pytest.fixture
def client(raw_root):
    p = RAGPipeline(
        RetrieverService(FakeBackend([result("gene:A", "gene_info")]), "fixture"),
        ContextBuilder(),
        OfflineEvidenceGenerator(),
    )
    app = FastAPI()
    app.include_router(
        create_router(
            raw_root,
            lambda: p,
            lambda gene: {},
            lambda: PhenotypeGlossary(
                {"T1": {"label": "Trait one", "aliases": ["Alias"]}, "T2": {}}
            ),
        )
    )
    return TestClient(app)


def test_source_index_preserves_counts_and_rejects_bad_p_values(raw_root):
    store = DataStore(raw_root)
    catalog = store.catalog()
    assert {r["phenotype"]: r["count"] for r in catalog["gwas"]} == {
        "2hrFFA": 2,
        "2hrG": 1,
    }
    assert (
        next(s for s in catalog["sources"] if s["source_file"].endswith(".gz"))[
            "rejected_records"
        ]
        == 1
    )
    assert DataStore(raw_root).catalog() == catalog


def test_qq_is_not_recomputed_from_significance_filtered_subset(raw_root):
    store = DataStore(raw_root)
    all_data = store.gwas("2hrFFA")
    filtered = store.gwas("2hrFFA", threshold=0.05)
    assert filtered["qq"] == all_data["qq"]
    assert filtered["total_records"] == 2 and filtered["significant_records"] == 1


def test_expression_preserves_rna_statistics_and_all_protein_observations(raw_root):
    store = DataStore(raw_root)
    rna = store.expression("a", "rna")
    protein = store.expression("a", "protein")
    assert rna["records"] == [
        {"tissue": "Liver", "count": 4.0, "50%": 2.0, "mean": 3.0}
    ]
    assert [r["value"] for r in protein["records"]] == [-1, 2]
    assert store.expression("' OR 1=1 --", "protein")["records"] == []


def test_region_boundaries_and_censored_zero_p(raw_root):
    store = DataStore(raw_root)
    assert store.gwas("2hrFFA", chromosome="1", start=10, end=10)["total_records"] == 1
    assert store.gwas("2hrG")["manhattan"][0]["minus_log10_p"] == 300


def test_api_invalid_region_and_unknown_data(client):
    assert client.get("/api/analysis/gwas?start=100&end=1").status_code == 422
    assert (
        client.get("/api/analysis/gwas?phenotype=missing").json()["total_records"] == 0
    )


def test_uploaded_factors_align_components_and_selection_filters_effects(client):
    response = client.post(
        "/api/analysis/matrix",
        json={
            "w_csv": "gene,C1,C2\nA,1,0\nB,0,1\n",
            "h_csv": "component,T1,T2\nC2,0,3\nC1,3,0\n",
            "associations_csv": "gene,phenotype,beta,stdErr,pValue\nA,T1,.4,.1,.001\nB,T2,-.3,.1,.001\n",
        },
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["h"] == [[3, 0], [0, 3]]
    selected = client.get(
        f"/api/analysis/runs/{run['run_id']}/selection?component=0&weight=.5&z_cutoff=3&trait=T1"
    ).json()
    assert [r["gene"] for r in selected["genes"]] == ["A"]
    assert selected["genes"][0]["effects"][0]["z"] == 4
    assert (
        client.get(
            f"/api/analysis/runs/{run['run_id']}/selection?component=5"
        ).status_code
        == 422
    )


def test_factor_csv_labels_and_nonnegative_validation(client):
    assert (
        client.post(
            "/api/analysis/matrix",
            json={"w_csv": "gene,C1\nA,1\n", "h_csv": "component,T1\nDIFFERENT,2\n"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/analysis/matrix",
            json={"matrix_csv": "gene,T1\nA,-1\n", "components": 1},
        ).status_code
        == 422
    )


def test_local_uploaded_library_requires_real_background(client):
    response = client.post(
        "/api/analysis/enrichment",
        json={
            "genes": ["A", "B"],
            "background": ["A", "B", "C", "D", "E"],
            "gmt": "set\tdesc\tA\tB\nother\tdesc\tD\n",
        },
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["q_value"] == pytest.approx(0.2)
    assert (
        client.post(
            "/api/analysis/enrichment",
            json={"genes": ["OUTSIDE"], "background": ["A"], "gmt": "set\tdesc\tA\n"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/analysis/enrichment",
            json={"genes": ["A"], "background": ["A"], "library": "../../secret"},
        ).status_code
        == 422
    )


def test_benchmark_requires_independent_labels(client):
    assert (
        client.post(
            "/api/analysis/evaluate", json={"benchmark_jsonl": '{"question":"test"}'}
        ).status_code
        == 422
    )
    annotation = json.dumps(
        {
            "question": "function of A",
            "expected_status": "answer",
            "gold_citations": ["gene:A"],
            "required_facts": ["Approved evidence summary."],
        }
    )
    report = client.post(
        "/api/analysis/evaluate", json={"benchmark_jsonl": annotation}
    ).json()
    assert report["status_accuracy"] == 1
    assert report["gold_citation_precision"] == 1
    assert report["results"][0]["human_review"]["citation_support"] is None


def test_phenotype_listing_uses_dictionary_glossary(client):
    response = client.get("/api/analysis/phenotypes")
    assert response.status_code == 200
    assert [r["code"] for r in response.json()["phenotypes"]] == ["T1", "T2"]
    filtered = client.get("/api/analysis/phenotypes?q=Alias").json()["phenotypes"]
    assert [r["code"] for r in filtered] == ["T1"]


def test_database_survives_relocation_and_timestamp_changes(raw_root, tmp_path):
    import os
    import shutil
    import hashlib
    store = DataStore(raw_root)
    store.ensure()
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    moved = tmp_path / "relocated"
    shutil.copytree(raw_root / "data", moved / "data")
    (moved / "artifacts/structured").mkdir(parents=True)
    shutil.copy2(store.path, moved / "artifacts/structured/analysis.sqlite")
    for file in (moved / "data/raw").rglob("*"):
        if file.is_file():
            os.utime(file, (1000000000, 1000000000))
    relocated = DataStore(moved)
    original_mtime = relocated.path.stat().st_mtime_ns
    relocated.ensure()
    assert relocated.path.stat().st_mtime_ns == original_mtime
    assert hashlib.sha256(relocated.path.read_bytes()).hexdigest() == before
    assert relocated.sources == store.sources


def test_database_detects_same_size_source_edit_with_preserved_timestamp(raw_root):
    import os
    store = DataStore(raw_root)
    store.ensure()
    source = raw_root / "data/raw/gtx_tissue_expression/ALL_GENES_GTEx_Proteomics.csv"
    stat = source.stat()
    source.write_text(source.read_text().replace("2,1,Liver,A", "9,1,Liver,A"))
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    changed = DataStore(raw_root)
    changed.ensure()
    with changed.connect() as db:
        assert db.execute("SELECT MAX(value) FROM expression WHERE kind='protein'").fetchone()[0] == 9


def test_database_detects_removed_source(raw_root):
    store = DataStore(raw_root)
    store.ensure()
    source = raw_root / "data/raw/gtx_tissue_expression/ALL_GENES_GTEx_Proteomics.csv"
    source.unlink()
    changed = DataStore(raw_root)
    changed.ensure()
    with changed.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM expression WHERE kind='protein'").fetchone()[0] == 0
