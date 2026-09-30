.PHONY: install ml-install ingest test api web label train evaluate export-onnx index eval-search promptfoo-search annotate-search scout-benchmark mcp demo-up demo-down e2e eval-gate

install:
	python3.12 -m pip install -e 'services/api[dev]'
	python3.12 -m pip install -r ml/requirements.txt
	cd apps/web && npm install

ml-install:
	python3.12 -m pip install -r ml/requirements.txt

ingest:
	cd services/api && python3.12 -m app.ingest

test:
	cd services/api && python3.12 -m pytest

api:
	cd services/api && python3.12 -m app.start

web:
	cd apps/web && npm run dev

demo-up:
	docker compose up --build -d postgres redis api web

demo-down:
	docker compose down

e2e:
	cd apps/web && npx playwright install chromium && npm run test:e2e

eval-gate:
	python3 services/api/evals/check_fixtures.py

label:
	python3.12 ml/label.py --count 200

train:
	SEED=17 python3.12 ml/train.py

evaluate:
	python3.12 ml/evaluate.py

export-onnx:
	python3.12 ml/export_onnx.py

index:
	python3.12 ml/index_pgvector.py

eval-search:
	cd services/api && python3.12 evals/evaluate_search.py

promptfoo-search:
	cd services/api/evals && npx --yes promptfoo@latest eval -c promptfooconfig.yaml

annotate-search:
	cd services/api && python3.12 evals/annotate_relevance.py

scout-benchmark:
	cd services/api && python3.12 evals/run_scout_benchmark.py

mcp:
	cd services/api && python3.12 -m app.mcp_server
