# Therapist-Dashboard-Software
Therapist Sidekick is an all-in-one digital platform designed to reduce the administrative and cognitive overhead associated with managing a psychotherapy practice.

## HealthScribe microphone recorder

This starter records from the browser microphone and sends the resulting file to
Amazon HealthScribe for asynchronous transcription and draft clinical-note
generation. The original recording plus HealthScribe's raw transcript, raw
clinical note, and UI-ready transcript are saved together in a local session
folder under `recordings`.

1. Apply the Terraform infrastructure and add the three `HEALTHSCRIBE_*` values
   from `terraform output` to your local `.env` file. See
   [the startup guide](docs/startup.md).
2. Sign in to AWS IAM Identity Center and select the Terraform profile:

   ```powershell
   aws sso login --profile terraform
   $env:AWS_PROFILE = "terraform"
   ```

3. Create and activate a Python virtual environment, then install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Start the local server:

   ```powershell
   uvicorn server:app --reload
   ```
4. Visit `http://127.0.0.1:8000`, allow microphone access, and click **Record**. The button changes to **Stop**; stopping it displays the transcript.

Each recording is saved locally in the `recordings` folder and is available for
playback or download after processing. HealthScribe's generated content is a
draft and must be reviewed before use. Treat this folder as sensitive client data
and protect it accordingly.
