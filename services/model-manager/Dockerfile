FROM ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:031c0058432ab0769057273cdfda45848d00fef11e993448eef98c7ebb45a8c6

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /manager
COPY services/model-manager/requirements.txt ./
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt
COPY services/model-manager/model_manager ./model_manager
COPY services/model-manager/catalog.json ./catalog.json
COPY deploy/apertus-v1-chat-template.jinja /templates/apertus-v1-chat-template.jinja
ENV PATH="/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/app"
ENV MODEL_MANAGER_CATALOG=/manager/catalog.json
ENV MODEL_MANAGER_LIBRARY=/models
ENV MODEL_MANAGER_LLAMA_SERVER=/app/llama-server
ENV MODEL_MANAGER_RUNTIME_IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:031c0058432ab0769057273cdfda45848d00fef11e993448eef98c7ebb45a8c6"
EXPOSE 8090 8080
ENTRYPOINT []
CMD ["uvicorn", "model_manager.app:app", "--host", "0.0.0.0", "--port", "8090"]
