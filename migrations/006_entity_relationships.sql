-- Entity relationships inferred from article/entity cooccurrences in clusters.
-- One row represents an undirected pair. IDs are stored in canonical order.

CREATE TABLE IF NOT EXISTS entity_relationships (
  id TEXT PRIMARY KEY,
  source_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  target_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL DEFAULT 'cooccurs_in_cluster',
  strength_score INTEGER DEFAULT 0,
  evidence_count INTEGER DEFAULT 0,
  evidence_cluster_ids JSONB DEFAULT '[]'::jsonb,
  evidence_article_ids JSONB DEFAULT '[]'::jsonb,
  evidence_summary JSONB DEFAULT '{}'::jsonb,
  first_seen_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  CHECK (source_entity_id <> target_entity_id),
  UNIQUE(source_entity_id, target_entity_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_entity_relationships_source
  ON entity_relationships(source_entity_id, strength_score DESC);

CREATE INDEX IF NOT EXISTS idx_entity_relationships_target
  ON entity_relationships(target_entity_id, strength_score DESC);

CREATE INDEX IF NOT EXISTS idx_entity_relationships_type
  ON entity_relationships(relation_type);

CREATE INDEX IF NOT EXISTS idx_entity_relationships_strength
  ON entity_relationships(strength_score DESC);
