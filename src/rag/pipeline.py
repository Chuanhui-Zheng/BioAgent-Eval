from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from augmentation.builder import ContextBuilder
from generation.provider import GeneratorProvider
from generation.schema import GeneratedAnswer
from generation.validator import ValidationResult, validate_answer
from retrieval.service import RetrievalRequest, RetrievalResponse, RetrieverService


@dataclass
class RAGRun:
    run_id: str
    created_at: str
    retrieval: RetrievalResponse
    context: Any
    answer: GeneratedAnswer
    validation: ValidationResult
    latency_s: dict[str, float]


@dataclass
class RAGPipeline:
    retriever: RetrieverService
    context_builder: ContextBuilder
    generator: GeneratorProvider

    def run(self, request: RetrievalRequest) -> RAGRun:
        started = time.perf_counter()
        retrieval = self.retriever.retrieve(request)
        after_retrieval = time.perf_counter()
        context = self.context_builder.build(retrieval)
        after_context = time.perf_counter()
        answer = self.generator.generate(context)
        validation = validate_answer(answer, context)
        if not validation.valid:
            answer = GeneratedAnswer(
                status="error",
                answer="The generated response failed evidence validation.",
                claims=[],
                citations=[],
                limitations=validation.errors,
            )
        finished = time.perf_counter()
        seed = f"{request.question}|{time.time_ns()}".encode()
        return RAGRun(
            run_id=hashlib.sha256(seed).hexdigest()[:16],
            created_at=datetime.now(timezone.utc).isoformat(),
            retrieval=retrieval,
            context=context,
            answer=answer,
            validation=validation,
            latency_s={
                "retrieval": after_retrieval - started,
                "augmentation": after_context - after_retrieval,
                "generation_and_validation": finished - after_context,
                "total": finished - started,
            },
        )

    @staticmethod
    def save_run(run: RAGRun, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{run.run_id}.json"
        path.write_text(json.dumps(asdict(run), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
