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

Each recording is saved locally in the `recordings` folder and is available for playback or download after transcription. Treat this folder as sensitive client data and protect it accordingly.

By default it uses WhisperX's small `base` model on CPU. You can choose a model or GPU before starting the server, for example:

```powershell
$env:WHISPERX_MODEL = "small"
$env:WHISPERX_DEVICE = "cuda"
$env:WHISPERX_COMPUTE_TYPE = "float16"
uvicorn server:app --reload
```
