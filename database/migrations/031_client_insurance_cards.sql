BEGIN;

CREATE TABLE app.client_insurance_cards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES app.organizations(id),
  client_id uuid NOT NULL REFERENCES app.clients(id),
  front_artifact_id uuid NOT NULL UNIQUE REFERENCES app.clinical_artifacts(id),
  back_artifact_id uuid NOT NULL UNIQUE REFERENCES app.clinical_artifacts(id),
  front_filename text NOT NULL CHECK (length(trim(front_filename)) > 0),
  back_filename text NOT NULL CHECK (length(trim(back_filename)) > 0),
  status text NOT NULL DEFAULT 'processing'
    CHECK (status IN ('processing', 'ready', 'failed', 'replaced')),
  model_extracted_fields jsonb NOT NULL DEFAULT '{}'::jsonb,
  client_corrected_fields jsonb,
  source_provider text,
  source_model text,
  source_response_id text,
  analyzed_at timestamptz,
  corrected_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX client_insurance_cards_active
  ON app.client_insurance_cards (organization_id, client_id)
  WHERE status <> 'replaced';

CREATE INDEX client_insurance_cards_history
  ON app.client_insurance_cards (organization_id, client_id, created_at DESC);

CREATE TRIGGER client_insurance_cards_set_updated_at
BEFORE UPDATE ON app.client_insurance_cards
FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

COMMIT;
