from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from graph_server.application.use_cases import GetAnomaliesUseCase
from graph_server.infrastructure.rdflib_repo import KnowledgeGraphRepository


RAW_DATA_DIR = Path("data/raw")
O2C_REQUIRED_FILES = frozenset({"VBAK.csv", "VBAP.csv", "LIKP.csv", "LIPS.csv"})


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)


class QueryResponse(BaseModel):
    results: list[dict[str, str]]


class UploadResponse(BaseModel):
    status: str
    files: list[str]


class GraphTriple(BaseModel):
    subject: str
    predicate: str
    object: str
    object_is_uri: bool
    anomaly: bool


def create_router(
    get_repository: Any,
    get_anomalies_use_case: Any,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/anomalies", response_model=QueryResponse)
    async def get_anomalies(
        use_case: GetAnomaliesUseCase = Depends(get_anomalies_use_case),
    ) -> QueryResponse:
        return QueryResponse(results=await use_case.execute())

    @router.post("/api/v1/query", response_model=QueryResponse)
    async def execute_query(
        request: QueryRequest,
        repository: KnowledgeGraphRepository = Depends(get_repository),
    ) -> QueryResponse:
        return QueryResponse(results=await repository.execute_sparql(request.query))

    @router.get("/api/v1/graph-data", response_model=list[GraphTriple])
    async def graph_data(
        repository: KnowledgeGraphRepository = Depends(get_repository),
    ) -> list[GraphTriple]:
        return [GraphTriple(**row) for row in await repository.graph_data()]

    @router.post("/api/v1/upload-and-process", response_model=UploadResponse)
    async def upload_and_process(files: list[UploadFile] = File(...)) -> UploadResponse:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

        saved_files: list[str] = []
        for upload in files:
            destination = _safe_upload_path(upload.filename)
            content = await upload.read()
            destination.write_bytes(content)
            saved_files.append(destination.name)

        await asyncio.to_thread(_run_pipeline_scripts, saved_files)
        return UploadResponse(status="success", files=saved_files)

    return router


def _safe_upload_path(filename: str | None) -> Path:
    if not filename:
        raise HTTPException(status_code=400, detail="Upload filename is required.")
    clean_name = Path(filename).name
    suffix = Path(clean_name).suffix.lower()
    if suffix not in {".csv", ".json"}:
        raise HTTPException(status_code=400, detail="Only .csv and .json uploads are supported.")
    return RAW_DATA_DIR / clean_name


def _run_pipeline_scripts(saved_files: list[str]) -> None:
    normalized_files = {file_name.upper() for file_name in saved_files}
    if {file_name.upper() for file_name in O2C_REQUIRED_FILES}.issubset(normalized_files):
        _run_module("etl.materialize")
        _run_module("etl.reasoning")
        return

    uploaded_paths = [str(RAW_DATA_DIR / file_name) for file_name in saved_files]
    _run_module("etl.dynamic_materialize", uploaded_paths)


def _run_module(module_name: str, args: list[str] | None = None) -> None:
    command = [sys.executable, "-m", module_name]
    if args:
        command.extend(args)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"{module_name} failed."
        raise HTTPException(status_code=500, detail=detail[-4000:])
