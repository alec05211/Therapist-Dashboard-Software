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

### Moving this workflow to another Windows machine

The current scripts explicitly load a **Google Cloud service-account JSON key**
using `--credentials`. They do not read `GEMINI_API_KEY`, `GOOGLE_API_KEY`, or
automatically use `GOOGLE_APPLICATION_CREDENTIALS`. A Gemini AI Studio API key
alone does not configure this script's authentication path.

Use the existing Google Cloud project and service account if appropriate. The
default local filename above is a repository convention, not a searchable Google
Cloud key name. Existing private key material cannot be downloaded again from
the console. If the authorized original file cannot be securely transferred,
create a replacement only under the account's credential-management policy;
review whether the old key should be retired. Do not commit keys or paste them
into chat. [Google service-account key guidance](https://cloud.google.com/iam/docs/keys-create-delete).

After authorized credential setup, use the repository's Python environment to
avoid installing into a different interpreter:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Billing, API enablement, authenticated identity, and
`aiplatform.endpoints.predict` permission must be checked separately from local
file presence. An authentication check alone does not establish successful TTS
generation. See [Gemini-TTS setup](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)
and [Cloud TTS authentication](https://docs.cloud.google.com/text-to-speech/docs/authentication).

Voice samples are available in the Gemini-TTS voice table. Owen's current
fixture uses Orus with quiet, reserved delivery; Jeremy's established voice is
Sadaltager. `tools/google_tts_dialogue.py` accepts explicit speaker aliases and
voices, but the caller must still pass the case-specific performance prompt.

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
