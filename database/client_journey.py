"""Source-linked HealthScribe proposals and therapist-reviewed journey history."""

CATEGORIES = {'context', 'theme', 'important_quote', 'resolution', 'breakthrough', 'open_thread'}
REVIEW_STATES = {'accepted', 'rejected', 'hidden', 'stale', 'disputed'}


def propose_from_healthscribe(cursor, storage, raw_transcript, raw_note, transcript_version_id):
    """Store source-linked note excerpts as proposals, never as accepted facts."""
    source_indices = {}
    sequence = 0
    for segment in raw_transcript.get('Conversation', {}).get('TranscriptSegments', []):
        if not str(segment.get('Content') or '').strip():
            continue
        if segment.get('SegmentId'):
            source_indices[segment['SegmentId']] = sequence
        sequence += 1
    cursor.execute("""SELECT id, sequence_number FROM app.transcript_segments
        WHERE transcript_version_id=%s""", (transcript_version_id,))
    persisted = {row['sequence_number']: row['id'] for row in cursor.fetchall()}
    written = 0
    for section_index, section in enumerate(raw_note.get('ClinicalDocumentation', {}).get('Sections', [])):
        section_name = section.get('SectionName', 'OTHER')
        for index, item in enumerate(section.get('Summary', [])):
            content = str(item.get('SummarizedSegment') or '').strip()
            cited = {persisted[source_indices[link['SegmentId']]]
                     for link in item.get('EvidenceLinks', [])
                     if link.get('SegmentId') in source_indices and source_indices[link['SegmentId']] in persisted}
            if not content or len(content) > 4000 or not cited:
                continue
            cursor.execute("""INSERT INTO app.client_journey_entries
                (organization_id, client_id, session_id, source_summary_key, source_provider, content)
                VALUES (%s,%s,%s,%s,'amazon_healthscribe',%s)
                ON CONFLICT (session_id, source_summary_key) DO NOTHING RETURNING id""",
                (storage['organization_id'], storage['client_id'], storage['session_id'], f'{section_index}:{section_name}:{index}', content))
            proposal = cursor.fetchone()
            if proposal:
                for segment_id in cited:
                    cursor.execute("""INSERT INTO app.client_journey_evidence
                        (journey_entry_id, transcript_segment_id) VALUES (%s,%s)""",
                        (proposal['id'], segment_id))
                written += 1
            if written >= 15:
                return written
    return written


def list_entries(connection, organization_id, client_id, status=None):
    with connection.cursor() as cursor:
        cursor.execute("""SELECT entry.id, entry.session_id, entry.source_provider,
                entry.category, entry.content, entry.status, entry.created_at,
                segment.id AS transcript_segment_id, segment.sequence_number,
                segment.starts_at_seconds, segment.ends_at_seconds, segment.content AS quote,
                COALESCE(job.storage->>'label', 'Completed session') AS session_label
            FROM app.client_journey_entries entry
            JOIN app.client_journey_evidence evidence ON evidence.journey_entry_id=entry.id
            JOIN app.transcript_segments segment ON segment.id=evidence.transcript_segment_id
            LEFT JOIN app.session_storage_jobs job ON job.session_id=entry.session_id
            WHERE entry.organization_id=%s AND entry.client_id=%s
              AND (%s::text IS NULL OR entry.status=%s)
            ORDER BY entry.created_at DESC, entry.id, segment.sequence_number""",
            (organization_id, client_id, status, status))
        rows = cursor.fetchall()
    entries = {}
    for row in rows:
        entry_id = str(row['id'])
        entry = entries.setdefault(entry_id, {
            'id': entry_id, 'session_id': f"session-{row['session_id']}",
            'source_provider': row['source_provider'], 'category': row['category'],
            'text': row['content'], 'status': row['status'],
            'created_at': row['created_at'].isoformat(), 'evidence': [],
        })
        entry['evidence'].append({
            'evidence_id': str(row['transcript_segment_id']),
            'session_id': entry['session_id'], 'session_label': row['session_label'],
            'segment_index': row['sequence_number'],
            'start': float(row['starts_at_seconds']), 'end': float(row['ends_at_seconds']),
            'quote': row['quote'],
        })
    return list(entries.values())


def review_entry(connection, *, organization_id, client_id, entry_id, category, content, state, actor_user_id):
    if category not in CATEGORIES or state not in REVIEW_STATES or not content.strip():
        raise ValueError('Choose a category, a review decision, and non-empty text.')
    with connection.cursor() as cursor:
        cursor.execute("""SELECT status, category, content FROM app.client_journey_entries
            WHERE id=%s AND organization_id=%s AND client_id=%s FOR UPDATE""",
            (entry_id, organization_id, client_id))
        previous = cursor.fetchone()
        if not previous:
            return False
        cursor.execute("""UPDATE app.client_journey_entries
            SET category=%s, content=%s, status=%s, reviewed_by_user_id=%s,
                reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s AND organization_id=%s AND client_id=%s""",
            (category, content.strip(), state, actor_user_id, entry_id, organization_id, client_id))
        cursor.execute("""INSERT INTO app.client_journey_entry_revisions
            (journey_entry_id, previous_status, next_status, previous_category,
             next_category, previous_content, next_content, changed_by_user_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (entry_id, previous['status'], state, previous['category'], category,
             previous['content'], content.strip(), actor_user_id))
    return True
