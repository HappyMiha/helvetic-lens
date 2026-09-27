FROM python:3.11-slim-bookworm
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    USE_TF=0 USE_TORCH=1 TOKENIZERS_PARALLELISM=false TORCH_DISABLE_NATIVE_JIT=1 \
    HF_HOME=/models OMP_NUM_THREADS=2 LAYA_DEVICE=cpu LAYA_MAX_CONCURRENT=4
RUN pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install 'laya[serve] @ https://github.com/NandhaKishorM/laya/archive/4066d5d5fbf08b66c6757ddeedbd797bd7655bc0.tar.gz' && pip check
RUN useradd --uid 10001 --create-home laya && mkdir /models && chown laya:laya /models
COPY server.py /opt/laya/server.py
USER laya
EXPOSE 8000
CMD ["python", "/opt/laya/server.py"]
