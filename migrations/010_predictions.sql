-- 010_predictions.sql
-- Table de suivi des prédictions extraites par le LLM.
-- Source : podcasts (Phase E), analyses de clusters, article intelligence.
-- Chaque prédiction peut être marquée résolue/manquée/floue plus tard.

CREATE TABLE IF NOT EXISTS predictions (
  id TEXT PRIMARY KEY,
  prediction TEXT NOT NULL,          -- ce qui a été prédit (en français)
  horizon TEXT,                       -- short-term | medium-term | long-term | unknown
  confidence TEXT,                    -- stated | implied | speculative
  source_type TEXT NOT NULL,          -- 'podcast' | 'cluster' | 'article'
  source_id TEXT NOT NULL,            -- id du podcast/cluster/article
  source_title TEXT,                  -- titre de la source
  source_name TEXT,                   -- nom de la source (ex: Tronche de Tech)
  speaker TEXT,                       -- qui a fait la prédiction (si identifiable)
  domain TEXT,                        -- AI | finance | space | energy | other
  status TEXT DEFAULT 'pending',      -- pending | resolved | missed | ambiguous
  resolved_at TIMESTAMPTZ,            -- quand la prédiction a été tranchée
  resolution_notes TEXT,              -- notes sur la résolution
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_domain ON predictions(domain);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_source ON predictions(source_type, source_id);
