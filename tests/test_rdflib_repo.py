from pathlib import Path
import asyncio

from graph_server.infrastructure.rdflib_repo import KnowledgeGraphRepository


def test_repository_executes_select_query(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.ttl"
    graph_path.write_text(
        """
        @prefix o2c: <http://enterprise.com/ontology/o2c#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        <http://enterprise.com/resource/sales-item/1-10>
            a o2c:PartialDeliveryAnomaly ;
            o2c:orderedQuantity "10"^^xsd:decimal .
        """,
        encoding="utf-8",
    )
    repository = KnowledgeGraphRepository(graph_path)

    rows = asyncio.run(
        repository.execute_sparql(
            """
            PREFIX o2c: <http://enterprise.com/ontology/o2c#>
            SELECT ?sales_item WHERE { ?sales_item a o2c:PartialDeliveryAnomaly . }
            """
        )
    )

    assert rows == [{"sales_item": "http://enterprise.com/resource/sales-item/1-10"}]
