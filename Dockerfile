FROM python:3.12-slim
WORKDIR /app
COPY app/ ./app/
COPY data/ ./data/
COPY assets/ ./assets/
COPY index.html ./
COPY BUGS.md README.md ./
COPY run.sh ./
RUN useradd -m appuser && mkdir -p /app/dist /app/state \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
# Default: serve the page. The checker service overrides this with
# `python app/scheduler.py` (see docker-compose.yml).
CMD ["python", "app/serve.py"]
