FROM node:22-slim AS frontend
WORKDIR /build
COPY src/frontend/spanish-ranked/package.json src/frontend/spanish-ranked/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY src/frontend/spanish-ranked/ ./
RUN npm run build

# Verb tables for conjugation and form analysis (docs/ROADMAP.md Phase 1). verbecc is only needed to
# generate them, so it stays out of the runtime image. Only the files the build script reads are
# copied, so this ~1 minute step is cached across ordinary code changes.
FROM python:3.14-slim AS verbdata
WORKDIR /build
RUN pip install --no-cache-dir verbecc==2.1.0
COPY src/backend/app/__init__.py backend/app/__init__.py
COPY src/backend/app/lexicon/__init__.py src/backend/app/lexicon/grammar_terms.py backend/app/lexicon/
COPY src/backend/scripts/build_verb_data.py backend/scripts/
RUN python backend/scripts/build_verb_data.py --out /build/verbs.db

FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/backend/ ./backend/
COPY --from=verbdata /build/verbs.db ./backend/data/verbs.db
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
