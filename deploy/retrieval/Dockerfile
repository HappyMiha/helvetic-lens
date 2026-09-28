FROM python:3.11-slim-bookworm
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    USE_TF=0 USE_TORCH=1 TOKENIZERS_PARALLELISM=false TORCH_DISABLE_NATIVE_JIT=1 \
    HF_HOME=/models OMP_NUM_THREADS=2 LAYA_DEVICE=cpu LAYA_MAX_CONCURRENT=4
RUN pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install transformers==5.17.0 fastapi==0.141.1 uvicorn==0.54.0 safetensors==0.8.0 && pip check
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('intfloat/multilingual-e5-small', revision='614241f622f53c4eeff9890bdc4f31cfecc418b3', allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','sentencepiece.bpe.model','README.md'])"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
RUN useradd --uid 10001 --create-home retrieval && chmod -R a+rX /models
COPY server.py /opt/retrieval/server.py
COPY THIRD_PARTY_NOTICES.md /opt/retrieval/THIRD_PARTY_NOTICES.md
USER retrieval
EXPOSE 8000
CMD ["python", "/opt/retrieval/server.py"]
