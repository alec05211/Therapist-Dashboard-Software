from collections import defaultdict
from functools import lru_cache
import base64
import logging
from time import monotonic
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from speaker_matching import suggest_assignments


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@lru_cache(maxsize=1)
def encoder():
    from speechbrain.inference.speaker import EncoderClassifier
    return EncoderClassifier.from_hparams(source="/var/task/model", savedir="/tmp/speaker-model",
                                          overrides={"pretrained_path": "/var/task/model"},
                                          run_opts={"device": "cpu"})


def embedding(path, start, duration):
    import numpy as np
    import torch
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-ss", str(start), "-i", str(path),
         "-t", str(duration), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
        check=True, capture_output=True, timeout=30,
    )
    samples = np.frombuffer(result.stdout, dtype="<f4").copy()
    if len(samples) < 32000 or np.sqrt(np.mean(samples ** 2)) < 0.005:
        return None
    with torch.no_grad():
        return encoder().encode_batch(torch.from_numpy(samples).unsqueeze(0)).flatten().tolist()


def handler(event, context):
    operation = event.get("operation")
    if operation not in {"enroll", "match"}:
        raise ValueError("Unknown speaker operation")
    request_id = context.aws_request_id
    started = monotonic()
    logger.info("speaker_worker_started request_id=%s operation=%s", request_id, operation)
    try:
        result = process(event, request_id)
    except Exception as exc:
        logger.error("speaker_worker_failed request_id=%s operation=%s error_type=%s",
                     request_id, operation, type(exc).__name__)
        raise RuntimeError("Speaker worker processing failed") from None
    logger.info("speaker_worker_completed request_id=%s operation=%s elapsed_ms=%d result_count=%d",
                request_id, operation, (monotonic() - started) * 1000, len(result))
    return result


def process(event, request_id):
    with TemporaryDirectory() as directory:
        path = Path(directory) / "audio"
        if event["operation"] == "enroll":
            path.write_bytes(base64.b64decode(event["audio"], validate=True))
            try:
                vector = embedding(path, 0, 30)
            except subprocess.CalledProcessError:
                return {}
            return {"embedding": vector} if vector else {}

        try:
            response = urlopen(event["url"], timeout=60)
        except OSError:
            raise RuntimeError("Could not download recording") from None
        with response, path.open("wb") as output:
            remaining = 512 * 1024 * 1024
            while chunk := response.read(1024 * 1024):
                remaining -= len(chunk)
                if remaining < 0:
                    raise ValueError("Recording exceeds worker size limit")
                output.write(chunk)

        logger.info("speaker_audio_loaded request_id=%s bytes=%d", request_id, path.stat().st_size)
        groups = defaultdict(list)
        for label, start, end in event["turns"]:
            if end - start >= 2.5:
                groups[label].append((start, min(end - start, 8)))
        clips = []
        for label, turns in groups.items():
            turns.sort()
            sample_count = min(len(turns), 7)
            for index in range(sample_count):
                sample_index = index * (len(turns) - 1) // max(1, sample_count - 1)
                start, duration = turns[sample_index]
                vector = embedding(path, start, duration)
                if vector:
                    clips.append((label, vector))
        logger.info("speaker_clips_encoded request_id=%s groups=%d clips=%d", request_id, len(groups), len(clips))
        return suggest_assignments(clips, event["references"],
                                   threshold=float(os.environ["VOICE_MATCH_THRESHOLD"]),
                                   margin=float(os.environ["VOICE_MATCH_MARGIN"]))
