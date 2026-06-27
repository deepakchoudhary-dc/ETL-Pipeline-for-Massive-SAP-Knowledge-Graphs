from pathlib import Path

from fastapi.testclient import TestClient
from rdflib import Graph

from graph_server.main import app


def test_upload_accepts_generic_product_extracts_without_500() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/upload-and-process",
        files=[
            (
                "files",
                (
                    "SAP_RT_POS_L_Product.csv",
                    b"productKey,productId,merchandiseCategory\nAA1,MR411412,Digital Cameras\n",
                    "text/csv",
                ),
            ),
            (
                "files",
                (
                    "SAP_RT_POS_L_Product_Text.csv",
                    b"languageKey,productKey,description,language\nEN,AA1,10 MP Camera,EN\n",
                    "text/csv",
                ),
            ),
        ],
    )

    assert response.status_code == 200
    graph = Graph()
    graph.parse(Path("data/output/sap_graph.ttl"))
    assert len(graph) > 0
