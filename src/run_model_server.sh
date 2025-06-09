#!/bin/bash

CONFIG_FILE=demo_chat_config_kor.json

# jq를 사용하여 config에서 값 읽기
MAX_MODEL_LEN=$(jq -r '.max_model_length' "$CONFIG_FILE")
PORT=$(jq -r '.vllm_server_port' "$CONFIG_FILE")
MODEL_PATH=$(jq -r '.vllm_model_path' "$CONFIG_FILE")
MODEL_NAME=$(jq -r '.vllm_model_name' "$CONFIG_FILE")

# 고정 설정값
DTYPE="float16"
TP_SIZE=2
KV_CACHE_DTYPE="fp8"

# 모델 서버 실행
python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$MODEL_NAME" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --dtype "$DTYPE" \
    --tensor-parallel-size "$TP_SIZE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --kv-cache-dtype "$KV_CACHE_DTYPE"