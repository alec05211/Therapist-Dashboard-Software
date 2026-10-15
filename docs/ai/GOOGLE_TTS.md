# Google Cloud Gemini-TTS script

`tools/google_tts.py` converts a UTF-8 text file into an MP3 or WAV file using
the Google Cloud Text-to-Speech API and a Gemini-TTS voice.

## One-time setup

1. Enable billing and the Cloud Text-to-Speech API for the credential's Google
   Cloud project.
2. Grant the service account permission to use Gemini-TTS. Google currently
   documents the Vertex AI User role (`roles/aiplatform.user`) as providing the
   required `aiplatform.endpoints.predict` permission.
3. Install the project's Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

The local service-account key is expected at
`.secrets/google_tts-script-runner_key.json`. The entire `.secrets` directory is
ignored by Git. Never commit or share this key.

## Create audio

Create an MP3 next to the source text file:

```powershell
python tools/google_tts.py "C:\path\to\narration.txt"
```

Create a WAV at a specific path:

```powershell
python tools/google_tts.py "C:\path\to\narration.txt" -o "C:\path\to\narration.wav"
```

Choose a voice and give delivery instructions:

```powershell
python tools/google_tts.py "C:\path\to\narration.txt" `
  --voice Charon `
  --prompt "Speak slowly, warmly, and conversationally." `
  -o "C:\path\to\narration.mp3"
```

Use `--overwrite` to replace an existing output file. Run
`python tools/google_tts.py --help` to see every option.

## Limits and privacy

The synchronous Cloud TTS endpoint currently limits each `text` and `prompt`
field to 4,000 UTF-8 bytes. The script checks that limit before sending data.
Split longer source material into multiple text files.

Text is sent to Google Cloud for synthesis. Do not use identifiable therapy or
clinical content unless the project's consent, contractual, access, retention,
and other sensitive-data requirements have been approved.
