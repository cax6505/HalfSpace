.PHONY: install ingest test api web

install:
	python3.12 -m pip install -e 'services/api[dev]'
	cd apps/web && npm install

ingest:
	cd services/api && python3.12 -m app.ingest

test:
	cd services/api && python3.12 -m pytest

api:
	cd services/api && uvicorn app.main:app --reload

web:
	cd apps/web && npm run dev
