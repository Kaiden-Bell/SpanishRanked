FROM node:22-slim AS frontend
WORKDIR /build
COPY src/frontend/spanish-ranked/package.json src/frontend/spanish-ranked/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY src/frontend/spanish-ranked/ ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/backend/ ./backend/
COPY --from=frontend /build/dist ./frontend-dist

RUN useradd --system --uid 10001 languageai \
    && mkdir /data \
    && chown languageai /data
USER languageai

ENV LANGUAGEAI_DATA_DIR=/data \
    LANGUAGEAI_FRONTEND_DIST=/app/frontend-dist
VOLUME /data
EXPOSE 8000
# Liveness only (database). A slow model must never make Docker restart a healthy app.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
