FROM python:3.14-slim
RUN pip install --no-cache-dir gradio==6.32.0 pytest==9.2.0
COPY entry.py /opt/runner_entry.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GRADIO_ANALYTICS_ENABLED=False GRADIO_RUN_HISTORY=False HOME=/tmp GRADIO_SERVER_PORT=7860
WORKDIR /workspace
USER 65534:65534
CMD ["python", "/opt/runner_entry.py"]
