-- TechPulse v2 — structured article intelligence.
-- Adds LLM-derived article metadata used before clustering.

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS llm_enrichment_status TEXT,
  ADD COLUMN IF NOT EXISTS llm_enriched_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS llm_enrichment_model TEXT;

ALTER TABLE pipeline_runs
  ADD COLUMN IF NOT EXISTS articles_enriched INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_articles_llm_enrichment_status
  ON articles(llm_enrichment_status);

CREATE TABLE IF NOT EXISTS article_intelligence (
  id TEXT PRIMARY KEY,
  article_id TEXT NOT NULL UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
  model_provider TEXT,
  model_name TEXT,
  language TEXT,
  canonical_title TEXT,
  summary TEXT,
  article_type TEXT,
  primary_domain TEXT,
  topic TEXT,
  subtopics JSONB DEFAULT '[]'::jsonb,
  event_fingerprint TEXT,
  event_date DATE,
  entities JSONB DEFAULT '[]'::jsonb,
  companies JSONB DEFAULT '[]'::jsonb,
  people JSONB DEFAULT '[]'::jsonb,
  products JSONB DEFAULT '[]'::jsonb,
  sectors JSONB DEFAULT '[]'::jsonb,
  countries JSONB DEFAULT '[]'::jsonb,
  keywords JSONB DEFAULT '[]'::jsonb,
  tags JSONB DEFAULT '[]'::jsonb,
  sentiment TEXT,
  sentiment_score FLOAT,
  tech_impact TEXT,
  business_impact TEXT,
  finance_impact TEXT,
  market_impact TEXT,
  quality_score INTEGER,
  relevance_score INTEGER,
  novelty_score INTEGER,
  time_sensitivity TEXT,
  should_cluster BOOLEAN DEFAULT true,
  cluster_hint TEXT,
  confidence FLOAT,
  raw JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_article_intelligence_article
  ON article_intelligence(article_id);
CREATE INDEX IF NOT EXISTS idx_article_intelligence_domain
  ON article_intelligence(primary_domain);
CREATE INDEX IF NOT EXISTS idx_article_intelligence_topic
  ON article_intelligence(topic);
CREATE INDEX IF NOT EXISTS idx_article_intelligence_fingerprint
  ON article_intelligence(event_fingerprint);
CREATE INDEX IF NOT EXISTS idx_article_intelligence_relevance
  ON article_intelligence(relevance_score DESC);
