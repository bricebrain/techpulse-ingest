-- Migration 008 — Sérendipité scientifique
--
-- Onglet "inspirationnel" : chaque jour, quelques pépites scientifiques
-- multidisciplinaires (astro, physique, neuro, biotech...) vulgarisées.
-- ANCRAGE : chaque carte provient d'un VRAI papier arXiv (arxiv_id + source_url),
-- le LLM ne fait que vulgariser le titre+résumé réels → pas d'invention de sources.

CREATE TABLE IF NOT EXISTS serendipity_cards (
  id TEXT PRIMARY KEY,
  arxiv_id TEXT UNIQUE,            -- identifiant arXiv (dédup + provenance)
  source_url TEXT,                -- lien abs arXiv (citation cliquable)
  domain TEXT,                    -- domaine vulgarisé en français (ex. "astrophysique")
  arxiv_category TEXT,            -- catégorie arXiv brute (ex. "astro-ph.HE")
  title_choc TEXT NOT NULL,       -- titre accrocheur (FR)
  enigme TEXT,                    -- pourquoi c'est fou, en 2 phrases
  personnage TEXT,                -- le/la chercheur·se ou l'équipe clé
  concept TEXT,                   -- explication vulgarisée, sans jargon
  so_what TEXT,                   -- le "et alors ?" : impact / pourquoi ça compte
  paper_title TEXT,               -- titre original du papier (provenance)
  authors JSONB DEFAULT '[]'::jsonb,
  published_at TIMESTAMPTZ,       -- date du papier
  model_provider TEXT,
  model_name TEXT,
  status TEXT DEFAULT 'active',   -- "active" | "archived"
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_serendipity_created
  ON serendipity_cards(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_serendipity_domain
  ON serendipity_cards(domain);
CREATE INDEX IF NOT EXISTS idx_serendipity_status
  ON serendipity_cards(status);
