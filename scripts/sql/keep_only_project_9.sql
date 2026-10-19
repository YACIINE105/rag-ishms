-- Run against the PostgreSQL database "rag-ishms" while processing/indexing is idle.
-- Keeps project 9, its assets/chunks, and all its PGVector collection versions.
-- Removes other projects' database records; uploaded files and job logs stay on disk.

BEGIN;
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF current_database() <> 'rag-ishms' THEN
        RAISE EXCEPTION 'Connect to the rag-ishms database before running this script';
    END IF;
END
$$;

LOCK TABLE public.projects, public.assets, public.chunks
    IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    collection_table record;
BEGIN
    -- Step 1: abort rather than delete everything if project 9 is missing.
    IF NOT EXISTS (SELECT 1 FROM public.projects WHERE project_id = 9) THEN
        RAISE EXCEPTION 'Project 9 does not exist; cleanup cancelled';
    END IF;

    -- Step 2: handle embeddings before deleting their referenced chunks.
    FOR collection_table IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename ~ '^collection_[a-z0-9_]+_[0-9]+$'
        ORDER BY tablename
    LOOP
        IF collection_table.tablename ~ '_9$' THEN
            EXECUTE format(
                'DELETE FROM public.%I AS vectors
                 WHERE NOT EXISTS (
                     SELECT 1 FROM public.chunks AS chunks
                     WHERE chunks.chunk_id = vectors.chunkid
                       AND chunks.chunk_project_id = 9
                 )',
                collection_table.tablename
            );
        ELSE
            EXECUTE format('DROP TABLE public.%I', collection_table.tablename);
        END IF;
    END LOOP;

    -- Step 3: delete dependent records before their parent projects.
    DELETE FROM public.chunks WHERE chunk_project_id <> 9;
    DELETE FROM public.assets WHERE asset_project_id <> 9;
    DELETE FROM public.projects WHERE project_id <> 9;
END
$$;

-- Step 4: report the remaining database records before committing.
SELECT project_id,
       (SELECT count(*) FROM public.assets WHERE asset_project_id = project_id) AS assets,
       (SELECT count(*) FROM public.chunks WHERE chunk_project_id = project_id) AS chunks
FROM public.projects;

SELECT tablename AS remaining_embedding_table
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename ~ '^collection_[a-z0-9_]+_[0-9]+$'
ORDER BY tablename;

COMMIT;
