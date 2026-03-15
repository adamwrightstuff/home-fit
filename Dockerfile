# Railway API: use this so Python is on PATH at runtime (fixes "python3: command not found").
# In Railway: Settings → Build → set Builder to "Dockerfile" if it doesn't auto-detect.

FROM python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create data_cache and build NRHP DB at image build time (optional; app works without it)
RUN mkdir -p data_cache && python3 scripts/build_nrhp_db.py --out data_cache/nrhp.sqlite || true

# Railway sets PORT at runtime
EXPOSE 8000
CMD python3 -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
