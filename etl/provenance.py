from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD


PROV = Namespace("http://www.w3.org/ns/prov#")
RUN = Namespace("http://enterprise.com/provenance/run/")
FILE = Namespace("http://enterprise.com/provenance/file/")
STATUS = Namespace("http://enterprise.com/provenance/status/")
STATUS_STATE = URIRef(STATUS["state"])


class ProvenanceLogger:
    def __init__(
        self,
        output_file: Path = Path("data/output/sap_graph.ttl"),
        audit_file: Path = Path("data/output/audit_trail.ttl"),
        agent_uri: URIRef = URIRef("http://enterprise.com/agent/etl-system"),
    ) -> None:
        self.output_file = output_file
        self.audit_file = audit_file
        self.agent_uri = agent_uri
        self.graph = Graph()
        self.activity_uri = URIRef(RUN[str(uuid4())])

    def __enter__(self) -> "ProvenanceLogger":
        self.graph.bind("prov", PROV)
        self.graph.bind("status", STATUS)
        self.graph.add((self.activity_uri, RDF.type, PROV.Activity))
        self.graph.add(
            (
                self.activity_uri,
                PROV.startedAtTime,
                Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime),
            )
        )
        return self

    def register_input(self, file_path: str | Path) -> URIRef:
        entity_uri = self._file_entity_uri(Path(file_path))
        self.graph.add((entity_uri, RDF.type, PROV.Entity))
        self.graph.add((entity_uri, PROV.value, Literal(str(file_path))))
        self.graph.add((self.activity_uri, PROV.used, entity_uri))
        return entity_uri

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        output_uri = self._file_entity_uri(self.output_file)
        self.graph.add((output_uri, RDF.type, PROV.Entity))
        self.graph.add((output_uri, PROV.value, Literal(str(self.output_file))))
        self.graph.add((output_uri, PROV.wasGeneratedBy, self.activity_uri))

        self.graph.add((self.agent_uri, RDF.type, PROV.Agent))
        self.graph.add((output_uri, PROV.wasAttributedTo, self.agent_uri))
        self.graph.add((self.activity_uri, PROV.wasAssociatedWith, self.agent_uri))
        self.graph.add(
            (
                self.activity_uri,
                PROV.endedAtTime,
                Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime),
            )
        )

        if exc_type is None:
            self.graph.add((self.activity_uri, STATUS_STATE, URIRef(STATUS["completed"])))
        else:
            self.graph.add((self.activity_uri, STATUS_STATE, URIRef(STATUS["failed"])))
            self.graph.add((self.activity_uri, PROV.value, Literal(str(exc_value))))

        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        self.graph.serialize(destination=str(self.audit_file), format="turtle")
        return False

    @staticmethod
    def _file_entity_uri(file_path: Path) -> URIRef:
        safe_path = str(file_path).replace("\\", "/").lstrip("./").replace("/", "_")
        return URIRef(FILE[safe_path])
