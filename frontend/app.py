from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

from frontend import rag_agent

try:
    from yfiles_graphs_for_streamlit import Edge, Node, StreamlitGraphWidget
except ImportError:
    Edge = None  # type: ignore[assignment]
    Node = None  # type: ignore[assignment]
    StreamlitGraphWidget = None  # type: ignore[assignment]


API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")


def fetch_graph_data() -> list[dict[str, Any]]:
    response = requests.get(f"{API_URL}/api/v1/graph-data", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Graph data endpoint must return a list.")
    return payload


def upload_and_process(uploaded_files: list[Any]) -> None:
    files = [
        ("files", (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream"))
        for uploaded_file in uploaded_files
    ]
    response = requests.post(f"{API_URL}/api/v1/upload-and-process", files=files, timeout=300)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))


def llm_settings_from_sidebar() -> rag_agent.LlmSettings:
    st.header("LLM")
    providers = ["ollama", "openai", "openai-compatible"]
    configured_provider = os.getenv("LLM_PROVIDER", "ollama")
    if configured_provider not in providers:
        configured_provider = "ollama"
    provider = st.selectbox(
        "Provider",
        options=providers,
        index=providers.index(configured_provider),
    )

    if provider == "ollama":
        model = st.text_input("Model", value=os.getenv("OLLAMA_MODEL", os.getenv("LLM_MODEL", "gemma4:e4b")))
        base_url = st.text_input("Ollama URL", value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        return rag_agent.LlmSettings(provider=provider, model=model, base_url=base_url)

    if provider == "openai":
        model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4.1-mini")))
        api_key = st.text_input("API key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
        base_url = st.text_input("API URL", value=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        return rag_agent.LlmSettings(provider=provider, model=model, base_url=base_url, api_key=api_key)

    model = st.text_input("Model", value=os.getenv("LLM_MODEL", "local-model"))
    base_url = st.text_input("API URL", value=os.getenv("LLM_API_BASE_URL", "http://localhost:8001/v1"))
    api_key = st.text_input("API key", value=os.getenv("LLM_API_KEY", ""), type="password")
    return rag_agent.LlmSettings(provider=provider, model=model, base_url=base_url, api_key=api_key)


def build_yfiles_elements(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    if Node is None or Edge is None:
        return [], []

    nodes_by_id: dict[str, Any] = {}
    edges: list[Any] = []

    for index, row in enumerate(rows):
        subject = str(row["subject"])
        obj = str(row["object"])
        predicate = str(row["predicate"])

        nodes_by_id.setdefault(subject, _make_node(subject, bool(row.get("anomaly"))))
        if row.get("object_is_uri"):
            nodes_by_id.setdefault(obj, _make_node(obj, False))
            edges.append(_make_edge(f"edge-{index}", subject, obj, predicate))

    return list(nodes_by_id.values()), edges


def render_graph(rows: list[dict[str, Any]]) -> None:
    if StreamlitGraphWidget is None:
        st.warning("Install yfiles-graphs-for-streamlit to render the interactive graph.")
        st.dataframe(rows, use_container_width=True)
        return

    nodes, edges = build_yfiles_elements(rows)
    widget = StreamlitGraphWidget(
        nodes=nodes,
        edges=edges,
        node_label_mapping="label",
        node_color_mapping="color",
        edge_label_mapping="label",
        directed_mapping=lambda edge: True,
    )
    widget.hierarchic_layout()
    widget.show()


def _make_node(node_id: str, anomaly: bool) -> Any:
    color = "#C1121F" if anomaly else "#386641"
    label = node_id.rsplit("/", 1)[-1]
    return Node(
        id=node_id,
        properties={
            "label": label,
            "color": color,
            "anomaly": anomaly,
        },
    )


def _make_edge(edge_id: str, source: str, target: str, predicate: str) -> Any:
    label = predicate.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return Edge(
        start=source,
        end=target,
        id=edge_id,
        properties={"label": label},
    )


def main() -> None:
    st.set_page_config(page_title="SAP O2C Knowledge Graph", layout="wide")
    st.title("SAP O2C Knowledge Graph")

    with st.sidebar:
        llm_settings = llm_settings_from_sidebar()
        st.divider()
        st.header("Data Ingestion")
        uploaded_files = st.file_uploader(
            "Upload SAP extracts",
            type=["csv", "json"],
            accept_multiple_files=True,
        )
        if st.button("Run ETL & Update Graph", disabled=not uploaded_files):
            with st.spinner("Materializing graph and applying reasoning..."):
                try:
                    upload_and_process(uploaded_files or [])
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    st.cache_data.clear()
                    st.session_state["graph_refresh_token"] = st.session_state.get("graph_refresh_token", 0) + 1
                    st.toast("Knowledge graph updated.")
                    st.success("Knowledge graph updated.")

    rows = _cached_graph_data(st.session_state.get("graph_refresh_token", 0))
    render_graph(rows)

    question = st.chat_input("Ask about the graph")
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Querying the knowledge graph..."):
                try:
                    st.write(rag_agent.answer_question(question, llm_settings))
                except (rag_agent.RagConfigurationError, requests.RequestException, ValueError) as exc:
                    st.error(str(exc))


@st.cache_data(show_spinner=False)
def _cached_graph_data(refresh_token: int) -> list[dict[str, Any]]:
    del refresh_token
    return fetch_graph_data()


if __name__ == "__main__":
    main()
