from __future__ import annotations

import os
import time

import numpy as np
import torch
from sqlalchemy import create_engine, text

from data import collate
from model import SequenceEncoder


def main():
    url=os.getenv("DATABASE_URL", "postgresql+psycopg://halfspace:halfspace@localhost:5432/halfspace")
    engine=create_engine(url); checkpoint=torch.load(os.getenv("ARTIFACT_DIR", "ml/artifacts")+"/encoder.pt", map_location="cpu", weights_only=False)
    model=SequenceEncoder().eval(); model.load_state_dict(checkpoint["state_dict"])
    with engine.begin() as conn:
        rows=conn.execute(text("SELECT id,tokens FROM sequences ORDER BY id")).mappings().all()
        vectors=[]
        with torch.no_grad():
            for row in rows: vectors.append(model(*collate([{"tokens":row["tokens"]}])).numpy()[0])
        for row, vector in zip(rows,vectors):
            value="["+",".join(f"{v:.8f}" for v in vector.tolist())+"]"
            conn.execute(text("UPDATE sequences SET embedding=CAST(:v AS vector) WHERE id=:id"), {"v":value,"id":row["id"]})
        conn.execute(text("DROP INDEX IF EXISTS sequences_embedding_hnsw"))
        conn.execute(text("CREATE INDEX sequences_embedding_hnsw ON sequences USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=128) WHERE embedding IS NOT NULL"))
    sample=np.asarray(vectors, dtype=np.float32)
    if len(sample)<2: raise SystemExit("Need at least two stored sequence embeddings to evaluate HNSW")
    rng=np.random.default_rng(17); query_indices=rng.choice(len(sample), min(100,len(sample)), replace=False)
    results=[]
    for m in (8,16,32):
        with engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS sequences_embedding_hnsw"))
            conn.execute(text(f"CREATE INDEX sequences_embedding_hnsw ON sequences USING hnsw (embedding vector_cosine_ops) WITH (m={m}, ef_construction=128) WHERE embedding IS NOT NULL"))
        for ef in (20,50,100):
            recalls=[]; latencies=[]
            with engine.connect() as conn:
                conn.execute(text(f"SET hnsw.ef_search = {ef}"))
                for idx in query_indices:
                    q="["+",".join(f"{v:.8f}" for v in sample[idx].tolist())+"]"
                    conn.execute(text("SET LOCAL enable_indexscan = off"))
                    exact=conn.execute(text("SELECT id FROM sequences WHERE embedding IS NOT NULL AND id != :id ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"),{"q":q,"id":int(rows[idx]["id"])}).scalars().all()
                    conn.execute(text("SET LOCAL enable_indexscan = on"))
                    start=time.perf_counter(); approximate=conn.execute(text("SELECT id FROM sequences WHERE embedding IS NOT NULL AND id != :id ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"),{"q":q,"id":int(rows[idx]["id"])}).scalars().all(); latencies.append((time.perf_counter()-start)*1000)
                    recalls.append(len(set(exact)&set(approximate))/max(1,len(exact)))
            result={"m":m,"ef_search":ef,"recall_at_10":float(np.mean(recalls)),"latency_ms_p50":float(np.percentile(latencies,50)),"latency_ms_p95":float(np.percentile(latencies,95))}; results.append(result)
            print(result)
    from pathlib import Path
    best=max(results, key=lambda r: (r["recall_at_10"], -r["latency_ms_p95"]))
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS sequences_embedding_hnsw"))
        conn.execute(text(f"CREATE INDEX sequences_embedding_hnsw ON sequences USING hnsw (embedding vector_cosine_ops) WITH (m={best['m']}, ef_construction=128) WHERE embedding IS NOT NULL"))
    from sqlalchemy import text as sql_text
    with engine.begin() as conn: conn.execute(sql_text(f"SET hnsw.ef_search = {best['ef_search']}"))
    md=["# pgvector HNSW benchmark", "", f"Measured against exact cosine neighbors over {len(vectors)} sequence embeddings; query sample size {len(query_indices)}.", "", "| m | ef_search | Recall@10 | p50 latency (ms) | p95 latency (ms) |", "|---:|---:|---:|---:|---:|"]
    md += [f"| {r['m']} | {r['ef_search']} | {r['recall_at_10']:.3f} | {r['latency_ms_p50']:.3f} | {r['latency_ms_p95']:.3f} |" for r in results]
    md += ["", f"Selected index parameters: `m={best['m']}`; set `hnsw.ef_search={best['ef_search']}` per database session for the measured operating point.", ""]
    doc=Path("docs/EVALS.md"); existing=doc.read_text() if doc.exists() else "# Model evaluations\n\n## Labeled retrieval metrics\n\nNot measured: a real hand-labeled set is required.\n"
    marker="\n## Latest HNSW benchmark\n"; existing=existing.split(marker)[0]
    doc.write_text(existing.rstrip()+"\n\n## Latest HNSW benchmark\n\n"+"\n".join(md[2:])+"\n")
    print(f"\nPersisted index parameters: m={best['m']}, ef_search={best['ef_search']}")


if __name__ == "__main__": main()
