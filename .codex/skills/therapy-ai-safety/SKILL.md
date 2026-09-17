---
name: therapy-ai-safety
description: Design or review AI features that process therapy-session data, longitudinal client context, clinical summaries, or clinician-facing insights.
---

# Therapy AI safety

Apply this skill to product, design, implementation, and evaluation work involving therapy-session recordings, transcripts, clinical notes, or longitudinal client context.

## Core boundary

The system supports clinician review; it does not diagnose a client, determine risk, or make treatment decisions. Do not represent a generated inference, trend, emotional cue, or behavioral pattern as objective fact.

Frame model-generated patterns as review prompts and make source evidence available. A qualified clinician remains responsible for interpretation and action.

## Source and correction hierarchy

Prefer therapist-finalized records over raw model output. Preserve the relationship between a generated claim and its source session, finalized note, corrected transcript segment, and—when appropriate—synchronized recording timestamp. Give therapists a way to correct, hide, delete, pin, and mark remembered information as outdated; apply those choices to future retrieval.

## Longitudinal review modes

Keep the concise pre-session brief separate from the evidence-rich clinical journey review. The brief is selective and oriented to the upcoming session; the clinical journey review enables deeper historical inspection and correction. Do not turn the brief into an indiscriminate client dossier.

## Sensitive-data boundary

Do not assume redaction or removal of direct identifiers makes therapy content safe to send to a model provider. Before using any external model with real client data, confirm the approved data flow, contractual and retention terms, access controls, and applicable privacy, legal, clinical-policy, and security requirements. Preserve a replaceable provider boundary.

## Evaluation

Evaluate with representative, appropriately governed data. Include grounding, faithfulness, relevance, correction behavior, privacy, bias, and harmful-overreach failure modes—not only output fluency. Consult [AI/ML vision](../../../docs/AI_ML_VISION.md) for product-specific strategy and governance.
