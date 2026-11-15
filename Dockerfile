FROM python:3.12-slim
WORKDIR /studio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agents agents
COPY api api
COPY contracts contracts
COPY knowledge_base knowledge_base
COPY prompts prompts
COPY studio studio
COPY web web
ENV PYTHONUNBUFFERED=1 PYTHON_DOTENV_DISABLED=1 STUDIO_DATA_DIR=/data
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
