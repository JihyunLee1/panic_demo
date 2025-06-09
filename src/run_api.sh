#!/bin/bash

CONFIG_FILE=./demo_chat_config_kor.json
PORT=$(jq -r '.chat_api_port' "$CONFIG_FILE")

CONFIG_PATH=./demo_chat_config_kor.json uvicorn chatbot:app --reload --port 8000