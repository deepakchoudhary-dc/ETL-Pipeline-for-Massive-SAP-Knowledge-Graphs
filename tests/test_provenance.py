from pathlib import Path

from rdflib import Graph, URIRef

from etl.provenance import PROV, STATUS, STATUS_STATE, ProvenanceLogger


def test_provenance_logger_records_success(tmp_path: Path) -> None:
    output_file = tmp_path / "sap_graph.ttl"
    audit_file = tmp_path / "audit_trail.ttl"
    input_file = tmp_path / "VBAK.csv"
    input_file.write_text("VBELN\n1\n", encoding="utf-8")

    with ProvenanceLogger(output_file=output_file, audit_file=audit_file) as provenance:
        provenance.register_input(input_file)

    graph = Graph()
    graph.parse(audit_file)

    assert (None, STATUS_STATE, URIRef(STATUS["completed"])) in graph
    assert (None, PROV.used, None) in graph
    assert (None, PROV.wasGeneratedBy, None) in graph


def test_provenance_logger_records_failure(tmp_path: Path) -> None:
    audit_file = tmp_path / "audit_trail.ttl"

    try:
        with ProvenanceLogger(audit_file=audit_file):
            raise RuntimeError("pipeline failed")
    except RuntimeError:
        pass

    graph = Graph()
    graph.parse(audit_file)

    assert (None, STATUS_STATE, URIRef(STATUS["failed"])) in graph
