-- TechPulse v2 — source-specific extraction strategies.

CREATE TABLE IF NOT EXISTS source_extraction_rules (
  id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL UNIQUE,
  strategy TEXT NOT NULL DEFAULT 'trafilatura_fastapi',
  user_agent TEXT,
  use_fastapi BOOLEAN DEFAULT true,
  use_local_fallback BOOLEAN DEFAULT true,
  timeout_ms INTEGER DEFAULT 20000,
  max_retries INTEGER DEFAULT 2,
  requires_browser BOOLEAN DEFAULT false,
  is_blocked_often BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_extraction_rules_strategy
  ON source_extraction_rules(strategy);
CREATE INDEX IF NOT EXISTS idx_source_extraction_rules_fastapi
  ON source_extraction_rules(use_fastapi);

INSERT INTO source_extraction_rules (
  id, source_name, strategy, use_fastapi, use_local_fallback,
  timeout_ms, max_retries, requires_browser, is_blocked_often
) VALUES
  ('rule_techcrunch', 'TechCrunch', 'trafilatura_fastapi', true, true, 20000, 2, false, false),
  ('rule_the_verge', 'The Verge', 'trafilatura_fastapi', true, true, 20000, 2, false, false),
  ('rule_ars_technica', 'Ars Technica', 'trafilatura_fastapi', true, true, 20000, 2, false, false),
  ('rule_bloomberg', 'Bloomberg', 'metadata_only', false, true, 12000, 1, false, true),
  ('rule_youtube', 'YouTube', 'youtube_transcript', false, false, 20000, 1, false, false),
  ('rule_reddit', 'Reddit', 'manual_parser', false, false, 12000, 1, false, true),
  ('rule_medium', 'Medium', 'trafilatura_fastapi', true, true, 25000, 2, false, true)
ON CONFLICT (source_name) DO UPDATE SET
  strategy = EXCLUDED.strategy,
  use_fastapi = EXCLUDED.use_fastapi,
  use_local_fallback = EXCLUDED.use_local_fallback,
  timeout_ms = EXCLUDED.timeout_ms,
  max_retries = EXCLUDED.max_retries,
  requires_browser = EXCLUDED.requires_browser,
  is_blocked_often = EXCLUDED.is_blocked_often,
  updated_at = NOW();
