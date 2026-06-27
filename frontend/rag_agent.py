from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import requests


API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

SCHEMA_CONTEXT = """
Prefixes:
  o2c: <http://enterprise.com/ontology/o2c#>
  data: <http://enterprise.com/ontology/data#>

O2C classes:
  o2c:SalesOrder, o2c:SalesItem, o2c:Delivery, o2c:DeliveryItem,
  o2c:Invoice, o2c:InvoiceItem, o2c:PartialDeliveryAnomaly

O2C properties:
  o2c:hasSalesItem, o2c:fulfilledByDeliveryItem, o2c:billedByInvoiceItem,
  o2c:orderedQuantity, o2c:deliveredQuantity, o2c:billedQuantity

Dynamic table graph:
  Uploaded SAP tables are represented as data:<TableName>Record classes.
  Source rows use data:sourceFile and data:sourceTable.
  Uploaded columns become data:<columnName> predicates.
  Rows with matching key/id columns are linked with data:linksBy_<keyColumn>.
"""

FEW_SHOT_EXAMPLES = """
Question: Which sales items have partial delivery anomalies?
SPARQL:
PREFIX o2c: <http://enterprise.com/ontology/o2c#>
SELECT ?sales_item WHERE { ?sales_item a o2c:PartialDeliveryAnomaly . }

Question: Show product descriptions from uploaded product text tables.
SPARQL:
PREFIX data: <http://enterprise.com/ontology/data#>
SELECT ?product_text ?description
WHERE {
  ?product_text data:sourceTable ?table ;
      data:description ?description .
  FILTER(CONTAINS(LCASE(STR(?table)), "product_text"))
}

Question: Which product records are linked to text records?
SPARQL:
PREFIX data: <http://enterprise.com/ontology/data#>
SELECT ?product ?product_text
WHERE {
  ?product data:linksBy_productkey ?product_text .
}
"""

TEXT_TO_SPARQL_SYSTEM_PROMPT = """
You translate SAP data questions into SPARQL over this fixed graph model.
Use Explain-then-Translate exactly:
1. Output a <thought_process> block that briefly explains the graph traversal.
2. Output a <sparql_query> block containing only executable SPARQL.

Do not invent prefixes outside the schema. Prefer SELECT queries.

Schema:
{schema_context}

Few-shot examples:
{few_shot_examples}
"""

SUMMARY_SYSTEM_PROMPT = """
Summarize the JSON query result for a supply-chain or master-data analyst.
Use only values present in the JSON. Do not invent counts, document IDs, dates, names, or quantities.
"""


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    model: str
    base_url: str
    api_key: str = ""


class RagConfigurationError(RuntimeError):
    pass


def settings_from_env() -> LlmSettings:
    provider = os.getenv("LLM_PROVIDER")
    if not provider:
        provider = "openai" if os.getenv("OPENAI_API_KEY") else "ollama"

    normalized_provider = provider.strip().lower()
    if normalized_provider == "openai":
        return LlmSettings(
            provider="openai",
            model=os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4.1-mini")),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
        )
    if normalized_provider == "openai-compatible":
        return LlmSettings(
            provider="openai-compatible",
            model=os.getenv("LLM_MODEL", "local-model"),
            base_url=os.getenv("LLM_API_BASE_URL", "http://localhost:8001/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
        )
    return LlmSettings(
        provider="ollama",
        model=os.getenv("OLLAMA_MODEL", os.getenv("LLM_MODEL", "gemma4:e4b")),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def answer_question(user_input: str, settings: LlmSettings | None = None) -> str:
    active_settings = settings or settings_from_env()
    sparql = generate_sparql(user_input, active_settings)
    result_json = execute_sparql(sparql)
    return summarize_result(user_input, result_json, active_settings)


def generate_sparql(user_input: str, settings: LlmSettings | None = None) -> str:
    active_settings = settings or settings_from_env()
    system_prompt = TEXT_TO_SPARQL_SYSTEM_PROMPT.format(
        schema_context=SCHEMA_CONTEXT,
        few_shot_examples=FEW_SHOT_EXAMPLES,
    )
    response = _call_llm(
        system_prompt=system_prompt,
        user_prompt=user_input,
        settings=active_settings,
    )
    return parse_sparql(response)


def execute_sparql(sparql: str) -> list[dict[str, Any]]:
    response = requests.post(f"{API_URL}/api/v1/query", json={"query": sparql}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", payload)
    if not isinstance(results, list):
        raise ValueError("SPARQL API response must contain a list of results.")
    return results


def summarize_result(
    user_input: str,
    result_json: list[dict[str, Any]],
    settings: LlmSettings | None = None,
) -> str:
    active_settings = settings or settings_from_env()
    return _call_llm(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=f"Question: {user_input}\nJSON result:\n{json.dumps(result_json, indent=2, sort_keys=True)}",
        settings=active_settings,
    )


def parse_sparql(llm_output: str) -> str:
    candidates = [
        match.group(1)
        for match in re.finditer(
            r"<sparql_query>\s*(.*?)\s*</sparql_query>",
            llm_output,
            re.DOTALL | re.IGNORECASE,
        )
    ]
    candidates.extend(
        match.group(1)
        for match in re.finditer(
            r"```(?:sparql|ttl|rdf|query)?\s*(.*?)```",
            llm_output,
            re.DOTALL | re.IGNORECASE,
        )
    )
    candidates.append(llm_output)

    for candidate in candidates:
        sparql = _extract_query_text(candidate)
        if sparql:
            return sparql

    raise ValueError("The LLM did not return a recognizable SPARQL SELECT, ASK, CONSTRUCT, or DESCRIBE query.")


def _extract_query_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""

    query_match = re.search(
        r"((?:PREFIX\s+\w+:\s*<[^>]+>\s*)*(?:SELECT|ASK|CONSTRUCT|DESCRIBE)\b.*)",
        cleaned,
        re.DOTALL | re.IGNORECASE,
    )
    if not query_match:
        return ""

    sparql = query_match.group(1).strip()
    sparql = re.sub(r"</?sparql_query>", "", sparql, flags=re.IGNORECASE).strip()
    if not sparql:
        return ""
    return sparql


def _call_llm(system_prompt: str, user_prompt: str, settings: LlmSettings) -> str:
    provider = settings.provider.lower()
    if provider == "ollama":
        return _call_ollama(system_prompt, user_prompt, settings)
    if provider in {"openai", "openai-compatible"}:
        return _call_openai_compatible(system_prompt, user_prompt, settings)
    raise RagConfigurationError(f"Unsupported LLM provider: {settings.provider}")


def _call_ollama(system_prompt: str, user_prompt: str, settings: LlmSettings) -> str:
    response = requests.post(
        f"{settings.base_url.rstrip('/')}/api/chat",
        json={
            "model": settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=120,
    )
    if response.status_code >= 400:
        raise RagConfigurationError(f"Ollama request failed: {response.text[:1000]}")
    content = response.json().get("message", {}).get("content")
    if not content:
        raise RagConfigurationError("Ollama returned an empty response.")
    return str(content)


def _call_openai_compatible(system_prompt: str, user_prompt: str, settings: LlmSettings) -> str:
    if settings.provider.lower() == "openai" and not settings.api_key:
        raise RagConfigurationError("Set OPENAI_API_KEY or choose Ollama/local LLM in the sidebar.")

    headers = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"

    response = requests.post(
        f"{settings.base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        },
        timeout=120,
    )
    if response.status_code >= 400:
        raise RagConfigurationError(f"LLM API request failed: {response.text[:1000]}")

    choices = response.json().get("choices", [])
    if not choices:
        raise RagConfigurationError("LLM API returned no choices.")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RagConfigurationError("LLM API returned an empty response.")
    return str(content)
