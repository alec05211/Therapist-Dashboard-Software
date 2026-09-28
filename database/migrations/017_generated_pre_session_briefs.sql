BEGIN;
CREATE TABLE app.generated_pre_session_briefs (
    organization_id uuid NOT NULL REFERENCES app.organizations(id),
    client_id uuid NOT NULL REFERENCES app.clients(id),
    context_hash text NOT NULL,
    response jsonb NOT NULL,
    model text NOT NULL,
    generated_by uuid NOT NULL REFERENCES app.application_users(id),
    generated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, client_id)
);
COMMIT;
