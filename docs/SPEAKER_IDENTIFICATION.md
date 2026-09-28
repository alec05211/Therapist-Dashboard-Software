# Speaker names and review samples

Identification settings supply the default client and therapist names and optional
pronouns used by
database-backed transcript reads, including authorized client-portal transcripts.
The provider labels remain unchanged in stored source segments. Exact primary
labels `PATIENT` / `PATIENT_0` and `CLINICIAN` / `CLINICIAN_0` use the corresponding
default names (case-insensitively). Existing per-transcript corrections take
precedence. Without a saved profile, the client record and an unambiguous session
therapist participant supply defaults.

The settings UI identifies the relationship once rather than repeating controls
for each session. It shows compact Client and Therapist rows, exposes the provider
codes (`PATIENT_0` and `CLINICIAN_0`) through info tooltips, and plays a stored
sample pointer from an eligible matching segment. Samples prefer the longest
available turn and are capped at ten seconds. They use existing authorized
recording routes; no separate audio files or voiceprints are created. These are
listening aids for manual confirmation, not automated identity recognition.

HealthScribe jobs request up to six speakers by default. Every distinct returned
label—including `PATIENT_1`, `CLINICIAN_1`, or another numbered participant—is
persisted with a sample pointer in `app.transcript_speaker_samples`. This is
automatic diarization, not identity recognition: provider label numbering is not
a durable identity across recordings, so the UI does not treat additional labels
as relationship identities. Existing
per-transcript corrections remain authoritative, but relationship-level saves do
not create or change those overrides.

Profile updates commit after the existing relationship and clinical-write checks.
No schema migration is required because the profile table already stores optional
pronouns. Legacy file-only transcripts retain their existing explicit speaker mappings.

Validation: unit coverage for correction precedence, unknown/additional labels,
scoped defaults, sample duration and provenance, stale/cross-client rejection,
and resetting one override. Read-only demo checks verify all discovered speaker
rows have usable sample metadata and both primary labels resolve to names.
