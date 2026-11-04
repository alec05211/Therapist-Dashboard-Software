# Client care assistant scaffold

Status: OpenAI chat connected November 4, 2026; hosted demo scope. Client participation is the product
goal; this is a private client-to-assistant conversation, separate from therapist
messaging. The client-only tab sits immediately before Clinical workspace.

## Implemented boundary

Chats exist only in portal memory and are discarded on page reload or leaving
the portal. The history menu reopens chats across portal tab switches; when empty,
it shows only New chat under its centered heading. Empty-state information is
centered, non-interactive text with a shallow engraved treatment in both themes.

The composer posts to `POST /api/client-assistant/chat`, forwarded by the existing
authenticated Next.js proxy to `POST /client-assistant/chat`. The server calls the
OpenAI Responses API and returns plain-text replies. The empty state uses the
portal schedule and existing authenticated inbox/document-list reads. No clinical
retrieval, message persistence, file uploads, or new infrastructure is added.
Existing portal sharing permissions are unchanged.

## Operational read API and harness contract

Implemented in `database/client_operations.py`:

| Backend endpoint | Browser endpoint through existing authenticated proxy | Result |
| --- | --- | --- |
| `GET /client-operations/scheduling?limit=5` | `GET /api/client-operations/scheduling?limit=5` | Next 1–20 upcoming appointments; default 5, `has_more` indicates truncation. |
| `GET /client-operations/billing` | `GET /api/client-operations/billing` | Minimal insurance summary and explicit `billing.status=not_connected`. |

Each read resolves exactly one active portal/client/organization link from the
validated bearer-token subject. There is no client or organization identity
argument. Both queries scope by organization and client. Successful HTTP responses
use `Cache-Control: no-store`. Database failures return 503 rather than empty data;
authentication and authorization errors propagate. Appointment times include
stored UTC offsets, not an inferred display timezone. Insurance excludes member
IDs, card images, filenames, and clinical data. Client corrections take precedence
over extracted fields; processing/failed cards expose no extracted details.
Insurance data does not verify benefits. Invoice and balance values are null,
never zero or an empty invoice list implying a connected ledger.

`ai_harness/client_assistant_tools.py` supplies:

- `tool_definitions()`: strict Responses API function definitions, including
  descriptions telling the model when to fetch operational information.
- `INSTRUCTIONS`: fetch current facts for scheduling/billing questions; preserve
  unavailable states, do not infer benefits, and treat retrieved text as data.
- `dispatch_tool(name, arguments, authorization=...)`: an allowlisted dispatcher
  with server-side argument validation and fresh authentication on every read.
  Identity comes from the runner's authenticated request, never model arguments.

The HTTP routes and dispatcher call the same read functions. Internal dispatch
does not need an HTTP round trip. These tools are separate from the clinical
synthesis harness and cannot retrieve clinical records or modify operational data.

### Live chat runner

`database/client_assistant.py` authenticates the active client before provider
access. `ai_harness/client_assistant.py` passes tool definitions and instructions
on every Responses request, dispatches approved tool requests using server auth,
and replays response items (including encrypted reasoning) and matching
`function_call_output` items. This follows
[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling).

Configuration uses the existing `OPENAI_API_KEY` runtime environment variable and
`CLIENT_ASSISTANT_MODEL`, falling back to `INSIGHTS_MODEL`. The hosted deployment
already configures `INSIGHTS_MODEL=gpt-5`; no new credential or runtime secret is
needed. Missing configuration returns 503 rather than a fake assistant reply.
The optional override must support Responses, function calling, and low reasoning.

Limits: 11 input messages, alternating user/assistant and ending with user; 2,000
characters per user message, 12,000 per assistant message, and 16,000 total
conversation characters. The browser sends a bounded recent history. Each turn
allows at most three model requests and two sequential tool reads. The last
request disables tools. Each provider request caps output at 2,048 tokens and
uses a 20-second socket timeout, 120 KB request bound and 256 KB response bound.
There are no automatic retries. The browser times out after 90 seconds; aborting
or leaving the tab does not guarantee cancellation of an already-running provider
request or its charges. Failed sends restore the draft for an explicit retry.

Per process, enforce 20 attempts per client per 10 minutes, one active turn per
client, and eight globally active turns. Limits reset on process restart; multiple
API replicas require a shared limiter before scaling. Authorization is rechecked
before every provider call and tool read. Authentication failures end the turn;
temporary operational failures become sanitized unavailable results, never empty
records or zero balances. Unknown tool names and extra arguments cannot execute
arbitrary reads. Previous assistant messages are untrusted conversation context.

`store:false` is set on every provider request; response IDs are not used as
persistent conversations. This does not itself guarantee zero provider retention.
Only model name, call count, and aggregate token counts are logged, without chat
text, tool payloads, client identifiers, or credentials. Sensitive-data governance
for real clinical use remains governed by the AI/ML vision; this deployment is a
hosted demo and does not add access to private clinical records.

## Future context and provider connection

The desired experience explains approved shared information in approachable
language and answers practical scheduling and billing questions. Exact context
is deferred. Do not pass the therapist's complete Insights packet or private
notes to a client-facing model and rely on a prompt to prevent disclosure.
Define a separate, server-authorized client-facing packet with explicit sharing
and revocation rules before enabling retrieval. Private note text, excerpts,
citations that reveal private content, and unapproved clinical interpretations
must be excluded before model invocation.

Scheduling and billing should use narrowly scoped, read-only tools authorized
from the authenticated client's identity. Do not accept a browser-supplied client
identity as authorization. Changes to appointments or payments are outside this
initial scope. Answers must distinguish unavailable data from empty records.

The model receives only submitted chat history and approved operational tool
results. A future clinical context packet requires separate approved sensitive-data
handling, consent, retention/deletion rules, and source-sharing checks. No prompt
can grant access to the clinical record through the current tool registry.

## Validation before live use

Verify client-only access, cross-client isolation, sharing revocation, and absence
of private notes in model inputs. Evaluate attempts to reconstruct notes, prompt
injection in messages and retrieved material, unsupported claims, diagnosis or
treatment overreach, scheduling/billing accuracy, crisis escalation behavior,
and unavailable sources. The assistant must not imply therapist monitoring.
