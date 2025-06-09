#!/bin/bash

CONFIG_FILE=./config/config.json
PORT=$(jq -r '.chatbot_api_port' "$CONFIG_FILE")



PYTHONPATH="$(pwd)/src" \
CONFIG_PATH=$CONFIG_FILE \
uvicorn src.chatbot:app --host 0.0.0.0 --port "$PORT" --reload