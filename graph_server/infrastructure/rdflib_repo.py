from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef

from graph_server.domain.interfaces import IGraphRepository


class KnowledgeGraphRepository(IGraphRepository):
    def __init__(self, graph_path: Path = Path("data/output/sap_graph.ttl")) -> None:
        self.graph_path = graph_path
        self._graph = Graph()
        self._loaded = False
        self._mtime_ns: int | None = None

    async def execute_sparql(self, query: str) -> list[dict[str, str]]:
        return await asyncio.to_thread(self._execute_sparql_sync, query)

    async def graph_data(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._graph_data_sync)

    def _execute_sparql_sync(self, query: str) -> list[dict[str, str]]:
        self._ensure_loaded()
        result = self._graph.query(query)
        if result.type == "CONSTRUCT":
            return [
                {
                    "subject": self._format_term(subject),
                    "predicate": self._format_term(predicate),
                    "object": self._format_term(obj),
                }
                for subject, predicate, obj in result.graph.triples((None, None, None))
            ]
        return [
            {str(variable): self._format_term(row[index]) for index, variable in enumerate(result.vars)}
            for row in result
        ]

    def _graph_data_sync(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        anomaly_nodes = {
            str(subject)
            for subject in self._graph.subjects(
                URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
                URIRef("http://enterprise.com/ontology/o2c#PartialDeliveryAnomaly"),
            )
        }
        return [
            {
                "subject": str(subject),
                "predicate": str(predicate),
                "object": self._format_term(obj),
                "object_is_uri": isinstance(obj, URIRef),
                "anomaly": str(subject) in anomaly_nodes,
            }
            for subject, predicate, obj in self._graph.triples((None, None, None))
        ]

    def _ensure_loaded(self) -> None:
        if not self.graph_path.exists():
            self._graph = Graph()
            self._loaded = True
            self._mtime_ns = None
            return

        current_mtime_ns = self.graph_path.stat().st_mtime_ns
        if self._loaded and self._mtime_ns == current_mtime_ns:
            return

        graph = Graph()
        graph.parse(str(self.graph_path), format="turtle")
        self._graph = graph
        self._loaded = True
        self._mtime_ns = current_mtime_ns

    @staticmethod
    def _format_term(value: Any) -> str:
        if isinstance(value, Literal):
            return str(value)
        return str(value)
