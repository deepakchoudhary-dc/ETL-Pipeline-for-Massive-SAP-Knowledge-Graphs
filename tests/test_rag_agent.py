import pytest

from frontend.rag_agent import LlmSettings, fallback_sparql, generate_sparql, parse_sparql


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


def test_fallback_sparql_handles_product_questions() -> None:
    sparql = fallback_sparql("show me products and gtins")

    assert "data:productKey" in sparql
    assert "SELECT" in sparql


def test_generate_sparql_falls_back_when_llm_returns_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call_llm(*args: object, **kwargs: object) -> str:
        return "I would inspect the product table and summarize the records."

    monkeypatch.setattr("frontend.rag_agent._call_llm", fake_call_llm)

    sparql = generate_sparql(
        "show me products",
        LlmSettings(provider="ollama", model="gemma4:e4b", base_url="http://localhost:11434"),
    )

    assert "SELECT" in sparql
    assert "data:productKey" in sparql
