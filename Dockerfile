FROM python:3.13-slim AS api
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements/api.txt transformers huggingface-hub
COPY . .
RUN useradd --uid 10001 --create-home bioagent && chown -R bioagent:bioagent /app
USER bioagent
ENV PYTHONUNBUFFERED=1 HF_HOME=/app/artifacts/model-cache
EXPOSE 8000
HEALTHCHECK --start-period=180s --interval=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=10)"
CMD ["python", "deploy/start_api.py"]
