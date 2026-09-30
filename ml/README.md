# Modeling workspace

PyTorch training and evaluation code belongs here. The ingest pipeline stores sequence tokens as JSON arrays containing `event_type`, 12×8 `zone`, `outcome`, and `time_delta`. Embeddings are optional and stored in the `sequences.embedding` pgvector column (384 dimensions); choose and document a model before producing them.
