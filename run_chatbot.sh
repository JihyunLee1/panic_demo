#!/bin/bash

CONFIG_FILE=./config/config.json
PORT=$(jq -r '.chatbot_api_port' "$CONFIG_FILE")



openssl req -x509 -newkey rsa:2048 -sha256 -days 365 \
            -nodes -out cert.pem -keyout key.pem \
            -subj "/CN=localhost"

PYTHONPATH="$(pwd)/src" \
CONFIG_PATH=$CONFIG_FILE \
uvicorn src.chatbot:app --host 0.0.0.0 --port "$PORT" \
       --ssl-certfile cert.pem --ssl-keyfile key.pem



# uvicorn src.chatbot:app --host 0.0.0.0 --port "$PORT" --reload

