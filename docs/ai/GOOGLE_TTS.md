# Gemini 3.8 text to speech workflow

The repository uses Gemini 3.8 Flash TTS to create fictional single-speaker and two-speaker audio fixtures. The workflow uses the Gemini Enterprise `generateContent` API because Gemini 3.8 is not exposed through the older Cloud Text-to-Speech `synthesizeSpeech` API.

Gemini TTS is fixture-generation tooling. Amazon HealthScribe remains the current provider for transcription, diarization, and the initial clinical-document output produced from recorded sessions.

## Safety boundary

Use fictional demonstration material only. Do not send identifiable therapy recordings, transcripts, clinical notes, or other client content unless the approved data flow, contract and retention terms, consent, access controls, and applicable legal and clinical policies explicitly cover that use.

Vocal direction is a production instruction. It must not be treated as evidence of emotion, diagnosis, risk, or a clinical conclusion.

## Mandatory realism and native-timing contract

Read [Synthetic session realism contract](SYNTHETIC_SESSION_REALISM.md) before writing or rendering a session.

Every generation command prints the required preflight and refuses to call the paid API unless `--acknowledge-realism-policy` is supplied. The acknowledgment means the script was reviewed for imperfect recall, fragments, false starts, corrections, uncertainty, therapist fallibility, low-information stretches, and unresolved material.

Never globally slow down, accelerate, interpolate, or time-stretch a recording to meet a duration target. Keep Gemini's native rendered timing. If a recording is too short or too long, revise the transcript or exact assembled silence and render again.

## Current model

- Model: `gemini-3.8-flash-tts`
- API: Gemini Enterprise `generateContent`
- SDK: `google-genai>=2.33.0`
- Location: `global` for custom designed or replicated voices; `us` and `eu` are also available for prebuilt voices
- Output: complete 24 kHz mono WAV for unary requests

Gemini 3.8 Flash TTS is the fidelity-first choice for the synthetic therapy-dialogue evaluation set. Gemini 3.8 Flash-Lite TTS is available when throughput and cost matter more than acting nuance.

Official references:

- [Gemini 3.8 TTS guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/overview)
- [Gemini 3.8 model page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash-tts)
- [Migration from earlier Gemini TTS models](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/migration-guide)

## Vocal identity contract

Each client folder contains `voice-config.json`. The document and configuration use a stable logical reference such as `client-avery-chen-v1`. The logical reference separates the character identity from Google's provider-specific reference.

`provider_voice_reference` may contain one of these values:

- A prebuilt voice name such as `Aoede`
- An Extended Voice Library voice ID
- A stored designed or consent-based replicated voice ID beginning with `voice_`
- A short-lived stateless replication key beginning with `voicekey_`

Designed and replicated voices can be created once and reused. Google currently documents a one-year expiration after the last use for stored voices; using the voice refreshes that period. Store only the provider reference in configuration. Never place credentials in the client folder or the Word character document.

## Authentication

The scripts use a Google Cloud service account and require the project ID separately. Set `GOOGLE_CLOUD_PROJECT` in the process environment or pass `--project`. The default credential path remains `.secrets/google_tts-script-runner_key.json`, which is ignored by Git.

Do not paste the key into a command, document, chat, or source file. The scripts pass the credential file directly to Google's authentication library and do not print or inspect its contents.

Install the project dependencies with the repository environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Try a voice in AI Studio

Open [Gemini 3.8 Flash TTS in Google AI Studio](https://aistudio.google.com/prompts/new_chat?model=gemini-3.8-flash-tts), select a voice, enter a short fictional audition, and add a restrained style description. Use the audition only to choose a starting voice. Record the approved selection in `voice-config.json` so later sessions do not depend on remembering an AI Studio setting.

## Generate a single voice

```powershell
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"
.\.venv\Scripts\python.exe tools\google_tts.py "C:\path\to\audition.txt" `
  --voice Aoede `
  --style "Grounded conversational delivery, measured pace, restrained emotion" `
  --acknowledge-realism-policy `
  -o "C:\path\to\audition.wav"
```

The `--voice` value may be a prebuilt name or a stored `voice_` ID.

## Generate two speaker dialogue

Use eight `## Part N` sections for an approximately 50-minute session. Each spoken line must begin with one of the two exact aliases configured in `voice-config.json`.

```powershell
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"
.\.venv\Scripts\python.exe tools\google_tts_dialogue.py `
  "demo-data\Clients\Avery Chen\session-script.txt" `
  --voice-config "demo-data\Clients\Avery Chen\voice-config.json" `
  --acknowledge-realism-policy `
  -o "demo-data\Clients\Avery Chen\session.wav"
```

Gemini 3.8 expects one structured part per spoken turn. The tool displays the mandatory policy, prints script-level realism indicators, removes speaker labels, places the speaker and sustained performance direction in `speech_metadata`, converts common legacy bracketed cues to inline Gemini tags, renders each production part, and joins the WAV files.

The indicator report is a review aid, not a realism score. Word counts, detected disfluencies, and silence counts cannot replace reading and listening review.

## Native-speed finalization

Gemini unary output is 24 kHz mono WAV. When the application requires 16 kHz, finalize it with the duration-preserving tool:

```powershell
.\.venv\Scripts\python.exe tools\finalize_tts_wav.py `
  "C:\path\to\native-provider-render.wav" `
  -o "C:\path\to\final-16khz.wav" `
  --minimum-minutes 45 `
  --maximum-minutes 50
```

The finalizer rejects a provider render outside the requested duration range. It changes sample rate and encoding only, then verifies that duration was preserved. It has no tempo-adjustment option. A short render must go back to script revision or exact-silence assembly.

## Script structure

Each trajectory document defines the same eight-part session shape:

1. Arrival and baseline
2. Agenda and immediate pressure
3. Narrative detail
4. Pressure point
5. Silence and reconsideration
6. Relational turn
7. Integration and experiment
8. Closing and carry forward

The baseline voice identity remains stable across all parts. Pace, volume, response latency, breath, and sentence completion may change at the turn level. Avoid instructions that change the character's apparent identity or turn distress into spectacle.

## Acceptance review

Listen to every rendered part before using it as an evaluation fixture. Check:

- The same voice identity persists across parts and sessions
- Every scripted turn is present and in order
- Speaker assignments remain correct
- Style changes are audible but restrained
- No direction or speaker label is spoken aloud
- Pronunciation and pauses remain plausible
- The output contains no unexpected ambience, music, or exaggerated acting
- The final duration is close to the planned target
- The recording remains at native rendered speed, without phasey or interpolated whole-file stretching
- Client recall, chronology, and wording are imperfect where a real person would plausibly be uncertain
- Client turns vary in shape and are not dominated by polished paragraphs
- Therapist reflections include ordinary clarification, occasional misses, and space rather than constant accurate formulation
- The session contains confusion, repetition, topic drift, low-information time, and unresolved material

Regenerate only the failing part when possible. Reject any duration-compliant recording that still sounds scripted or globally processed. Keep the approved script, configuration, model ID, raw provider WAV, final WAV, and listening decision together until final QA so the fixture remains reproducible.
