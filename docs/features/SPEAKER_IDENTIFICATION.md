# Speaker names and review samples

HealthScribe's provider roles are job-local model output, not person identities.
The provider labels remain unchanged in stored source segments and raw artifacts,
and database-backed transcript reads present each unreviewed speaker using that
exact provider label. Identification settings show the same label verbatim, save
a client-scoped name for it, and apply that name to
all existing and future transcripts in that care relationship. A later
transcript-specific correction remains authoritative for that individual session.

The settings UI groups detected speakers by completed session. Each row uses the
exact provider label, offers known relationship names as suggestions, accepts
another participant's name, and plays
a stored sample pointer from that exact transcript. Samples prefer the longest
available turn and are capped at ten seconds. They use existing authorized
recording routes; no separate audio files or voiceprints are created. These are
listening aids for manual confirmation, not automated identity recognition.

HealthScribe jobs request up to six speakers by default. Every distinct returned
label—including `PATIENT_1`, `CLINICIAN_1`, or another numbered participant—is
persisted with a sample pointer in `app.transcript_speaker_samples`. This is
automatic diarization, not identity recognition: provider label numbering is not
a durable identity across recordings. The application nevertheless carries an
explicit therapist-saved mapping for an exact provider label across this one
client relationship, as requested, and never shares it with another client. Existing per-transcript
corrections remain authoritative and are scoped to the selected transcript.

Profile updates commit after the existing relationship and clinical-write checks.
Migration `025_relationship_speaker_names.sql` stores relationship-wide speaker
labels separately from participant pronouns. Legacy file-only transcripts retain
their existing explicit speaker mappings.

Validation: unit coverage for correction precedence, unknown/additional labels,
scoped defaults, sample duration and provenance, stale/cross-client rejection,
and resetting one override. Read-only demo checks verify all discovered speaker
rows have usable sample metadata and both primary labels resolve to names.
