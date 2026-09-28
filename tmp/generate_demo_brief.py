import json
import os
from dotenv import load_dotenv, set_key
from psycopg.types.json import Json
from database.connection import connect
from database.longitudinal_records import LongitudinalRecordRepository
from database import client_journey
from ai_harness.brief_projection import project_accepted_insights
from ai_harness.brief_service import brief_input
from ai_harness.pre_session import generate_openai_pre_session_brief, resolve_brief
load_dotenv('.env')
client = 'e429487c-dc9c-493e-a460-c5b1d4c7750a'
with connect() as connection, connection.cursor() as cursor:
    cursor.execute("SELECT organization_id FROM app.clients WHERE id=%s", (client,))
    org = str(cursor.fetchone()['organization_id'])
    cursor.execute("""SELECT membership.user_id FROM app.client_therapist_access access
        JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
        JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
        WHERE access.client_id=%s AND access.organization_id=%s AND access.revoked_at IS NULL
        AND access.can_write_clinical AND membership.status='active' AND practitioner.status='active' LIMIT 1""", (client, org))
    actor = cursor.fetchone()['user_id']
    packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(organization_id=org, client_id=client)
    journey = client_journey.list_entries(connection, org, client, status='accepted')
fingerprint, request = brief_input(project_accepted_insights(packet, journey))
assert request['evidence'] and all(s.get('session_label', '').startswith('Synthetic · Elena Sadić · Session ') for s in request['evidence']), 'Only synthetic fixture evidence can be sent by this test.'
print('Generating one bounded synthetic brief; sources:', len(request['evidence']), flush=True)
try:
    generated, metadata = generate_openai_pre_session_brief(synthesis_request=request, api_key=os.environ['OPENAI_API_KEY'], model=os.environ['PRE_SESSION_MODEL'])
except RuntimeError as error:
    if hasattr(error, 'generated_response'):
        from pathlib import Path
        Path('tmp/synthetic-brief-validation.json').write_text(json.dumps({'response': error.generated_response, 'usage': error.usage}), encoding='utf-8')
    raise
resolved = resolve_brief(generated, request['evidence'])
with connect() as connection, connection.cursor() as cursor:
    current_packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(organization_id=org, client_id=client)
    current_journey = client_journey.list_entries(connection, org, client, status='accepted')
    assert brief_input(project_accepted_insights(current_packet, current_journey))[0] == fingerprint, 'Source context changed; result not saved.'
    cursor.execute("""INSERT INTO app.generated_pre_session_briefs
        (organization_id, client_id, context_hash, response, model, generated_by)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,client_id) DO UPDATE
        SET context_hash=EXCLUDED.context_hash,response=EXCLUDED.response,model=EXCLUDED.model,
        generated_by=EXCLUDED.generated_by,generated_at=CURRENT_TIMESTAMP""", (org,client,fingerprint,Json(generated),metadata['model'],actor))
usage = metadata['usage']
print(json.dumps({'model':metadata['model'], 'usage':usage, 'estimated_usd':(usage.get('input_tokens',0)*0.25+usage.get('output_tokens',0)*2)/1000000, 'claims':sum(len(i['claims']) for s in resolved['sections'] for i in s['items'])}))
