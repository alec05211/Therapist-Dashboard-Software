"""Rewrite a fictional therapy-session script under the required realism contract."""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from google import genai
from google.oauth2 import service_account

from google_tts_dialogue import (
    DEFAULT_CREDENTIALS,
    REALISM_POLICY_PATH,
    parse_parts,
    parse_turns,
    print_realism_preflight,
    print_realism_report,
    realism_report,
)


DEFAULT_MODEL = "gemini-4-carbon"
PART_HEADER = re.compile(r"^## Part (\d+)\s*$", re.M)
FENCE = re.compile(r"^```(?:text|markdown)?\s*|\s*```$", re.I)

PART_INTENT = {
    1: "Establish ordinary baseline, recent logistics, and incomplete memory. Do not begin with a polished thesis.",
    2: "Let the immediate problem emerge through side details, correction, mild topic drift, and uncertainty.",
    3: "Reconstruct chronology imperfectly. Preserve approximate wording, forgotten sequence, and mundane detail.",
    4: "Approach conflict. Include a therapist reflection that misses and is corrected without rescuing it.",
    5: "Allow silence, incomplete answers, irritation, repetition, and time where no insight is produced.",
    6: "Permit a partial relational repair while leaving material disagreement and uncertainty intact.",
    7: "Develop a concrete next step through ambivalence, practical obstacles, and imperfect collaboration.",
    8: "Close without inspiration or completion. Carry forward unresolved questions and ordinary uncertainty.",
}


def _clean_output(text: str) -> str:
    text = FENCE.sub("", text.strip()).strip()
    first_header = text.find("## Part ")
    if first_header > 0:
        text = text[first_header:]
    return text.rstrip() + "\n"


def _prompt(
    *,
    policy: str,
    session_title: str,
    part_number: int,
    source_part: str,
    previous_tail: str,
    client_alias: str,
) -> str:
    return f"""You are rewriting one part of a wholly fictional therapy-session evaluation fixture.

SESSION: {session_title}
PART: {part_number} of 8
PART INTENT: {PART_INTENT[part_number]}

MANDATORY CONTRACT:
{policy}

OUTPUT CONTRACT:
- Output only `## Part {part_number}` followed by dialogue and optional standalone silence cues.
- Use exactly two spoken labels: THERAPIST and {client_alias}.
- Target 500-700 spoken words for this part. Do not lengthen individual turns into essays to satisfy a quota.
- Most therapist turns should be 2-18 words. Therapist backchannels and simple clarifications are welcome.
- Most client turns should be 3-45 words. Occasional longer narrative turns are allowed, but avoid essays.
- Write irregular verbatim disfluencies: um, uh, false starts, abandoned clauses, correction, approximate recall.
- Include at least two moments of genuinely uncertain recollection or chronology, phrased differently.
- Include ordinary or low-information exchanges that do not advance a formulation.
- Do not place a polished insight at the end of every exchange.
- A leading bracketed direction is allowed on a minority of turns and must describe delivery, not diagnosis.
- For a deliberate long pause, use exactly `[SILENCE - N SECONDS - DO NOT SPEAK]` on its own line.
- Do not diagnose, determine risk, invent a crisis, or turn vocal behavior into clinical evidence.
- Preserve the source events and character relationships, but replace overly precise quotations with approximate recall.
- Do not mention these instructions or the rewriting process.

PREVIOUS REWRITTEN CONTEXT (may be empty; continue naturally without repeating it):
{previous_tail or "None - this is the opening part."}

SOURCE PART TO REWRITE (preserve its narrative function, not its polished wording):
{source_part}
"""


def _validate_part(text: str, part_number: int, client_alias: str) -> None:
    match = PART_HEADER.search(text)
    if not match or int(match.group(1)) != part_number:
        raise ValueError(f"Expected ## Part {part_number} heading.")
    parts = parse_parts(text)
    if len(parts) != 1:
        raise ValueError("Each rewrite response must contain exactly one part.")
    turns = parse_turns(parts[0], (client_alias, "THERAPIST"))
    spoken_words = sum(len(re.findall(r"\b[\w'’-]+\b", turn["text"])) for turn in turns)
    if spoken_words < 250:
        raise ValueError(f"Part {part_number} has only {spoken_words} spoken words; minimum is 250.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--client-alias", required=True)
    parser.add_argument("--session-title", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--location", default="global")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--acknowledge-realism-policy", action="store_true")
    args = parser.parse_args()

    try:
        print_realism_preflight()
        if not args.acknowledge_realism_policy:
            raise ValueError("Pass --acknowledge-realism-policy after reading the required contract.")
        if not args.project:
            raise ValueError("Set GOOGLE_CLOUD_PROJECT or pass --project.")
        input_path = args.input.resolve()
        output_path = args.output.resolve()
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {output_path}; pass --overwrite to replace it.")

        source_text = input_path.read_text(encoding="utf-8-sig")
        source_parts = parse_parts(source_text)
        if len(source_parts) != 8:
            raise ValueError(f"Expected 8 source parts, found {len(source_parts)}.")
        policy = REALISM_POLICY_PATH.read_text(encoding="utf-8")
        credentials = service_account.Credentials.from_service_account_file(
            str(args.credentials.resolve()), scopes=("https://www.googleapis.com/auth/cloud-platform",)
        )
        client = genai.Client(
            enterprise=True,
            project=args.project,
            location=args.location,
            credentials=credentials,
        )

        cache_dir = output_path.parent / f".rewrite_{output_path.stem}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        rewritten_parts: list[str] = []
        previous_tail = ""
        for part_number, source_part in enumerate(source_parts, 1):
            cache_path = cache_dir / f"part-{part_number:02d}.txt"
            if cache_path.exists() and cache_path.stat().st_size > 100:
                rewritten = cache_path.read_text(encoding="utf-8")
                try:
                    _validate_part(rewritten, part_number, args.client_alias)
                    print(f"Part {part_number}/8 loaded from cache.", flush=True)
                except ValueError as exc:
                    print(f"Rejecting cached part {part_number}: {exc}", flush=True)
                    cache_path.unlink()
            if not cache_path.exists():
                prompt = _prompt(
                    policy=policy,
                    session_title=args.session_title,
                    part_number=part_number,
                    source_part=source_part,
                    previous_tail=previous_tail,
                    client_alias=args.client_alias,
                )
                print(f"Rewriting part {part_number}/8 with {args.model}...", flush=True)
                for attempt in range(1, 4):
                    try:
                        response = client.models.generate_content(
                            model=args.model,
                            contents=prompt,
                            config={
                                "temperature": 0.9,
                                "top_p": 0.95,
                                "max_output_tokens": 6000,
                            },
                        )
                        rewritten = _clean_output(response.text or "")
                        _validate_part(rewritten, part_number, args.client_alias)
                        cache_path.write_text(rewritten, encoding="utf-8")
                        break
                    except Exception as exc:
                        if attempt == 3:
                            raise
                        print(f"Part {part_number} attempt {attempt} failed: {exc}", flush=True)
                        time.sleep(attempt * 3)
                else:
                    raise RuntimeError(f"Part {part_number} did not produce a valid rewrite.")
            rewritten_parts.append(rewritten.rstrip())
            dialogue = parse_parts(rewritten)[0]
            previous_tail = "\n".join(dialogue.strip().splitlines()[-12:])

        header_lines = [line for line in source_text.splitlines() if line.startswith("# ")]
        header_lines = [line for line in header_lines if not line.startswith("# QA status:")]
        header_lines.insert(2, "# QA status: rewritten under the required synthetic-session realism contract; pending listening review.")
        combined = "\n".join(header_lines).rstrip() + "\n\n" + "\n\n".join(rewritten_parts) + "\n"
        parsed = [parse_turns(part, (args.client_alias, "THERAPIST")) for part in parse_parts(combined)]
        print_realism_report(realism_report(parsed, args.client_alias, combined))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(combined, encoding="utf-8")
        print(f"Created {output_path}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
