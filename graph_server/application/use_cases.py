from __future__ import annotations

from graph_server.domain.interfaces import IGraphRepository


ANOMALIES_QUERY = """
PREFIX o2c: <http://enterprise.com/ontology/o2c#>

SELECT ?sales_item ?ordered_quantity
WHERE {
  ?sales_item a o2c:PartialDeliveryAnomaly ;
      o2c:orderedQuantity ?ordered_quantity .
}
ORDER BY ?sales_item
"""


class GetAnomaliesUseCase:
    def __init__(self, repository: IGraphRepository) -> None:
        self.repository = repository

    async def execute(self) -> list[dict[str, str]]:
        return await self.repository.execute_sparql(ANOMALIES_QUERY)
