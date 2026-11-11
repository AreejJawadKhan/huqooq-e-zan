.PHONY: setup ingest dev-backend dev-frontend test eval demo-cache check-models

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install
	@test -f .env || cp .env.example .env
	@echo "Now put a free GEMINI_API_KEY or GROQ_API_KEY in .env"

ingest:
	.venv/bin/python scripts/ingest.py --dump-text

dev-backend:
	.venv/bin/uvicorn backend.app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	.venv/bin/python -m pytest -q

eval:
	.venv/bin/python scripts/run_eval.py -v

demo-cache:
	.venv/bin/python scripts/build_demo_cache.py

check-models:
	.venv/bin/python scripts/check_models.py
