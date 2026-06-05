-- Optional migration for BAAI/bge-m3 embeddings.
-- Apply only when EMBEDDING_MODEL=BAAI/bge-m3 is enabled in GitHub Actions.
--
-- This invalidates existing 384-dim embeddings. After applying:
--   1. Set articles.embedding = NULL and status = 'scraped' for recent articles.
--   2. Recompute embeddings with the ingest pipeline.
--   3. Rebuild clusters from the new vectors.

DROP INDEX IF EXISTS idx_articles_embedding;
DROP INDEX IF EXISTS idx_clusters_centroid;

ALTER TABLE articles
  ALTER COLUMN embedding TYPE vector(1024);

ALTER TABLE clusters
  ALTER COLUMN centroid TYPE vector(1024);

CREATE INDEX IF NOT EXISTS idx_articles_embedding
  ON articles USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_clusters_centroid
  ON clusters USING hnsw (centroid vector_cosine_ops);
