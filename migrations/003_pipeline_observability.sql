-- TechPulse pipeline observability foundations.
--
-- Adds fine-grained article pipeline statuses and a generic jobs table without
-- removing the legacy articles.status column used by the current pipelines.

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS pipeline_status TEXT,
  ADD COLUMN IF NOT EXISTS extraction_status TEXT,
  ADD COLUMN IF NOT EXISTS embedding_status TEXT,
  ADD COLUMN IF NOT EXISTS clustering_status TEXT,
  ADD COLUMN IF NOT EXISTS analysis_status TEXT,
  ADD COLUMN IF NOT EXISTS extraction_method TEXT,
  ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS embedding_model TEXT,
  ADD COLUMN IF NOT EXISTS embedding_dimensions INTEGER,
  ADD COLUMN IF NOT EXISTS last_error TEXT,
  ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_processed_at TIMESTAMPTZ;

UPDATE articles
SET
  pipeline_status = COALESCE(
    pipeline_status,
    CASE
      WHEN status = 'analyzed' THEN 'analyzed'
      WHEN status = 'clustered' THEN 'clustered'
      WHEN embedding IS NOT NULL OR status = 'processed' THEN 'embedded'
      WHEN full_text IS NOT NULL OR status = 'scraped' THEN 'extracted'
      ELSE 'discovered'
    END
  ),
  extraction_status = COALESCE(
    extraction_status,
    CASE WHEN full_text IS NOT NULL OR status IN ('scraped', 'processed', 'clustered', 'analyzed')
      THEN 'extracted'
      ELSE 'pending'
    END
  ),
  embedding_status = COALESCE(
    embedding_status,
    CASE WHEN embedding IS NOT NULL OR status IN ('processed', 'clustered', 'analyzed')
      THEN 'embedded'
      ELSE 'pending'
    END
  ),
  clustering_status = COALESCE(
    clustering_status,
    CASE WHEN cluster_id IS NOT NULL OR status IN ('clustered', 'analyzed')
      THEN 'clustered'
      ELSE 'pending'
    END
  ),
  analysis_status = COALESCE(
    analysis_status,
    CASE WHEN status = 'analyzed'
      THEN 'analyzed'
      ELSE 'pending'
    END
  ),
  extracted_at = COALESCE(extracted_at, CASE WHEN full_text IS NOT NULL THEN fetched_at ELSE NULL END),
  embedded_at = COALESCE(embedded_at, CASE WHEN embedding IS NOT NULL THEN fetched_at ELSE NULL END),
  embedding_model = COALESCE(embedding_model, CASE WHEN embedding IS NOT NULL THEN 'BAAI/bge-m3' ELSE NULL END),
  embedding_dimensions = COALESCE(embedding_dimensions, CASE WHEN embedding IS NOT NULL THEN 1024 ELSE NULL END),
  retry_count = COALESCE(retry_count, 0);

CREATE INDEX IF NOT EXISTS idx_articles_pipeline_status
  ON articles(pipeline_status);
CREATE INDEX IF NOT EXISTS idx_articles_extraction_status
  ON articles(extraction_status);
CREATE INDEX IF NOT EXISTS idx_articles_embedding_status
  ON articles(embedding_status);
CREATE INDEX IF NOT EXISTS idx_articles_clustering_status
  ON articles(clustering_status);
CREATE INDEX IF NOT EXISTS idx_articles_analysis_status
  ON articles(analysis_status);
CREATE INDEX IF NOT EXISTS idx_articles_last_processed
  ON articles(last_processed_at DESC);

CREATE TABLE IF NOT EXISTS pipeline_jobs (
  id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES pipeline_runs(id) ON DELETE SET NULL,
  job_type TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  priority INTEGER DEFAULT 0,
  attempts INTEGER DEFAULT 0,
  max_attempts INTEGER DEFAULT 3,
  error_message TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  scheduled_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_status
  ON pipeline_jobs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_type_status
  ON pipeline_jobs(job_type, status);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_target
  ON pipeline_jobs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_run
  ON pipeline_jobs(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_scheduled
  ON pipeline_jobs(scheduled_at DESC);
