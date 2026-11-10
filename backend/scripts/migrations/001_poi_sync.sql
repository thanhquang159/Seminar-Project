BEGIN;

LOCK TABLE public.pois IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS public.poi_sync_state (
    singleton boolean PRIMARY KEY DEFAULT TRUE CHECK (singleton IS TRUE),
    last_cursor bigint NOT NULL CHECK (last_cursor >= 0)
);

INSERT INTO public.poi_sync_state (singleton, last_cursor)
SELECT TRUE,
       GREATEST(
           COALESCE(
               FLOOR(EXTRACT(EPOCH FROM MAX(updated_at)) * 1000000)::bigint,
               0
           ),
           1
       )
FROM public.pois
WHERE TRUE
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.poi_sync_changes (
    change_cursor bigint PRIMARY KEY,
    poi_id uuid NOT NULL,
    operation text NOT NULL CHECK (operation IN ('upsert', 'delete')),
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS ix_poi_sync_changes_poi_cursor
    ON public.poi_sync_changes (poi_id, change_cursor DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.poi_sync_changes) THEN
        WITH baseline AS (
            SELECT last_cursor FROM public.poi_sync_state WHERE singleton IS TRUE
        ),
        existing_pois AS (
            SELECT id, is_active, ROW_NUMBER() OVER (ORDER BY id) AS ordinal
            FROM public.pois
        )
        INSERT INTO public.poi_sync_changes (change_cursor, poi_id, operation)
        SELECT baseline.last_cursor + existing_pois.ordinal,
               existing_pois.id,
               CASE WHEN existing_pois.is_active IS TRUE THEN 'upsert' ELSE 'delete' END
        FROM existing_pois
        CROSS JOIN baseline;

        UPDATE public.poi_sync_state
        SET last_cursor = last_cursor + (SELECT COUNT(*) FROM public.pois)
        WHERE singleton IS TRUE;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.record_poi_sync_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    changed_poi_id uuid;
    change_operation text;
    next_cursor bigint;
BEGIN
    IF TG_OP = 'DELETE' THEN
        changed_poi_id := OLD.id;
        change_operation := 'delete';
    ELSE
        changed_poi_id := NEW.id;
        IF NEW.is_active IS TRUE THEN
            change_operation := 'upsert';
        ELSE
            change_operation := 'delete';
        END IF;
    END IF;

    -- The row lock serializes cursor allocation until this POI transaction commits.
    UPDATE public.poi_sync_state
    SET last_cursor = last_cursor + 1
    WHERE singleton IS TRUE
    RETURNING last_cursor INTO next_cursor;

    IF next_cursor IS NULL THEN
        RAISE EXCEPTION 'poi_sync_state singleton row is missing';
    END IF;

    INSERT INTO public.poi_sync_changes (change_cursor, poi_id, operation)
    VALUES (next_cursor, changed_poi_id, change_operation);

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_pois_record_sync_change ON public.pois;

CREATE TRIGGER trg_pois_record_sync_change
AFTER INSERT OR UPDATE OR DELETE ON public.pois
FOR EACH ROW
EXECUTE FUNCTION public.record_poi_sync_change();

COMMIT;
