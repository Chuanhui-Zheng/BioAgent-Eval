import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import server
from analysis.routes import create_router
from augmentation.builder import ContextBuilder
from chunking.gtex_chunker import build_gtex, validate_gtex
from generation.aihubmix import AIHubMixGenerator, _parse_answer
from generation.offline import OfflineEvidenceGenerator
from generation.schema import Claim, GeneratedAnswer
from generation.validator import validate_answer
from rag.pipeline import RAGPipeline
from retrieval.bm25_retriever import build_bm25_index
from retrieval.corpus import LoadedCorpus
from retrieval.dense_retriever import build_dense_index
from retrieval.schema import ChunkRecord
from retrieval.service import RetrievalRequest, RetrieverService
from tests.helpers import FakeBackend, result


def pipeline(hits):
    backend = FakeBackend(hits)
    backend.records = [ChunkRecord.from_dict(h.chunk) for h in hits]
    return RAGPipeline(RetrieverService(backend, 'fixture'), ContextBuilder(), OfflineEvidenceGenerator())


def test_bm25_filters_before_top_k_even_with_250_stronger_excluded_hits():
    records = [ChunkRecord.from_dict(result(f'gtex:X{i}', 'gtex_tissue_expression', content='glucose glucose glucose').chunk) for i in range(250)]
    records.append(ChunkRecord.from_dict(result('common:A', 'gene_association_common', content='glucose and other scientific evidence').chunk))
    index = build_bm25_index(LoadedCorpus(records, {}, {}), ('content',))
    assert [r.chunk_id for r in index.search('glucose', top_k=1, collections=['gene_association_common'])] == ['common:A']
    assert index.search('glucose', collections=[]) == []


def test_dense_filters_before_top_k_even_with_250_stronger_excluded_hits():
    class Encoder:
        dimension = 2
        model_name = revision = device = 'fixture'
        def encode_documents(self, texts):
            return np.array([[1, 0] if t == 'excluded' else [0.5, 0.5] for t in texts], dtype=np.float32)
        def encode_queries(self, texts):
            return np.array([[1, 0] for _ in texts], dtype=np.float32)
    records = [ChunkRecord.from_dict(result(f'gtex:X{i}', 'gtex_tissue_expression', content='excluded').chunk) for i in range(250)]
    records.append(ChunkRecord.from_dict(result('common:A', 'gene_association_common', content='allowed').chunk))
    index = build_dense_index(LoadedCorpus(records, {}, {}), Encoder(), 64, progress=None)
    assert [r.chunk_id for r in index.search('query', top_k=1, collections=['gene_association_common'])] == ['common:A']


def test_gtex_sources_units_nonfinite_values_and_requested_tissue(tmp_path):
    raw = tmp_path / 'data/raw/gtx_tissue_expression'
    raw.mkdir(parents=True)
    (raw/'ALL_GENES_GTEx_RNAseq.csv').write_text('tissue,Liver,Brain,gene\n50%,2,8,PPARG\n50%,NaN,3,OTHER\n')
    (raw/'ALL_GENES_GTEx_Proteomics.csv').write_text('value,tissue_specificity,tissue,gene\n4,0,Liver,OTHER\n')
    report = build_gtex(tmp_path)
    records = [json.loads(x) for x in (tmp_path/report['output']['path']).read_text().splitlines()]
    gene = next(r for r in records if r['metadata']['gene_symbol'] == 'PPARG')
    assert gene['citation']['source_file'].endswith('RNAseq.csv')
    assert len(gene['citation']['sources']) == 1
    assert gene['citation']['source_sha256']
    assert 'TPM' not in gene['content']
    assert report['rejected_values'] == 1
    hit = result(gene['chunk_id'], gene['collection'], metadata=gene['metadata'], content=gene['content'])
    run = pipeline([hit]).run(RetrievalRequest('In which tissues is PPARG expressed, including Liver?'))
    assert 'Liver' in run.answer.answer and 'median 2' in run.answer.answer
    assert 'Function information is not available' not in run.answer.answer
    assert run.answer.status == 'qualified' and run.validation.valid
    validate_gtex(tmp_path, tmp_path/report['output']['path'])
    (raw/'ALL_GENES_GTEx_RNAseq.csv').write_text('changed')
    with pytest.raises(ValueError, match='source changed'):
        validate_gtex(tmp_path, tmp_path/report['output']['path'])


def test_answer_body_cannot_bypass_claim_validation():
    run = pipeline([result('gene:PPARG', 'gene_info')]).run(RetrievalRequest('Function of PPARG'))
    bad = GeneratedAnswer('answer', 'This target cures every disease.', [Claim('Approved evidence summary.', ['gene:PPARG'])], [], [])
    assert not validate_answer(bad, run.context).valid
    parsed = _parse_answer({'status':'answer', 'answer':bad.answer, 'claims':[{'text':'Approved evidence summary.', 'citations':['gene:PPARG']}]}, run.context, 'mock')
    assert parsed.answer == 'Approved evidence summary.'
    assert validate_answer(parsed, run.context).valid


def test_compare_uses_gene_details_schema_instead_of_missing_row_gene(monkeypatch, tmp_path):
    monkeypatch.setattr(server, '_GENE_INDEX', {'TCF7L2': {'title':'Gene TCF7L2','content':'Function','metadata':{},'citation':{}}})
    monkeypatch.setattr(server, '_COMMON_ASSOC', {'TCF7L2':[{'metadata':{'phenotype':'2hrG','bf_common':45}}]})
    monkeypatch.setattr(server, '_RARE_ASSOC', {})
    app = FastAPI()
    app.include_router(create_router(tmp_path, lambda: None, server.get_gene_details, lambda: None))
    response = TestClient(app).post('/api/analysis/compare', json={'genes':['TCF7L2'], 'phenotype':'2hrG'})
    assert response.status_code == 200
    assert response.json()['genes'][0]['associations'][0]['gene'] == 'TCF7L2'


def test_workspace_query_evidence_structured_routes_and_logs(monkeypatch, tmp_path):
    p = pipeline([result('gene:PPARG','gene_info'), result('rare:PPARG','gene_association_rare',metadata={'gene':'PPARG'})])
    monkeypatch.setattr(server, 'get_pipeline', lambda: p)
    monkeypatch.setattr(server, 'PROJECT_ROOT', tmp_path)
    client = TestClient(server.app)
    headers = {'X-Workspace-ID':'annotations'}
    response = client.post('/api/rag/query', headers=headers, json={'question':'Rare-variant evidence for PPARG','authorized_collections':['gene_association_rare']})
    assert response.status_code == 200 and response.json()['retrieved_count'] == 0
    assert client.get('/api/evidence/rare:PPARG', headers=headers).status_code == 404
    assert client.get('/api/evidence/gene:PPARG', headers=headers).status_code == 200
    assert client.get('/api/analysis/gwas', headers=headers).status_code == 403
    assert client.get('/api/health', headers={'X-Workspace-ID':'unknown'}).status_code == 422
    logs = list((tmp_path/'artifacts/runs/annotations').glob('*.json'))
    assert len(logs) == 1
    saved = json.loads(logs[0].read_text())
    assert saved['run_id'] == response.json()['run_id']
    assert saved['retrieval']['diagnostics']['workspace'] == 'annotations'


def test_api_falls_back_on_invalid_claim_citation_and_does_not_log_key(monkeypatch, tmp_path):
    p = pipeline([result('gene:PPARG','gene_info')])
    monkeypatch.setattr(server, 'get_pipeline', lambda: p)
    monkeypatch.setattr(server, 'PROJECT_ROOT', tmp_path)
    bad = SimpleNamespace(provider='fixture-hosted', generate=lambda ctx: GeneratedAnswer('answer','Unsupported',[Claim('Unsupported',['external'])],[],[]))
    monkeypatch.setattr(server, 'build_llm_generator', lambda **kwargs: bad)
    response = TestClient(server.app).post('/api/rag/query', json={'question':'Function of PPARG','api_key':'DO-NOT-LOG-THIS'})
    assert response.status_code == 200
    assert response.json()['provider'] == 'offline_fallback'
    log = next((tmp_path/'artifacts/runs/all').glob('*.json')).read_text()
    assert 'DO-NOT-LOG-THIS' not in log and 'api_key' not in log


def test_usage_and_configured_price_are_recorded():
    context = pipeline([result('gene:PPARG','gene_info')]).run(RetrievalRequest('Function of PPARG')).context
    payload = json.dumps({'status':'answer','answer':'ignored','claims':[{'text':'Approved evidence summary.','citations':['gene:PPARG']}]})
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload))], usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    generator = AIHubMixGenerator('test', client=client, input_cost_per_million=1, output_cost_per_million=2)
    usage = generator.generate(context).diagnostics['usage']
    assert usage['input_tokens'] == 100 and usage['api_calls'] == 1
    assert usage['estimated_cost_usd'] == pytest.approx(0.00014)


def test_citation_version_mismatch_is_not_silently_replaced(monkeypatch):
    p = pipeline([result('gene:PPARG','gene_info')])
    p.retriever.backend.records[0].citation['corpus_version'] = 'new'
    monkeypatch.setattr(server, 'get_pipeline', lambda: p)
    client = TestClient(server.app)
    assert client.get('/api/evidence/gene:PPARG?corpus_version=old').status_code == 409
    assert client.get('/api/evidence/gene:PPARG?corpus_version=new').status_code == 200


def test_broad_association_question_uses_source_evidence_instead_of_alphabetical_baselines():
    hits = [result('common:AAA', 'gene_association_common', metadata={'gene':'AAA','phenotype':'2hrG','bf_common':1}),
            result('common:ZZZ', 'gene_association_common', metadata={'gene':'ZZZ','phenotype':'2hrG','bf_common':100}),
            result('rare:ZZZ', 'gene_association_rare', metadata={'gene':'ZZZ','phenotype':'2hrG','is_significant':True,'pValue':0.00001,'beta':0.2})]
    run = pipeline(hits).run(RetrievalRequest('What genes are associated with 2-hour glucose (2hrG)?'))
    assert [r.chunk_id for r in run.retrieval.results] == ['common:ZZZ','rare:ZZZ']
    assert run.answer.status == 'qualified'
    assert any('not combined' in note for note in run.answer.limitations)


def test_exact_trait_pair_does_not_fill_context_with_unrelated_correlations():
    hits = [result('ldsc:2hrI:2hrFFA','ldsc_genetic_correlation', metadata={'phenotype':'2hrI','other_phenotype':'2hrFFA'}),
            result('ldsc:2hrI:OTHER','ldsc_genetic_correlation', metadata={'phenotype':'2hrI','other_phenotype':'OTHER'})]
    run = pipeline(hits).run(RetrievalRequest('What is the genetic correlation between 2hrI and 2hrFFA?'))
    assert [p.chunk_id for p in run.context.passages] == ['ldsc:2hrI:2hrFFA']


def test_uploaded_analysis_runs_do_not_cross_simulated_workspaces():
    client = TestClient(server.app)
    created = client.post('/api/analysis/matrix', headers={'X-Workspace-ID':'annotations'}, json={'matrix_csv':'gene,T1,T2\nA,1,2\nB,3,4\n', 'components':1, 'iterations':10})
    assert created.status_code == 200
    path = '/api/analysis/runs/' + created.json()['run_id'] + '/selection'
    assert client.get(path, headers={'X-Workspace-ID':'annotations'}).status_code == 200
    assert client.get(path, headers={'X-Workspace-ID':'genetics'}).status_code == 404


def test_same_size_stale_bm25_index_is_rejected(tmp_path):
    from retrieval.bm25_retriever import save_bm25_index, load_bm25_index
    record = ChunkRecord.from_dict(result('gene:PPARG','gene_info').chunk)
    index = build_bm25_index(LoadedCorpus([record], {'genes.jsonl':'old'}, {}), ('content',))
    save_bm25_index(index, tmp_path)
    with pytest.raises(ValueError, match='stale'):
        load_bm25_index(tmp_path, [record], expected_chunk_hashes={'genes.jsonl':'new'})
