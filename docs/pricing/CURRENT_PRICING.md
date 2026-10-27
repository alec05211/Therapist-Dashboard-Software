# Current architecture pricing

**Last verified:** October 26, 2026. **Currency:** USD, before tax. **Status:** planning estimate, not an invoice or customer subscription price.

This document estimates Auth0 Enterprise, recorded-session processing, and OpenAI synthesis for the current architecture. A client means a person receiving care; an Auth0 monthly active user (MAU) means an active login identity. These counts are different, especially when therapists and administrators also sign in.

## Planning assumptions

| Input | Working assumption |
| --- | --- |
| Sessions per client | 4 per month; 48 per year. Weekly attendance averaged across 52 weeks costs more. |
| Session lengths | 60, 90, and 120 recorded minutes; silence and conversation around the appointment still count when processed. |
| AWS Region | US East (N. Virginia), matching the Terraform default. |
| OpenAI model | `gpt-6-astra` as an illustrative budget scenario, not a selected production synthesis model. |
| Normal generation per session | One transcript proposal analysis, one coordinated Insights refresh, and one brief for an upcoming appointment. |
| Discounts | No free tiers, negotiated discounts, caching savings, or Batch discounts assumed. |

The example configuration leaves `JOURNEY_PROPOSAL_MODEL`, `INSIGHTS_MODEL`, and `PRE_SESSION_MODEL` empty. Actual spend depends on deployment configuration and recorded token usage; no secrets or live account configuration were inspected for this estimate.

## Auth0 Enterprise pricing

Auth0 lists Enterprise as custom pricing, so a defensible dollar total requires a sales quote. Its advertised self-service plans are not an Enterprise price substitute. [Official Auth0 pricing](https://auth0.com/pricing).

| Cost item | Current pricing treatment | Information needed |
| --- | --- | --- |
| Enterprise subscription | **Quote required: A per month** | Contract minimum, term, included MAUs, and overage rates. |
| Organizations and enterprise SSO | Confirm in quote | Expected practice organizations, SSO connections, and enterprise tiers. |
| Security, support, and compliance | Confirm in quote | MFA requirements, SLA/support, and applicable BAA scope. |
| Additional usage and environments | Confirm in quote | Machine-to-machine tokens, production/development tenants, and any add-ons. |

Allocate the shared monthly Auth0 bill as `A / N` per client when budgeting across `N` active care clients. This is an accounting allocation, not Auth0's billing unit. Do not assume every client is an MAU or that only clients count toward MAUs.

## Amazon HealthScribe and lengthy sessions

The current recording workflow uses asynchronous batch HealthScribe jobs. Published N. Virginia pricing is **$0.001667 per audio second**, billed in one-second increments with a 15-second minimum per request. Transcription, speaker-role identification, and clinical-document summarization are included. Do not add a separate transcription or initial draft-note charge for the same HealthScribe job. [Official AWS HealthScribe pricing](https://aws.amazon.com/healthscribe/pricing/).

| Recorded session | Per session | Per client/month: 4 sessions | Per client/year: 48 sessions |
| --- | ---: | ---: | ---: |
| 60 minutes | $6.00 | $24.00 | $288.06 |
| 90 minutes | $9.00 | $36.01 | $432.09 |
| 120 minutes | $12.00 | $48.01 | $576.12 |

These figures use the published per-second rate and round only the final result. AWS also describes this as approximately $0.10 per minute; the small difference comes from its published rate precision. Reprocessing the same recording can add another processing charge. Free-tier allowances are temporary and excluded from steady-state budgeting.

## OpenAI model calls for synthesis

The current pipeline adds transcript proposal analysis after HealthScribe, generates Insights in one coordinated request, and condenses validated Insights into a read-only pre-session brief. Review/finalization changes can trigger further Insights refreshes; page views do not. Closely timed events may coalesce. A normal session is therefore not a guaranteed fixed number of calls. See the [generation lifecycle](../ai/harness/CLINICAL_SYNTHESIS_GENERATION_LIFECYCLE.md).

Published standard token rates below are per **one million tokens**, using the short-context pricing view. They are comparison scenarios, not a model-selection decision. [Official OpenAI API pricing](https://developers.openai.com/api/docs/pricing).

| Illustrative model | Input | Output | Cached input |
| --- | ---: | ---: | ---: |
| `gpt-6-astra` | $10.00 | $50.00 | $1.00 |
| `gpt-6.1-sol` | $2.00 | $10.00 | $0.10 |
| `gpt-6-luna` | $0.10 | $0.50 | $0.01 |

Use the actual model, context tier, and service tier before relying on a forecast. Regional processing and eligible FedRAMP endpoints have a published 10% uplift. Budget reasoning tokens within billed output, rather than counting only visible prose. The estimates below assume uncached input and no uplift.

### Illustrative call budget

Token volumes are explicit planning assumptions, not measured application averages. Input includes instructions, schemas, transcript/evidence, and history. Output budgets represent total billable output. Longer sessions or larger clinical histories can exceed these assumptions.

| Work per session cycle | Calls | Input tokens per call | Billed output tokens per call | Cost at Astra rates |
| --- | ---: | ---: | ---: | ---: |
| Transcript proposal analysis | 1 | 30,000 | 4,000 | $0.50 |
| Coordinated Insights synthesis | 1 | 40,200 | 6,320 | $0.72 |
| Downstream pre-session brief | 1 | 8,000 | 2,000 | $0.18 |
| **Normal cycle** | **3** | **78,200 total** | **12,320 total** | **$1.40** |
| Additional Insights + brief refresh | 2 | 48,200 total | 8,320 total | $0.90 |

Section-summary planning update (2026-10-27): the same coordinated Insights request now emits up to four distinct summaries of at most 280 characters each. Allow an additional 200 input tokens for instructions/schema and 320 output tokens per request (unmeasured planning estimates, not token ceilings). This adds $0.018 per Insights call at the published standard short-context Astra rates ($10/M input, $50/M output), or $0.072 over four normal cycles; tables round only final dollar amounts. The unrounded normal-cycle estimate is $1.398. No extra request, refresh trigger, retry allowance, or output cap is added. Actual usage and any downstream brief-context growth must be measured; the existing 8,000-token brief-input estimate is assumed to include this small metadata addition. Rates verified 2026-10-27 against [official OpenAI pricing](https://developers.openai.com/api/docs/pricing).

Formula: `call cost = input tokens / 1,000,000 × input rate + billed output tokens / 1,000,000 × output rate`.

At four normal cycles, this is **$5.59 per client/month** with Astra. The same assumed token volumes would cost **$1.1184** with Sol or **$0.05592** with Luna; equal token volumes do not imply equal clinical quality or equivalent behavior.

### Repairs, retries, and growth

Insights permits up to three additional whole-document repair calls. Its output cap is 30,000 tokens per request; proposal analysis caps output at 16,000 and the brief at 6,000. Caps are limits, not expected usage. See [Insights implementation](../../ai_harness/longitudinal_insights.py), [proposal analysis](../../ai_harness/journey_proposals.py), and [brief generation](../../ai_harness/pre_session.py).

At the assumed 40,200 input and 6,320 output tokens, three extra Insights repairs add **$2.15** to a cycle. Actual repair inputs include the invalid document and errors, so this is a sensitivity example rather than a ceiling. Queue retries, edits after finalization, changed transcripts, and administrative reprocessing can add calls even if no usable result is published. An absent upcoming appointment can remove the brief call.

Replace these assumptions with observed calls and input/cached/output usage by task and model. Track normal generations separately from repairs and retries; reprice larger context packets as the client's history grows. The application currently sends ordinary model requests; background execution alone does not obtain OpenAI Batch pricing.

### Context capacity and evidence compaction (October 26, 2026)

The shared context cap increases from 110,000 to 250,000 UTF-8 bytes; the complete initial/repair Insights request cap increases from 180,000 to 350,000 bytes. Synthesis now sends eligible evidence bodies once, uses source-ID references for repeated context citations, and keeps unique pending-proposal evidence separate and unreviewed. Source-count limits, model selection, output caps, generation triggers, and retry counts are unchanged. This removes duplicate input but also permits larger histories that previously failed before a billable provider call. A recovered queue revision may incur an Insights call, up to three repairs, and a downstream brief; repeated queue attempts can multiply those costs.

The hosted demo was verified to use `gpt-5` for Insights and briefs. Published standard GPT-5 rates are $1.25/million input tokens, $0.125/million cached input tokens, and $10/million output tokens, verified October 26, 2026. [Official GPT-5 pricing](https://developers.openai.com/api/docs/models/gpt-5). Each additional 10,000 uncached input tokens therefore costs $0.0125 per request with GPT-5, or $0.10 at the Astra scenario rate above. Conversely, removing that many duplicate input tokens saves those amounts per request; repairs resubmit context and repeat the input cost.

At the same illustrative 78,000 input/12,000 output token normal-cycle budget, GPT-5 costs $0.2175 per cycle and $0.87 per client/month for four cycles. An additional Insights/brief refresh at 48,000 input/8,000 output costs $0.14, and three Insights repairs at 40,000 input/6,000 output each add $0.33. These are planning scenarios, not measured usage. The existing Astra tables and totals retain their stated token assumptions and are unchanged. Actual net savings or increased spend from compaction and newly successful larger requests remain unquantified until per-request token usage is measured; byte limits cannot be converted into a fixed token count or dollar ceiling.

## Costs still to price

Database credential recovery (verified October 27, 2026): the API continues to cache its managed database credential during successful operation. A PostgreSQL password-authentication rejection now permits one credential refresh and one connection retry, with a 30-second per-process refresh cooldown and shared-cache reuse across concurrent threads. Network failures do not refresh credentials; explicitly injected credentials and database URLs retain their existing configuration path. No SQL transaction or model generation is replayed by this recovery. Additional Secrets Manager reads are therefore driven by credential changes or repeated authentication failures, rather than every workspace request.

AWS publishes $0.05 per 10,000 Secrets Manager API calls and $0.40 per secret/month. [Official AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/). Illustratively, four refreshes/month/process add $0.00002 in API-call charges; persistent password rejection at the 30-second cooldown permits approximately 86,400 refreshes per 30 days/process, or $0.432 in additional API-call charges, excluding process restarts, initial reads, other secret consumers, KMS, networking, and taxes. These are planning scenarios, not observed usage or an account-wide cost ceiling. No additional secret is provisioned, and the existing processing-service totals are unchanged. Actual rotation frequency, process count, and failure traffic must be measured for a forecast.

Client diagnostics adds an indexed operational event table with a 30-day trace window, pruning older rows on the next diagnostic write for that client. A successful worker attempt records seven stage events, with up to three additional Insights repair events; failed/retried attempts add their own traces. Each append performs an insert plus a client-scoped retention delete. Existing review/upload ledgers are read rather than copied. No clinical prompts, model responses, or source text are duplicated into diagnostic storage.

While Diagnostics is open, visible, and unpaused, the UI polls once per ten seconds: up to 360 API reads and 1,800 bounded SQL SELECTs per active viewing hour (five SELECTs/read). Opening, reading, pausing, or resuming diagnostics never calls a model or queues work. As a storage sizing example only, assuming 1 KB per stage event including row/index overhead, four successful attempts/month/client would retain roughly 28 KB/client or 2.8 MB for 100 clients over 30 days, before extra reviews, repairs, retries, backups, and database overhead. These are unmeasured planning assumptions. Dollar impact remains unpriced until actual event size, polling-viewer hours, RDS capacity/I/O, backup retention, and API/network usage are measured against the selected hosting rates; existing model-call budget tables are unchanged.

| Architecture cost | Why it affects the full operating total |
| --- | --- |
| PostgreSQL/RDS, API hosting, and workers | Instance sizes, uptime, concurrency, and deployment topology determine charges. |
| S3 and retention | Organization audio, provider artifacts, object versions, requests, backups, and playback transfer accumulate over time. |
| Encryption, secrets, networking, and logs | KMS keys/requests, secret storage, network paths, and observability add shared and usage charges. |
| Other model features | Insurance-card extraction, experiments, and evaluation runs are outside the synthesis scenario above. |

These are **unpriced**, not zero. The tables below total the requested processing services and explicitly carry the remaining costs as variables.

## Total

Normal Astra usage is assumed at every session length below to isolate the effect of recorded minutes. Longer transcripts may increase token usage, so these are scenarios rather than upper bounds.

| Session length | HealthScribe/client/month | OpenAI/client/month | Priced usage subtotal/client/month | 100 clients/month |
| --- | ---: | ---: | ---: | ---: |
| 60 minutes × 4 | $24.00 | $5.52 | **$29.52** | **$2,952.48** |
| 90 minutes × 4 | $36.01 | $5.52 | **$41.53** | **$4,152.72** |
| 120 minutes × 4 | $48.01 | $5.52 | **$53.53** | **$5,352.96** |

Fleet totals use unrounded component costs. For the lengthy-session scenario of **100 clients, four 90-minute sessions each month**, the priced usage subtotal is **$4,152.72/month**, or **$49,832.64/year** at unchanged volume and rates.

**Full monthly operating total = $4,152.72 + A + H + E**, where `A` is the monthly Auth0 Enterprise contract cost, `H` is hosting/storage/operations, and `E` is extra generations, retries, and other excluded usage. Per client, divide that full total by 100. A final all-in dollar total remains pending the Auth0 quote and infrastructure sizing.
