from __future__ import annotations

from pathlib import Path

import morph_kgc
from rdflib import Graph

from etl.provenance import ProvenanceLogger


DEFAULT_CONFIG_PATH = Path("etl/config.ini")
DEFAULT_OUTPUT_PATH = Path("data/output/sap_graph.ttl")
DEFAULT_RAW_DATA_PATH = Path("data/raw")


def materialize_graph(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Graph:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph: Graph = morph_kgc.materialize(str(config_path))
    graph.serialize(destination=str(output_path), format="turtle")
    return graph


def main() -> None:
    with ProvenanceLogger(output_file=DEFAULT_OUTPUT_PATH) as provenance:
        for input_file in sorted(DEFAULT_RAW_DATA_PATH.glob("*")):
            if input_file.is_file():
                provenance.register_input(input_file)
        provenance.register_input(DEFAULT_CONFIG_PATH)
        materialize_graph()


if __name__ == "__main__":
    main()
