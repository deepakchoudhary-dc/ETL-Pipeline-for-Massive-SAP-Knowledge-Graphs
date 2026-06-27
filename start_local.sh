#!/usr/bin/env bash
set -euo pipefail

API_PID=""
FRONTEND_PID=""

green="\033[0;32m"
blue="\033[0;34m"
reset="\033[0m"

cleanup() {
  echo -e "${blue}Stopping local services...${reset}"
  if [[ -n "${FRONTEND_PID}" ]]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" 2>/dev/null || true
  fi
}

trap cleanup SIGINT SIGTERM EXIT

echo -e "${green}Starting SAP O2C graph API on http://localhost:8000${reset}"
uvicorn graph_server.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

sleep 3

echo -e "${green}Starting Streamlit dashboard on http://localhost:8501${reset}"
streamlit run frontend/app.py --server.port 8501 &
FRONTEND_PID=$!

echo -e "${green}God-Level architecture is online.${reset}"
wait
