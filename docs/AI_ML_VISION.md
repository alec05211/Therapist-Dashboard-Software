# AI / ML Vision and Learning Direction

> A living strategy for the product's AI and machine-learning work. This document captures both a product conviction and a learning agenda: the goal is not merely to replace a vendor, but to develop accountable, purpose-built intelligence for psychiatric care.

**Last updated:** 2026-09-01  
**Status:** Long-term direction; HealthScribe remains the current early-development provider

## 1. Intent

The product will initially use Amazon HealthScribe to validate the session workflow, but the long-term aim is to understand, evaluate, and selectively build the ML capabilities that matter most for psychiatric and therapeutic care.

The desired end state is not necessarily a single model built entirely from scratch. It is an accountable, purpose-built system in which the team can understand the components, evaluate their behavior for the intended setting, control the data and workflows, and improve the capabilities that create real value for therapists and clients.

## 2. Why this direction matters

AWS HealthScribe is closed source. It is useful and effective for early development, but it limits visibility into model behavior, task-specific tradeoffs, evaluation methods, and the choices behind generated output.

For a tool handling psychiatric sessions, generic medical transcription and note generation may not be sufficient in the long run. Therapeutic conversations have distinctive characteristics:

- Nuance often exists in pauses, hedging, emotion, repair, and tone—not just literal words.
- Speaker identity and role matter to the meaning of a conversation.
- Context accumulates across sessions and relationships over long periods.
- A therapist needs evidence, control, and the ability to correct or reject assistance.
- Privacy, consent, safety, and the consequences of error are unusually important.

The project therefore intends to build knowledge and eventually custom capabilities for transcription, diarization, session synthesis, and longitudinal insight—not to automate therapy or replace clinical judgment.

## 3. Long-term capability areas

### A. Psychiatric / therapy-aware transcription

Develop or integrate transcription capabilities that can be evaluated specifically for therapy-session language and real recording conditions.

Desired qualities include accurate words, useful punctuation and segmentation, appropriate handling of disfluencies, correct terminology when relevant, and transparent correction workflows.

### B. Flexible speaker diarization

Identify and separate speakers with timing suitable for synchronized playback and review.

The system must eventually support more than a simple therapist-client pair, including atypical sessions with a partner, family member, caregiver, interpreter, supervisor, or other participant. Speaker attribution should remain correctable by the therapist.

### C. Session synthesis and draft clinical support

Produce reviewable, therapist-controlled summaries and structured key points from finalized session records.

The purpose is to reduce administrative and cognitive burden while preserving the nuance of the session. Outputs should distinguish source-grounded information from inference and should never present themselves as authoritative clinical judgment.

### D. Longitudinal memory and insight

Use the collection of finalized sessions for a particular therapist-client relationship to surface relevant themes, changes, recurring topics, open threads, and useful context over time.

Longitudinal memory should be selective, attributable, and controllable. It must not become an opaque or indiscriminate store of sensitive content.

### E. Exploratory audio and video signals

Audio cues such as tone, pacing, pauses, and emphasis—and potentially video cues such as body language—may eventually be useful for review. This area is exploratory and secondary to accurate core capture, transcription, diarization, and clinician-controlled synthesis.

No such signal should be framed as a diagnosis, emotion certainty, risk determination, or clinical conclusion without a rigorous, validated, and ethically appropriate basis.

## 4. Design principles for AI/ML work

- **Clinical support, not clinical replacement:** models assist therapists; therapists retain judgment and control.
- **Human review by design:** important outputs should be inspectable, editable, accepted, or rejected.
- **Grounding and attribution:** where possible, generated content should connect back to source transcript segments and recordings.
- **Purpose-built evaluation:** assess capabilities against representative therapeutic tasks, not generic benchmark performance alone.
- **Privacy and consent first:** sensitive data use, retention, access, and training choices require explicit policies and safeguards.
- **Accountability over novelty:** prefer systems whose behavior, limitations, provenance, and failure modes can be documented and improved.
- **Progressive development:** validate user value and safety one capability at a time before expanding scope.
- **No overstated inference:** avoid presenting model-derived cues or trends as facts, diagnoses, or predictions.

## 5. The learning agenda

Building ML capability is also a deliberate learning path. The project should steadily develop understanding in these areas:

| Area | What to learn | Why it matters here |
| --- | --- | --- |
| Speech recognition | Audio preprocessing, automatic speech recognition, domain adaptation, word timestamps, and error analysis | Reliable transcripts are the foundation of every downstream feature |
| Speaker diarization | Speaker embeddings, segmentation, clustering, overlap handling, diarization error rate, and speaker-label correction | Accurate speaker attribution and timing are essential for review and context |
| Language models | Prompting, retrieval, structured output, grounding, evaluation, fine-tuning tradeoffs, and hallucination control | Enables useful but reviewable summaries and longitudinal assistance |
| Information retrieval / memory | Session indexing, embeddings, metadata, retrieval quality, temporal context, and memory controls | Makes longitudinal insights relevant instead of indiscriminate |
| Evaluation | Representative test sets, human review rubrics, error taxonomies, baseline comparisons, and regression testing | Makes progress measurable and model behavior accountable |
| Privacy and security | De-identification, access controls, encryption, retention, data lineage, consent, and secure deployment | Required because the source data is highly sensitive |
| Responsible clinical AI | Bias, uncertainty, oversight, intended use, limitations, and human factors | Prevents harmful overreach in a high-stakes setting |

## 6. Development approach

### Near term: learn from the existing product

- Use HealthScribe as a baseline for the end-to-end experience.
- Preserve raw source outputs and normalized application outputs for inspection.
- Collect structured feedback on transcript quality, speaker-label quality, note usefulness, and review friction.
- Define what “good enough” means for the product's actual users before choosing a custom replacement path.

### Medium term: build evaluation before replacement

- Create a consented, securely governed evaluation set that represents intended session conditions and edge cases.
- Define metrics for transcript accuracy, diarization accuracy, timestamp alignment, summary faithfulness, and longitudinal retrieval relevance.
- Establish a human-review rubric for therapist usefulness and safety.
- Compare candidate open, hosted, and custom components to the HealthScribe baseline.
- Experiment with modular components so transcription, diarization, summarization, and memory can evolve independently.

### Long term: own the differentiating intelligence

- Customize, train, fine-tune, or assemble components where evidence shows a material benefit for psychiatric care.
- Maintain reproducible evaluation, versioning, documentation, monitoring, and rollback practices.
- Keep models and data flows configurable enough to adapt as product requirements, policies, and evidence change.

## 7. What “custom built” should mean

Custom built does not automatically mean training a foundation model from zero. That path is expensive, data-intensive, and may not be the responsible or most useful choice.

For this project, custom built means owning the product-specific system design and the evidence behind it. Depending on the capability, that may include:

- Selecting and evaluating open or commercial base models.
- Building specialized preprocessing, segmentation, speaker-labeling, retrieval, and review workflows.
- Fine-tuning or adapting models only when there is sufficient governed data, a demonstrated need, and a clear evaluation plan.
- Designing the longitudinal-memory layer, controls, source linking, and therapist-facing interaction specifically for this product.
- Operating an evaluation and monitoring process that makes limitations visible.

## 8. Safety, privacy, and governance gates

Before an AI/ML capability moves from exploration into real clinical use, define and satisfy appropriate gates for:

- Intended use and explicit non-use boundaries.
- Informed consent and permissions for recording, analysis, storage, and any training/evaluation use.
- Data minimization, retention, deletion, access control, encryption, and auditability.
- Evaluation against representative data and relevant quality thresholds.
- Bias and failure-mode analysis, including multi-speaker and vulnerable-user scenarios.
- Therapist review, correction, escalation, and override workflows.
- Clear user communication about what the system does, does not do, and how generated content should be used.
- Legal, regulatory, clinical-policy, and security review appropriate to the release scope.

## 9. Explicit non-goals

- Diagnose a client, determine risk, or make treatment decisions autonomously.
- Represent inferred tone, emotion, or body-language analysis as objective fact.
- Use sensitive session data for model training or evaluation without appropriate consent, governance, and safeguards.
- Replace therapists' notes, reasoning, or responsibility with generated output.
- Pursue custom models merely for ownership when a well-evaluated component is safer or more effective.

## 10. How to evaluate proposed AI/ML work

For every proposed AI/ML feature, experiment, or integration, document:

1. The specific therapist or client problem it solves.
2. The input data it requires and the permission/retention implications.
3. The expected output and who will review or act on it.
4. The baseline it must improve upon (including HealthScribe where relevant).
5. The success metrics and meaningful failure modes.
6. How the output is grounded in or linked to source material.
7. The safety, privacy, bias, and misuse risks.
8. Whether it belongs in the current phase or remains research.

## 11. Current decisions and open questions

### Current decisions

- Amazon HealthScribe is the early-development provider for batch transcription, diarization, and generated clinical documentation.
- The current system is a baseline to learn from, not the final ML architecture.
- Transcript review and therapist control are core product requirements.
- Longitudinal insight is a major long-term direction, not a near-term excuse to collect or infer indiscriminately.

### Open questions to maintain

- What quality thresholds make an in-house or alternative component worth adopting?
- Which parts of the pipeline are truly differentiating for psychiatric care?
- What consent and data-governance model will allow safe evaluation and improvement?
- Which longitudinal insights are genuinely useful to therapists and clients, and how should they be presented?
- When, if ever, do audio/video cue analyses provide enough value and reliability to justify inclusion?

## 12. Living-document maintenance

Update this document when ML priorities, use cases, evidence, evaluation criteria, provider choices, governance decisions, or learning goals change. For each new initiative, record whether it is:

- **Current product work** — approved for implementation.
- **Experiment** — bounded research with a defined question and evaluation.
- **Future direction** — valuable but not yet ready to build.
- **Non-goal** — intentionally excluded.

Keep [PROJECT_VISION.md](PROJECT_VISION.md) as the source of truth for overall product direction, and [HEALTHSCRIBE.md](HEALTHSCRIBE.md) as the current provider/infrastructure reference.
