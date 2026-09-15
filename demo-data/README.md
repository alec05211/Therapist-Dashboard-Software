# Synthetic demonstration data

This directory is the repository's versioned synthetic-data closet. It holds planning materials and, later, fictional scripts and other source artifacts for demonstrations.

Everything placed here must be fictional. Do not add a real client name, recording, transcript, or identifiable health information. Audio and HealthScribe output created locally should remain outside version control unless a future decision establishes a safe, explicit repository policy for synthetic artifacts.

`heartwell-case-direction.docx` is the planning outline for the future Jeremy Heartwell and Elena Sadić case. It does not seed the application or call any external service.

`legacy-test-session` contains the original generated audio and its complete HealthScribe outputs. It is retained only as a temporary legacy demonstration fixture until a purpose-built Elena Sadić recording replaces it. Its contents use the former Maya scenario and should not be treated as part of the Heartwell case.

`heartwell-sadic-case/session-01-intake-and-stabilization.txt` is the first source script for the Heartwell and Sadić case. It includes a general session summary for future comparison with generated HealthScribe artifacts.

## Staging the first Elena Sadić recording

For local testing only, upload the synthetic Session 01 WAV through the local API. The endpoint accepts only WAV files, limits uploads to 100 MB, and will not overwrite an existing recording.

```powershell
curl.exe -X POST http://127.0.0.1:8000/demo/heartwell-sadic/session-01/audio `
  -F "audio=@C:\path\to\elena-and-jeremy-session-01.wav"
```

The file is stored as `heartwell-sadic-case/session-01-intake-and-stabilization/recording.wav`. This staging endpoint does not invoke HealthScribe; submit the recording through the normal processing flow only when you are ready to create the next set of generated artifacts.

To process the staged synthetic recording while keeping the results in the data closet, call:

```powershell
curl.exe -X POST http://127.0.0.1:8000/demo/heartwell-sadic/session-01/process
```

This creates a batch HealthScribe job. Its status and raw transcript, draft clinical document, and normalized transcript are written beside the Session 01 WAV when processing finishes.
