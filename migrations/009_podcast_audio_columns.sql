-- 009_podcast_audio_columns.sql
-- Ajoute les colonnes audio pour les épisodes podcast transcrits.
-- Le Worker (D1) a déjà ces colonnes via schema.sql — cette migration aligne Neon.

ALTER TABLE articles ADD COLUMN IF NOT EXISTS audio_url TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS audio_duration INTEGER;

-- Index pour filtrer rapidement les épisodes podcast non encore transcrits
CREATE INDEX IF NOT EXISTS idx_articles_audio_url
  ON articles(audio_url)
  WHERE audio_url IS NOT NULL;
