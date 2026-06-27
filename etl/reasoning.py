from __future__ import annotations

from pathlib import Path

from rdflib import Graph


DEFAULT_GRAPH_PATH = Path("data/output/sap_graph.ttl")

PARTIAL_DELIVERY_CONSTRUCT = """
PREFIX o2c: <http://enterprise.com/ontology/o2c#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

CONSTRUCT {
  ?sales_item a o2c:PartialDeliveryAnomaly .
}
WHERE {
  ?sales_item a o2c:SalesItem ;
      o2c:orderedQuantity ?ordered_quantity .

  {
    SELECT ?sales_item (SUM(?delivered_value) AS ?delivered_total)
    WHERE {
      ?sales_item a o2c:SalesItem .
      OPTIONAL {
        ?sales_item o2c:fulfilledByDeliveryItem ?delivery_item .
        ?delivery_item o2c:deliveredQuantity ?raw_delivered_quantity .
      }
      BIND(COALESCE(xsd:decimal(?raw_delivered_quantity), "0"^^xsd:decimal) AS ?delivered_value)
    }
    GROUP BY ?sales_item
  }
  FILTER (xsd:decimal(?ordered_quantity) > ?delivered_total)
}
"""


def apply_partial_delivery_reasoning(graph: Graph) -> Graph:
    inferred = graph.query(PARTIAL_DELIVERY_CONSTRUCT)
    for triple in inferred:
        graph.add(triple)
    return graph


def reason_over_file(graph_path: Path = DEFAULT_GRAPH_PATH) -> Graph:
    graph = Graph()
    graph.parse(str(graph_path), format="turtle")
    apply_partial_delivery_reasoning(graph)
    graph.serialize(destination=str(graph_path), format="turtle")
    return graph


def main() -> None:
    reason_over_file()


if __name__ == "__main__":
    main()
