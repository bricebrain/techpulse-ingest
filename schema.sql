-- TechPulse v2 — Neon PostgreSQL + pgvector
-- Run this once on your Neon database to set up the full schema.

-- ============================================================
-- 0. Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for full-text search

-- ============================================================
-- 1. Articles — raw ingested content
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT UNIQUE NOT NULL,
  source_name TEXT NOT NULL,
  source_type TEXT NOT NULL,
  author TEXT,
  description TEXT,
  full_text TEXT,
  language TEXT DEFAULT 'en',
  published_at TIMESTAMPTZ,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  external_score INTEGER DEFAULT 0,
  comments_count INTEGER DEFAULT 0,
  category TEXT,
  category_confidence FLOAT,
  sentiment TEXT,
  sentiment_score FLOAT,
  embedding vector(384),
  cluster_id TEXT,
  internal_score INTEGER DEFAULT 0,
  status TEXT DEFAULT 'new',
  image_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_embedding
  ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_articles_cluster
  ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_status
  ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_published
  ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_type
  ON articles(source_type);
CREATE INDEX IF NOT EXISTS idx_articles_url
  ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_title_trgm
  ON articles USING gin (title gin_trgm_ops);

-- ============================================================
-- 2. Clusters — grouped stories
-- ============================================================
CREATE TABLE IF NOT EXISTS clusters (
  id TEXT PRIMARY KEY,
  title TEXT,
  summary TEXT,
  main_theme TEXT,
  status TEXT DEFAULT 'active',
  importance_score INTEGER DEFAULT 0,
  growth_score INTEGER DEFAULT 0,
  novelty_score INTEGER DEFAULT 0,
  source_diversity INTEGER DEFAULT 0,
  article_count INTEGER DEFAULT 0,
  centroid vector(384),
  first_seen_at TIMESTAMPTZ,
  last_updated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clusters_centroid
  ON clusters USING hnsw (centroid vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_clusters_status
  ON clusters(status);
CREATE INDEX IF NOT EXISTS idx_clusters_importance
  ON clusters(importance_score DESC);

ALTER TABLE articles
  ADD CONSTRAINT fk_articles_cluster
  FOREIGN KEY (cluster_id) REFERENCES clusters(id)
  ON DELETE SET NULL;

-- ============================================================
-- 3. Cluster ↔ Article join table
-- ============================================================
CREATE TABLE IF NOT EXISTS cluster_articles (
  id TEXT PRIMARY KEY,
  cluster_id TEXT NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
  article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  similarity_score FLOAT,
  role TEXT DEFAULT 'supporting',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(cluster_id, article_id)
);

-- ============================================================
-- 4. Entities — auto-detected actors, technologies, concepts
-- ============================================================
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  type TEXT NOT NULL,
  aliases JSONB DEFAULT '[]',
  description TEXT,
  embedding vector(384),
  mentions_count INTEGER DEFAULT 0,
  trend_score INTEGER DEFAULT 0,
  first_seen_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entities_type
  ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_normalized
  ON entities(normalized_name);
CREATE INDEX IF NOT EXISTS idx_entities_trend
  ON entities(trend_score DESC);

-- ============================================================
-- 5. Article ↔ Entity join table
-- ============================================================
CREATE TABLE IF NOT EXISTS article_entities (
  id TEXT PRIMARY KEY,
  article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  role TEXT,
  confidence FLOAT DEFAULT 0.0,
  source TEXT DEFAULT 'ner',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(article_id, entity_id)
);

-- ============================================================
-- 6. Keywords — auto-discovered search terms
-- ============================================================
CREATE TABLE IF NOT EXISTS keywords (
  id TEXT PRIMARY KEY,
  keyword TEXT NOT NULL UNIQUE,
  category TEXT,
  source TEXT DEFAULT 'manual',
  status TEXT DEFAULT 'active',
  usage_count INTEGER DEFAULT 0,
  discovery_reason TEXT,
  first_seen_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 7. Source queries — dynamic search queries for YouTube/Reddit
-- ============================================================
CREATE TABLE IF NOT EXISTS source_queries (
  id TEXT PRIMARY KEY,
  query TEXT NOT NULL,
  source_type TEXT NOT NULL,
  category TEXT,
  priority INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  generated_by TEXT DEFAULT 'manual',
  last_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  result_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 8. Timeline events — story evolution over time
-- ============================================================
CREATE TABLE IF NOT EXISTS timeline_events (
  id TEXT PRIMARY KEY,
  cluster_id TEXT NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  event_date TIMESTAMPTZ,
  source_article_id TEXT REFERENCES articles(id) ON DELETE SET NULL,
  importance INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_cluster
  ON timeline_events(cluster_id);
CREATE INDEX IF NOT EXISTS idx_timeline_date
  ON timeline_events(event_date DESC);

-- ============================================================
-- 9. AI Analyses — LLM-generated insights on clusters
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_analyses (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  model_provider TEXT,
  model_name TEXT,
  analysis_type TEXT,
  content JSONB NOT NULL,
  tokens_used INTEGER DEFAULT 0,
  cost_estimate FLOAT DEFAULT 0.0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyses_target
  ON ai_analyses(target_type, target_id);

-- ============================================================
-- 10. Trend snapshots — daily metrics for tracking growth
-- ============================================================
CREATE TABLE IF NOT EXISTS trend_snapshots (
  id TEXT PRIMARY KEY,
  entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  keyword_id TEXT REFERENCES keywords(id) ON DELETE CASCADE,
  cluster_id TEXT REFERENCES clusters(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,
  mention_count INTEGER DEFAULT 0,
  source_count INTEGER DEFAULT 0,
  growth_rate FLOAT DEFAULT 0.0,
  sentiment_avg FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trends_date
  ON trend_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_trends_entity
  ON trend_snapshots(entity_id);

-- ============================================================
-- 11. Podcasts
-- ============================================================
CREATE TABLE IF NOT EXISTS podcasts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  podcast_type TEXT DEFAULT 'daily',
  script TEXT,
  audio_url TEXT,
  duration_seconds INTEGER,
  cluster_ids JSONB DEFAULT '[]',
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 12. Alerts — user-defined notification rules
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  condition JSONB NOT NULL,
  status TEXT DEFAULT 'active',
  last_triggered_at TIMESTAMPTZ,
  last_checked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 13. Sources config — migrated from D1
-- ============================================================
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT,
  source_type TEXT NOT NULL,
  theme TEXT DEFAULT 'general',
  is_active BOOLEAN DEFAULT true,
  is_default BOOLEAN DEFAULT false,
  fetch_frequency_minutes INTEGER DEFAULT 120,
  last_fetched_at TIMESTAMPTZ,
  error_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 14. Pipeline runs — track each pipeline execution
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id TEXT PRIMARY KEY,
  pipeline_type TEXT NOT NULL,
  status TEXT DEFAULT 'running',
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  articles_fetched INTEGER DEFAULT 0,
  articles_embedded INTEGER DEFAULT 0,
  clusters_created INTEGER DEFAULT 0,
  clusters_updated INTEGER DEFAULT 0,
  analyses_generated INTEGER DEFAULT 0,
  errors JSONB DEFAULT '[]',
  duration_seconds INTEGER
);
