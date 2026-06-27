from abc import ABC, abstractmethod


class IGraphRepository(ABC):
    @abstractmethod
    async def execute_sparql(self, query: str) -> list[dict[str, str]]:
        raise NotImplementedError
