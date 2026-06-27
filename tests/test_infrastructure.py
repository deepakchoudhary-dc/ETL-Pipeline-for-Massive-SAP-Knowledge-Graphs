from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_defines_api_and_frontend_services():
    config = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    services = {service["name"]: service for service in config["services"]}

    api = services["sap-o2c-graph-api"]
    assert api["type"] == "web"
    assert api["env"] == "python"
    assert api["buildCommand"] == "pip install -r requirements.txt"
    assert api["startCommand"] == (
        "uvicorn graph_server.main:app --host 0.0.0.0 --port 8000"
    )

    frontend = services["sap-o2c-frontend"]
    assert frontend["type"] == "web"
    assert frontend["env"] == "python"
    assert frontend["buildCommand"] == "pip install -r requirements.txt"
    assert frontend["startCommand"] == "streamlit run frontend/app.py --server.port 8501"
    assert frontend["envVars"] == [
        {
            "key": "API_URL",
            "value": "http://sap-o2c-graph-api:8000",
        }
    ]


def test_requirements_cover_runtime_and_test_dependencies():
    package_names = {
        line.split("==", 1)[0]
        .split(">=", 1)[0]
        .split("<", 1)[0]
        .split("[", 1)[0]
        .lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }

    assert {
        "fastapi",
        "uvicorn",
        "streamlit",
        "pandas",
        "rdflib",
        "morph-kgc",
        "requests",
        "yfiles-graphs-for-streamlit",
        "pytest",
        "httpx",
    }.issubset(package_names)


def test_local_start_script_manages_both_processes():
    script = (ROOT / "start_local.sh").read_text(encoding="utf-8")

    assert "trap cleanup SIGINT SIGTERM EXIT" in script
    assert "uvicorn graph_server.main:app" in script
    assert "sleep 3" in script
    assert "streamlit run frontend/app.py" in script
    assert "kill \"${FRONTEND_PID}\"" in script
    assert "kill \"${API_PID}\"" in script
    assert "\\033[" in script
    assert "God-Level architecture is online" in script


def test_gitignore_excludes_private_and_generated_files():
    patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "/*.md" in patterns
    assert "!/README.md" in patterns
    assert ".env" in patterns
    assert "__pycache__/" in patterns
    assert ".pytest_cache/" in patterns
    assert ".venv/" in patterns
    assert "data/raw/*" in patterns
    assert "data/output/*" in patterns
