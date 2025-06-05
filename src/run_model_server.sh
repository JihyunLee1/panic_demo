python -m vllm.entrypoints.openai.api_server \
    --model ./model/checkpoint-5500_merged \
    --served-model-name pacer \
    --host 0.0.0.0 \
    --port 8001 \
    --dtype float16 \
    --tensor-parallel-size 2 \
    --max-model-len 512 \
    --kv-cache-dtype fp8