from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from etl.provenance import ProvenanceLogger


DATA = Namespace("http://enterprise.com/ontology/data#")
RESOURCE = "http://enterprise.com/resource/data"
DEFAULT_OUTPUT_PATH = Path("data/output/sap_graph.ttl")


def materialize_files(file_paths: list[Path], output_path: Path = DEFAULT_OUTPUT_PATH) -> Graph:
    graph = Graph()
    graph.bind("data", DATA)

    tables = [_load_table(file_path) for file_path in file_paths]
    row_indexes: dict[str, dict[str, dict[str, list[URIRef]]]] = {}

    for table in tables:
        table_index: dict[str, dict[str, list[URIRef]]] = {}
        class_uri = DATA[f"{_to_pascal_case(table.name)}Record"]
        graph.add((class_uri, RDF.type, DATA.TableClass))

        for row_number, row in table.frame.iterrows():
            row_uri = _row_uri(table.name, row_number, row)
            graph.add((row_uri, RDF.type, class_uri))
            graph.add((row_uri, DATA.sourceFile, Literal(table.file_path.name)))
            graph.add((row_uri, DATA.sourceTable, Literal(table.name)))

            for column in table.frame.columns:
                value = row[column]
                if pd.isna(value) or str(value).strip() == "":
                    continue
                predicate = DATA[_safe_name(column)]
                graph.add((row_uri, predicate, _literal(value)))
                table_index.setdefault(_normalize_column(column), {}).setdefault(str(value), []).append(row_uri)

        row_indexes[table.name] = table_index

    _add_inferred_links(graph, tables, row_indexes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(output_path), format="turtle")
    return graph


def main(argv: list[str] | None = None) -> None:
    raw_args = sys.argv[1:] if argv is None else argv
    file_paths = [Path(arg) for arg in raw_args]
    if not file_paths:
        file_paths = sorted(path for path in Path("data/raw").glob("*") if path.suffix.lower() in {".csv", ".json"})

    with ProvenanceLogger(output_file=DEFAULT_OUTPUT_PATH) as provenance:
        for file_path in file_paths:
            provenance.register_input(file_path)
        materialize_files(file_paths)


class Table:
    def __init__(self, name: str, file_path: Path, frame: pd.DataFrame) -> None:
        self.name = name
        self.file_path = file_path
        self.frame = frame


def _load_table(file_path: Path) -> Table:
    if file_path.suffix.lower() == ".csv":
        frame = pd.read_csv(file_path, sep=None, engine="python")
    elif file_path.suffix.lower() == ".json":
        frame = _read_json(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path.name}")

    frame.columns = [str(column).strip() for column in frame.columns]
    return Table(name=_safe_name(file_path.stem), file_path=file_path, frame=frame)


def _read_json(file_path: Path) -> pd.DataFrame:
    try:
        return pd.read_json(file_path)
    except ValueError:
        return pd.read_json(file_path, lines=True)


def _row_uri(table_name: str, row_number: int, row: pd.Series) -> URIRef:
    key_columns = _key_columns(row.index)
    if key_columns:
        key = "__".join(str(row[column]) for column in key_columns if not pd.isna(row[column]))
    else:
        key = str(row_number + 1)
    return URIRef(f"{RESOURCE}/{quote(table_name)}/{quote(key)}")


def _key_columns(columns: pd.Index) -> list[str]:
    candidates = [
        str(column)
        for column in columns
        if _normalize_column(str(column)).endswith("key") or _normalize_column(str(column)).endswith("id")
    ]
    return candidates[:3]


def _add_inferred_links(
    graph: Graph,
    tables: list[Table],
    row_indexes: dict[str, dict[str, dict[str, list[URIRef]]]],
) -> None:
    for source_table in tables:
        for target_table in tables:
            if source_table.name == target_table.name:
                continue
            shared_columns = set(row_indexes[source_table.name]).intersection(row_indexes[target_table.name])
            for column in sorted(shared_columns):
                if not _is_join_column(column):
                    continue
                predicate = DATA[f"linksBy_{_safe_name(column)}"]
                target_index = row_indexes[target_table.name][column]
                for value, source_rows in row_indexes[source_table.name][column].items():
                    for source_uri in source_rows:
                        for target_uri in target_index.get(value, []):
                            if source_uri != target_uri:
                                graph.add((source_uri, predicate, target_uri))


def _is_join_column(column: str) -> bool:
    return column.endswith("key") or column.endswith("id")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "unnamed"
    if cleaned[0].isdigit():
        return f"c_{cleaned}"
    return cleaned


def _normalize_column(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _to_pascal_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in _safe_name(value).split("_") if part)


def _literal(value: object) -> Literal:
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.decimal)
    return Literal(str(value))


if __name__ == "__main__":
    main()
