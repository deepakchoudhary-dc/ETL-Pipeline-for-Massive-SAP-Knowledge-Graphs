import pytest

from frontend.rag_agent import parse_sparql


def test_parse_sparql_extracts_query_block() -> None:
    output = """
    <thought_process>Find anomalous sales items.</thought_process>
    <sparql_query>
    PREFIX o2c: <http://enterprise.com/ontology/o2c#>
    SELECT ?s WHERE { ?s a o2c:PartialDeliveryAnomaly . }
    </sparql_query>
    """

    assert "SELECT ?s" in parse_sparql(output)


def test_parse_sparql_extracts_fenced_query() -> None:
    output = """
    Here is the SPARQL:
    ```sparql
    PREFIX data: <http://enterprise.com/ontology/data#>
    SELECT ?s WHERE { ?s data:productKey ?key . }
    ```
    """

    assert "data:productKey" in parse_sparql(output)


def test_parse_sparql_extracts_plain_query() -> None:
    output = "PREFIX data: <http://enterprise.com/ontology/data#>\nSELECT ?s WHERE { ?s ?p ?o . }"

    assert parse_sparql(output).startswith("PREFIX data:")


def test_parse_sparql_rejects_missing_query() -> None:
    with pytest.raises(ValueError):
        parse_sparql("I would look for product rows and descriptions.")
