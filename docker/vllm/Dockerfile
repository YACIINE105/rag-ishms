FROM vllm/vllm-openai:v0.30.0@sha256:5f5e535216848d0c52159c8c13a0af04be5f6fe1a84e79914300610796f76d40

# Match the existing separate vLLM environment's 4-bit loader.
RUN python3 -m pip install --no-cache-dir --no-deps \
    vllm-bnb-plugin==0.0.3 bitsandbytes==0.50.2

COPY docker/vllm/serve.py /opt/rag-ishms/serve.py
COPY docker/release/models.json /opt/rag-ishms/models.json

ENV HF_HOME=/models \
    HF_HUB_DISABLE_XET=1 \
    VLLM_NO_USAGE_STATS=1 \
    OMP_NUM_THREADS=4

LABEL org.opencontainers.image.source="https://github.com/YACIINE105/rag-ishms" \
    org.opencontainers.image.description="Qwen generation and BGE reranking runtime; pinned Hugging Face weights download to a volume" \
    io.rag-ishms.generator.url="https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/tree/cdbee75f17c01a7cc42f958dc650907174af0554"

ENTRYPOINT ["python3", "/opt/rag-ishms/serve.py"]
CMD ["generator"]
