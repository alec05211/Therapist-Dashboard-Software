# Therapist-Dashboard-Software
Therapist Sidekick is an all-in-one digital platform designed to reduce the administrative and cognitive overhead associated with managing a psychotherapy practice.

## Minimal microphone recorder

This starter records from the browser microphone and sends the resulting file to a **local** WhisperX server for transcription.

1. Install [FFmpeg](https://ffmpeg.org/download.html) and make sure it is available from your command line. WhisperX uses it to read browser-recorded WebM audio.
2. Create and activate a Python virtual environment, then install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   WhisperX also requires a compatible PyTorch install; follow the [PyTorch install selector](https://pytorch.org/get-started/locally/) first if you want GPU acceleration.
3. Start the local server:

   ```powershell
   uvicorn server:app --reload
   ```
4. Visit `http://127.0.0.1:8000`, allow microphone access, and click **Record**. The button changes to **Stop**; stopping it displays the transcript.

Each recording is saved locally in the `recordings` folder and is available for playback or download after transcription. A JSON file with the same name stores the full transcript and timestamped segments. Treat this folder as sensitive client data and protect it accordingly.

By default it uses WhisperX's small `base` model on CPU. You can choose a model or GPU before starting the server, for example:

```powershell
$env:WHISPERX_MODEL = "small"
$env:WHISPERX_DEVICE = "cuda"
$env:WHISPERX_COMPUTE_TYPE = "float16"
uvicorn server:app --reload
```

## Speaker diarization

WhisperX can label each timestamped segment with a speaker ID. Create a Hugging Face read token and accept the access terms for the `pyannote/speaker-diarization-community-1` model, then set the token before starting the server:

```powershell
$env:HF_TOKEN = "your_hugging_face_token"
$env:WHISPERX_DIARIZE = "true"
uvicorn server:app --reload
```

When diarization is enabled, the app first creates word timestamps and then splits
the transcript at every diarized speaker change. This makes each conversational
turn individually clickable for playback, rather than showing Whisper's longer
pause-based chunks. It assumes two speakers by default; for a group session set
`WHISPERX_NUM_SPEAKERS` to the exact participant count, or set it to `0` to let
pyannote infer the count.

The app stores these labels in `transcript.json`; use the Saved transcripts viewer to rename them, for example to `Therapist` and `Client`.
