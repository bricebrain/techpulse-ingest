-- Migration for BAAI/bge-m3 embeddings (1024 dimensions).
--
-- This intentionally invalidates existing 384-dim embeddings and clusters.
-- After applying, run the ingest pipeline to recompute embeddings, then let
-- techpulse-intelligence rebuild clusters from the new 1024-dim vectors.

BEGIN;

DROP INDEX IF EXISTS idx_articles_embedding;
DROP INDEX IF EXISTS idx_clusters_centroid;

DELETE FROM trend_snapshots WHERE cluster_id IS NOT NULL;
DELETE FROM timeline_events;
DELETE FROM ai_analyses WHERE target_type IN ('cluster', 'daily_digest');
DELETE FROM cluster_articles;
DELETE FROM clusters;

UPDATE articles
SET embedding = NULL,
    cluster_id = NULL,
    status = CASE
      WHEN full_text IS NOT NULL AND length(full_text) > 0 THEN 'scraped'
      ELSE 'new'
    END;

ALTER TABLE articles
  ALTER COLUMN embedding TYPE vector(1024)
  USING NULL;

ALTER TABLE clusters
  ALTER COLUMN centroid TYPE vector(1024)
  USING NULL;

ALTER TABLE entities
  ALTER COLUMN embedding TYPE vector(1024)
  USING NULL;

CREATE INDEX IF NOT EXISTS idx_articles_embedding
  ON articles USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_clusters_centroid
  ON clusters USING hnsw (centroid vector_cosine_ops);

COMMIT;
