"""Add ordinary, policy-compliant dialogue without lengthening turns into essays."""
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
    parse_parts,
    parse_turns,
    print_realism_preflight,
    print_realism_report,
    realism_report,
)


def _spoken_words(dialogue: str) -> int:
    return sum(
        len(re.findall(r"\b[\w'’-]+\b", line.split(":", 1)[1]))
        for line in dialogue.splitlines()
        if line.startswith(("THERAPIST:", "AVERY:"))
    )


def _clean(text: str) -> str:
    text = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", text.strip(), flags=re.I)
    text = re.sub(r"^## Part \d+\s*", "", text.strip())
    return text.strip()


def _insert_context(part: str, fraction: float) -> tuple[str, str, str]:
    lines = part.strip().splitlines()
    spoken_indexes = [i for i, line in enumerate(lines) if line.startswith(("THERAPIST:", "AVERY:"))]
    if len(spoken_indexes) < 12:
        split_at = max(1, len(lines) // 2)
    else:
        split_at = spoken_indexes[min(len(spoken_indexes) - 4, max(4, int(len(spoken_indexes) * fraction)))]
    before = "\n".join(lines[:split_at]).rstrip()
    after = "\n".join(lines[split_at:]).lstrip()
    before_context = "\n".join(before.splitlines()[-16:])
    after_context = "\n".join(after.splitlines()[:16])
    return before, after, f"BEFORE:\n{before_context}\n\nAFTER:\n{after_context}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--client-alias", default="AVERY")
    parser.add_argument("--target-spoken-words", type=int, default=6800)
    parser.add_argument("--model", default="gemini-3.8-flash")
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

        source = input_path.read_text(encoding="utf-8-sig")
        parts = parse_parts(source)
        if len(parts) != 8:
            raise ValueError(f"Expected 8 parts, found {len(parts)}.")
        current_words = sum(_spoken_words(part) for part in parts)
        words_needed = max(0, args.target_spoken_words - current_words)
        inserts_per_part = min(4, max(1, (words_needed + 799) // 800))
        per_insert_target = max(80, (words_needed + (8 * inserts_per_part) - 1) // (8 * inserts_per_part))

        credentials = service_account.Credentials.from_service_account_file(
            str(args.credentials.resolve()), scopes=("https://www.googleapis.com/auth/cloud-platform",)
        )
        client = genai.Client(
            enterprise=True,
            project=args.project,
            location=args.location,
            credentials=credentials,
        )
        cache_dir = output_path.parent / f".augment_{output_path.stem}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        augmented_parts: list[str] = []

        for index, part in enumerate(parts, 1):
            augmented_part = part.strip()
            fractions = [0.35, 0.58, 0.78, 0.88]
            for insert_index in range(1, inserts_per_part + 1):
                before, after, context = _insert_context(augmented_part, fractions[insert_index - 1])
                cache_path = cache_dir / f"part-{index:02d}-insert-{insert_index:02d}.txt"
                insert = ""
                if cache_path.exists() and cache_path.stat().st_size > 100:
                    insert = cache_path.read_text(encoding="utf-8").strip()
                    print(
                        f"Part {index}/8 insert {insert_index}/{inserts_per_part} loaded from cache.",
                        flush=True,
                    )
                else:
                    prompt = f"""Write only one additional fictional therapy dialogue exchange to insert at this point.

Use exactly THERAPIST and {args.client_alias} labels. Do not add a heading or markdown fence.
Produce about {per_insert_target}-{per_insert_target + 60} spoken words total. Short turns are required.

The exchange must sound like people thinking, not reading:
- fragments, irregular um/uh, false starts, corrections, and incomplete answers;
- uncertain memory or chronology and one detail the client cannot retrieve;
- ordinary logistics, repetition, or mild topic drift that does not create a new insight;
- brief therapist backchannels or clarification; the therapist may misunderstand and accept correction;
- no diagnosis, crisis invention, polished summary, inspirational ending, or interpretation of vocal cues;
- lead naturally from BEFORE toward AFTER without repeating either passage.

INSERTION CONTEXT:
{context}
"""
                    print(
                        f"Adding ordinary dialogue to part {index}/8 insert {insert_index}/{inserts_per_part}...",
                        flush=True,
                    )
                    for attempt in range(1, 4):
                        try:
                            response = client.models.generate_content(
                                model=args.model,
                                contents=prompt,
                                config={"temperature": 0.95, "top_p": 0.95, "max_output_tokens": 2000},
                            )
                            insert = _clean(response.text or "")
                            wrapped = f"## Part {index}\n{insert}\n"
                            parsed = parse_turns(parse_parts(wrapped)[0], (args.client_alias, "THERAPIST"))
                            words = sum(len(re.findall(r"\b[\w'’-]+\b", turn["text"])) for turn in parsed)
                            if words < 40:
                                raise ValueError(f"Insert has only {words} spoken words.")
                            cache_path.write_text(insert + "\n", encoding="utf-8")
                            break
                        except Exception as exc:
                            if attempt == 3:
                                raise
                            print(
                                f"Part {index} insert {insert_index} attempt {attempt} failed: {exc}",
                                flush=True,
                            )
                            time.sleep(attempt * 3)
                augmented_part = f"{before}\n\n{insert}\n\n{after}".strip()
            augmented_parts.append(f"## Part {index}\n\n{augmented_part}".strip())

        header = "\n".join(line for line in source.splitlines() if line.startswith("# "))
        combined = header.rstrip() + "\n\n" + "\n\n".join(augmented_parts) + "\n"
        parsed_parts = [
            parse_turns(part, (args.client_alias, "THERAPIST")) for part in parse_parts(combined)
        ]
        print_realism_report(realism_report(parsed_parts, args.client_alias, combined))
        total_words = sum(_spoken_words(part) for part in parse_parts(combined))
        print(f"Total spoken words: {total_words}", flush=True)
        if total_words < args.target_spoken_words - 400:
            raise ValueError(
                f"Augmented script has {total_words} words; target was {args.target_spoken_words}."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(combined, encoding="utf-8")
        print(f"Created {output_path}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
