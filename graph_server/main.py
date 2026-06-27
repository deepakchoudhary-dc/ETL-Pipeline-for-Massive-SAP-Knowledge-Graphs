from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI

from graph_server.application.use_cases import GetAnomaliesUseCase
from graph_server.infrastructure.rdflib_repo import KnowledgeGraphRepository
from graph_server.presentation.routes import create_router


@lru_cache
def get_repository() -> KnowledgeGraphRepository:
    return KnowledgeGraphRepository()


def get_anomalies_use_case() -> GetAnomaliesUseCase:
    return GetAnomaliesUseCase(get_repository())


app = FastAPI(title="SAP O2C Knowledge Graph API")
app.include_router(create_router(get_repository, get_anomalies_use_case))
