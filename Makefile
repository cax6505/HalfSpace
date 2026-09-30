.PHONY: install ml-install ingest test api web label train evaluate export-onnx index

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
	cd services/api && uvicorn app.main:app --reload

web:
	cd apps/web && npm run dev

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
