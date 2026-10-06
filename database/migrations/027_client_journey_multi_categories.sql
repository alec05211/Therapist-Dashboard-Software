BEGIN;

ALTER TABLE app.client_journey_entries
  ADD COLUMN categories text[];

UPDATE app.client_journey_entries
SET categories = ARRAY[category];

ALTER TABLE app.client_journey_entries
  ALTER COLUMN categories SET NOT NULL,
  ALTER COLUMN categories SET DEFAULT ARRAY['context']::text[],
  ADD CONSTRAINT client_journey_categories_valid CHECK (
    cardinality(categories) BETWEEN 1 AND 6
    AND categories <@ ARRAY[
      'context', 'theme', 'important_quote', 'resolution',
      'breakthrough', 'open_thread'
    ]::text[]
  );

ALTER TABLE app.client_journey_entry_revisions
  ADD COLUMN previous_categories text[],
  ADD COLUMN next_categories text[];

UPDATE app.client_journey_entry_revisions
SET previous_categories = ARRAY[previous_category],
    next_categories = ARRAY[next_category];

ALTER TABLE app.client_journey_entry_revisions
  ALTER COLUMN previous_categories SET NOT NULL,
  ALTER COLUMN next_categories SET NOT NULL;

COMMIT;
