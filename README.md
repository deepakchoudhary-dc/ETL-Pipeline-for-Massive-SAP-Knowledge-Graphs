# SAP Knowledge Graph ETL Pipeline

This project turns uploaded SAP-style tabular extracts into an RDF knowledge graph, serves it through FastAPI, and visualizes it in Streamlit.

## Features

- SAP O2C ontology and morph-kgc pipeline for `VBAK.csv`, `VBAP.csv`, `LIKP.csv`, and `LIPS.csv`.
- Dynamic RDF materialization for other SAP extracts such as product, product text, GTIN, and site tables.
- PROV-O audit trail generation for ETL runs.
- Partial delivery anomaly reasoning for O2C graphs.
- FastAPI endpoints for upload, SPARQL query execution, graph data, and anomalies.
- Streamlit dashboard with yFiles graph rendering.
- GraphRAG chat with selectable LLM providers:
  - Ollama/local LLM
  - OpenAI
  - OpenAI-compatible API

## Local Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn graph_server.main:app --host 127.0.0.1 --port 8000
```

Run the dashboard:

```bash
streamlit run frontend/app.py --server.port 8501
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8501`

## Upload Behavior

For O2C extracts, upload these files together:

- `VBAK.csv`
- `VBAP.csv`
- `LIKP.csv`
- `LIPS.csv`

For other SAP tables, upload the available CSV or JSON extracts. The dynamic materializer creates row nodes, data predicates from columns, and inferred links between rows that share key/id columns such as `productKey`.

## LLM Configuration

The Streamlit sidebar lets users choose the LLM provider.

For Ollama:

- Provider: `ollama`
- URL: `http://localhost:11434`
- Model: any installed Ollama model, for example `llama3.1`

For OpenAI:

- Provider: `openai`
- API URL: `https://api.openai.com/v1`
- API key: enter in the sidebar or set `OPENAI_API_KEY`
- Model: configurable in the sidebar

For OpenAI-compatible local or hosted APIs:

- Provider: `openai-compatible`
- API URL: the `/v1` base URL
- Model: the provider-specific model name
- API key: optional if the server does not require one

## Tests

```bash
pytest -q
```
