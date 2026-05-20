# Trovamo

We find your place.

Trovamo is a neighborhood scoring and discovery platform. Enter any address or neighborhood and get a livability score across 13 pillars — from social fabric and natural beauty to school quality and climate risk.

## Stack

- Frontend: Next.js, Tailwind CSS, deployed on Vercel
- Backend: FastAPI, deployed on Railway
- Data: OSM, Google Places, custom scoring pipeline

## Dev

```bash
# Backend
PYTHONPATH=. python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Tests
pytest tests/

# Score a location
curl "http://localhost:8000/score?location=Seattle,WA"
```

### Requirements

See [requirements.txt](./requirements.txt) for Python dependencies.
