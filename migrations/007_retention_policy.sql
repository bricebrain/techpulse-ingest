-- Migration 007 — Politique de rétention Neon (garder la DB sous le free tier 0.5 Go)
--
-- Idée : la VALEUR du produit vit dans les données structurées (clusters,
-- ai_analyses, entities, article_intelligence), qui sont petites. Le POIDS vient
-- de articles.full_text + articles.embedding (vector 1024 ≈ 4 Ko/article + index
-- HNSW) et de trend_snapshots / pipeline_jobs qui grossissent chaque jour.
--
-- On ne supprime donc pas l'intelligence : on (1) archive les clusters inactifs,
-- (2) vide full_text+embedding des vieux articles non rattachés à un cluster actif,
-- (3) supprime les articles orphelins très anciens, (4) purge les snapshots / runs
-- / analyses obsolètes. Tout est paramétrable et la fonction est idempotente.

-- Index utiles aux purges par date (les filtres deviennent des index scans).
CREATE INDEX IF NOT EXISTS idx_articles_created_at
  ON articles(created_at);
CREATE INDEX IF NOT EXISTS idx_clusters_last_updated
  ON clusters(last_updated_at);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at
  ON ai_analyses(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started
  ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_created
  ON pipeline_jobs(created_at);

-- Fonction de purge. Retourne un récapitulatif (étape, lignes touchées).
CREATE OR REPLACE FUNCTION prune_techpulse(
  p_fulltext_days     INTEGER DEFAULT 60,   -- au-delà : vider full_text+embedding des articles hors cluster actif
  p_article_delete_days INTEGER DEFAULT 180, -- au-delà : supprimer les articles orphelins (sans cluster)
  p_trend_days        INTEGER DEFAULT 120,  -- conserver N jours de trend_snapshots
  p_analysis_days     INTEGER DEFAULT 90,   -- supprimer les analyses obsolètes (on garde la plus récente par cible)
  p_cluster_idle_days INTEGER DEFAULT 30,   -- archiver les clusters sans activité depuis N jours
  p_pipeline_days     INTEGER DEFAULT 30    -- conserver N jours d'observabilité (runs/jobs)
)
RETURNS TABLE(step TEXT, rows_affected BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
  v_count BIGINT;
BEGIN
  -- 1) Archiver les clusters inactifs (réduit aussi l'ensemble actif du clustering).
  UPDATE clusters
     SET status = 'archived'
   WHERE status <> 'archived'
     AND COALESCE(last_updated_at, created_at) < NOW() - (p_cluster_idle_days || ' days')::INTERVAL;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'clusters_archived'; rows_affected := v_count; RETURN NEXT;

  -- 2) Alléger les vieux articles non rattachés à un cluster ACTIF :
  --    on supprime les gros champs (full_text + embedding) mais on garde les
  --    métadonnées et article_intelligence (petits, utiles aux références/timeline).
  UPDATE articles a
     SET full_text = NULL,
         embedding = NULL,
         embedding_status = 'pruned'
   WHERE a.created_at < NOW() - (p_fulltext_days || ' days')::INTERVAL
     AND a.full_text IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM clusters c
        WHERE c.id = a.cluster_id AND c.status <> 'archived'
     );
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'articles_slimmed'; rows_affected := v_count; RETURN NEXT;

  -- 3) Supprimer les articles orphelins très anciens (aucun cluster).
  --    Les FK ON DELETE CASCADE nettoient article_entities / cluster_articles /
  --    article_intelligence ; timeline_events.source_article_id passe à NULL.
  DELETE FROM articles a
   WHERE a.created_at < NOW() - (p_article_delete_days || ' days')::INTERVAL
     AND a.cluster_id IS NULL;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'articles_deleted'; rows_affected := v_count; RETURN NEXT;

  -- 4) Purger les vieux snapshots de tendance (on ne garde qu'une fenêtre glissante).
  DELETE FROM trend_snapshots
   WHERE snapshot_date < (CURRENT_DATE - p_trend_days);
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'trend_snapshots_deleted'; rows_affected := v_count; RETURN NEXT;

  -- 5) Purger les analyses obsolètes : garder la plus récente par (cible) et
  --    supprimer les versions plus anciennes au-delà de la fenêtre.
  WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
             PARTITION BY target_type, target_id, analysis_type
             ORDER BY created_at DESC
           ) AS rn
      FROM ai_analyses
  )
  DELETE FROM ai_analyses
   WHERE id IN (
     SELECT r.id FROM ranked r
      JOIN ai_analyses a ON a.id = r.id
     WHERE r.rn > 1
       AND a.created_at < NOW() - (p_analysis_days || ' days')::INTERVAL
   );
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'ai_analyses_deleted'; rows_affected := v_count; RETURN NEXT;

  -- 6) Observabilité : ne garder que les N derniers jours.
  DELETE FROM pipeline_jobs
   WHERE created_at < NOW() - (p_pipeline_days || ' days')::INTERVAL;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'pipeline_jobs_deleted'; rows_affected := v_count; RETURN NEXT;

  DELETE FROM pipeline_runs
   WHERE started_at < NOW() - (p_pipeline_days || ' days')::INTERVAL;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := 'pipeline_runs_deleted'; rows_affected := v_count; RETURN NEXT;

  RETURN;
END;
$$;
