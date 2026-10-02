# Design language

**Status:** Living reference — update this document when the visual system is deliberately refined.

## Character

The therapist workspace is calm, private, and legible: warm paper and charcoal neutrals form the working environment, while muted evergreen is a deliberate signal for selection, focus, and affirmative actions. Components should feel orderly and comfortably separated, never stark or decorative. The visual hierarchy must remain clear in both bright offices and lower-light clinical environments.

## Color schemes

Use semantic roles rather than treating a raw Tailwind stone shade as the design system. The current class mappings in `frontend/src/app/globals.css` implement these roles while the interface is being migrated.

| Role | Light mode | Dark mode | Use |
| --- | --- | --- | --- |
| Canvas | `#eeedea` | `#151412` | Page background; distinct from cards |
| Raised surface | `#f6f6f4` | `#211f1d` | Broad workspace sections, cards, panels, and dialogs |
| Subtle surface | `#fbfbfa` | `#292724` | Secondary sections and quiet controls |
| Inset surface | `#e8e7e3` | `#34312d` | Selected-neutral rows and expanded content |
| Standard divider | `#c9c4bc` | `#625d57` | Component borders and separators |
| Strong divider | `#a9a299` | `#827b73` | Hover, selected-neutral, and high-definition boundaries |
| Primary text | `#292524` | `#f5f2ed` | Headings and primary content |
| Muted text | `#6b665f` | `#c0bab3` | Supporting copy; keep readable against its surface |
| Evergreen surface | `#eaf2eb` | `#22372a` | Selected state and quiet positive context |
| Evergreen action | `#465c4b` | `#4e6b54` | Primary action, focus, and selected borders; supports white button text |

Light mode uses a light-gray broad-section layer rather than stark white; it must remain visibly separate from the canvas through both tone and border. Reserve the lightest subtle surface for nested or quiet controls. Dark mode must preserve three discernible levels—canvas, raised surface, and inset surface—and must not turn secondary copy or evergreen labels into near-black text.

## Boundaries, elevation, and shape

- Use a `1px` divider for independent cards, fieldsets, selected rows, and structural separators. Do not rely solely on `shadow-sm` to define a component in light mode.
- Use soft shadows only as secondary depth cues on raised cards and dialogs; borders carry the primary separation.
- Prefer `rounded-xl` for contained controls and content groups; use `rounded-2xl` for primary panels and workspace sections. Keep the radius family consistent within a component.
- Reserve the strongest divider or an evergreen border/ring for focus and selected states. Do not introduce heavy outlines merely to compensate for a missing surface distinction.

## Motion and blur

- Motion is short, quiet, and purposeful. The established carousel uses `360ms cubic-bezier(0.22, 1, 0.36, 1)` for spatial movement; use a roughly `150–220ms ease-out` transition for hover, border, surface, and shadow changes.
- Respect `prefers-reduced-motion`; do not make motion essential to discovering state or completing work.
- Use backdrop blur only to soften a deliberate transition between visible and concealed content, such as collapsed previews and carousel edges. Pair it with a gradient mask, keep it subtle (`3–5px`), and never blur information that must be read or acted upon.
- Avoid decorative entrance animations, continuous motion, and glass effects. The product should feel composed rather than attention-seeking.

## Interface copy

- Use one meaningful heading per panel. Omit redundant context labels such as “Scheduled session” above a preparation heading, and avoid stacked headings that describe the same content.
- The pre-session brief uses the full available panel width, with no status/version badge or manual refresh control.
- Default to headings and controls without explanatory subtext above or below them. Avoid routine subtitles, eyebrow labels, and instructions that repeat an obvious action. Add supporting copy only when requested or needed for a meaningful error, empty state, consent, or otherwise unclear decision.
- Search fields use a concise placeholder and an accessible name; do not add a redundant visible label or helper sentence.
- Client permissions show one left-aligned list of editable choices using native checkbox inputs with switch semantics. Fixed Schedule, Documents, Chat, and completed/future session-card access is not repeated in the form.
- Relationship identification groups detected speakers by completed session. Show each provider speaker label verbatim, alongside a name field with known relationship names as suggestions and a brief audio sample. A saved name applies to the same provider label throughout that client relationship.

## Reusable content panels

Use `CollapsibleContentPanel` for a compact text teaser that expands into richer
content. Clinical notes and transcripts share this exact shell: title,
optional summary, a 96px faded preview, and a disclosure button. Pass text as
`preview` and expanded content as children; use `expanded` and
`onExpandedChange` when a parent needs to open it, such as transcript playback.
The entire collapsed card is one disclosure button, with a visible SVG down-chevron
  overlay above its faded preview. Once expanded, only the header toggles the
  panel so controls and text inside remain usable.
Transcripts and clinical notes supply `previewContent` using the same content
rendering as their expanded view, clipped to the preview height and inert while collapsed. Playback labels
and dialogue share the same first-line baseline, including wrapped segments.

Scheduled-session preparation uses that same `CollapsibleContentPanel` shell for
the pre-session brief, with its actual brief rendering serving as the collapsed
teaser. The brief and capture controls share one raised card. Below the brief, a
neutral split control presents the dominant `Record Session` action with a small
red recording dot and an appended icon-only upload action; both halves use the
same surface, border, and interaction treatment. Both actions stay disabled while
work is active. During browser upload, the entire split control becomes a
determinate loading surface: a slightly darker neutral fill advances across its
full height and explicitly asks the user to remain on the page. Once the server
accepts the recording, remove the preparation card and mark the corresponding
carousel card `Complete`. That card owns the remaining state: a small spinner in
its upper-right corner and a compact `Hang tight` message with a progressively
animated ellipsis until both transcript and draft clinical note are durable. It
must state accessibly that the upload is secure and the page may be left;
reduced-motion mode shows a static ellipsis. Completed-session review begins directly with Associated materials at
the standard 24px workspace-section gap, without a redundant completed-session
heading or uploaded-session label.

The session carousel uses symmetrical 2px blur over the outer 12% on each side,
keeping adjacent session labels sharp. Its schedule action is a calendar/edit
icon with an accessible label and hover description.

Document grids begin with a slightly compact upload tile, when authorized,
matching the document preview ratio and footer height. Download controls appear
on card hover or keyboard focus and use theme-aware gray surfaces and icons so
PDF previews cannot obscure the action.

The therapist calendar uses a Monday–Sunday week as its primary surface. Its
month view is a vertically scrollable stack that centers the current week on
entry. View and date controls remain attached to the calendar, while a subtle
masked blur softens content passing beneath the sticky weekday row. Month cells
use a near-square shape with the date tucked into the upper-left corner, and
prioritize active appointment counts and short time/client cues. The month
surface keeps a bounded live render window, indexes appointments by day, and
throttles scroll-derived state to preserve responsive navigation. Selecting a
day expands the calendar section and opens its complete agenda flush beside the
grid without narrowing the calendar on wide screens. Opening and dismissing the
agenda use the same quiet width-and-panel transition so the calendar geometry
does not jump. The calendar remains scrollable while its internal scrollbar
stays visually hidden. The agenda is closed initially;
selecting the same day again or clicking outside the agenda and day cells
dismisses it. Each detailed appointment shows
time, client, and appointment type; cancelled appointments remain visible with
subdued styling. Client scheduling settings use the same
appointment records and group recurring preferences, one-time or make-up
creation, and upcoming-session actions into distinct sections. Suggested
recurring times must account for the therapist's other active appointments. A
client-specific Monday–Friday week calendar supports direct rescheduling: the
current client's sessions use interactive evergreen cards, anonymous conflicts
from the therapist's other appointments use non-interactive neutral Unavailable blocks
with a blocked icon and `cursor-not-allowed`,
and open time remains a light neutral surface. Dragging preserves session length,
snaps to 30-minute slots, and remains backed by the manual reschedule controls.
A drop stages rather than commits the change: a confirmation
dialog names the proposed date and time and clarifies that a moved recurring
session returns to its normal time the following week.
Recurring scheduling configuration starts collapsed behind a single disclosure
row. Its suggested options state the full date and start/end block derived from
the selected session length; scheduling the series also persists those settings.
One-time and make-up creation belongs directly in available week-calendar slots,
not in a duplicate form below the calendar.
Recurring configuration is relationship-aware: saved preferences and the next
recurring time prefill for an established schedule, while a new relationship
starts with unselected frequency, length, format, and time fields.
The therapist client list uses one inline search surface for both filtering
connected clients and finding discoverable client accounts. Search results stay
inside the list rather than opening a separate add-client dialog, and use the
person's profile photo or initials alongside their account identity to reduce
selection mistakes. A newly linked relationship opens with only the basic name
card and a softly blurred, non-interactive preview of the session carousel;
card boundaries, spacing, and the carousel's general structure remain visible.
Its outer border and surface match the quiet treatment of the relationship name
card above it.
Center a single `Configure sessions` action over that preview; it opens Client
care settings directly to Scheduling with recurring appointment configuration
expanded, so the relationship can be scheduled before the normal workspace is
revealed.

## Interaction details

- Pre-session briefs use a short opening paragraph, visible follow-up bullets,
  and a separate supporting-context list. Keep source links small and adjacent
  to the statement rather than underlining whole paragraphs. In the pre-session
  brief, emphasize the model-selected short claim phrases, leaving surrounding prose
  normal-weight. Each phrase opens only its own attributed exchanges. Never infer
  highlights by matching words to quotations. Legacy items without granular
  claims use a small sentence-level Evidence link. These open a supporting-context dialog
  with quotes and transcript links. Show preparation only for the immediate
  upcoming scheduled session; later sessions remain empty.
- Transcript segments share one compact playback row: a fixed timestamp column on
  the left groups the play/pause icon, timestamp, and speaker name with even
  spacing, followed by dialogue. Flagged passage text is bold and selectable;
  avoid separate cards, badges, or underlines for those rows. Selecting bold text
  opens clinician guidance inline without changing playback. Clicking anywhere
  else in the row plays or pauses that segment. Hover uses a faint full-row inset
  surface, while active playback uses a slightly stronger neutral surface. Give
  each row rounded-xl corners and a small vertical gap so adjacent state surfaces
  remain visually separate; do not box the timestamp/name group. Make
  timestamps semibold. Place the play/pause icon before
  the timestamp and reveal it only on segment hover, keyboard focus, or active
  playback position; reserve its space to prevent layout shifts. Use equally sized
  SVG play and pause icons. Keep the viewport still while the active segment is
  visible; only scroll an offscreen segment into view using nearest alignment. Keep row spacing tight for long transcripts. Saved quotes and longer journey lists start
  collapsed in Insights.

- The therapist Insights page begins with its generated longitudinal overview,
  without a decorative accent bar. Four compact orientation metrics follow:
  evidence-linked sessions, themes in view, open threads, and items awaiting
  review. Follow them with a compact theme-recurrence view that compares each
  current theme by distinct cited sessions and cited record moments. Its bars
  show relative evidence coverage for navigation, not severity or clinical
  importance. These are record-navigation counts rather than clinical scores. A
  longitudinal overview follows, then evidence-linked sections for trajectory,
  recurring themes, open threads, and client context. The evidence and review
  queue remains a separate deeper section below the overview.
  Write each saved insight as cohesive natural-language prose with two semantic
  layers: first an unlinked analysis statement explaining what may matter, then
  contextual statements explaining where that interpretation appeared in the
  record. Keep them in one paragraph when concise and use an ordinary paragraph
  break only when length requires it; do not render the context as a list,
  nested panel, callout, or separately bordered block. Contextual prose should
  use sentence structures chosen for the specific evidence rather than repeated
  lead-ins such as “This appeared when.” Evidence belongs only in
  the contextual layer:
  one or more model-provided claim anchors bold and link each supported phrase to its exact
  transcript slices. Linked claims use bold text without colored underlines and
  remain true inline prose links, wrapping word-by-word like the surrounding text
  rather than moving the entire claim to a new line as an atomic control. Render
  the first letter in sentence case for its displayed position—capitalized at a
  sentence start and lowercase mid-sentence—without changing the stored anchor
  used to resolve evidence.
  Do not infer anchors from similar wording or quotations.
  Older items without valid claim anchors keep their analysis intact and place
  one quiet statement-level source link in a separate contextual block.

- Session review uses the same `SessionCardCarousel`, `CompletedSessionLayout`,
  `TranscriptViewer`, and `ClinicalNote` in both roles. The viewer owns playback
  when no controller is supplied and accepts explicit transcript/note visibility
  flags. Supply authorized data and recording URLs; never fork the visuals to
  enforce permissions. The server remains the authority for material access.

- Therapist and client workspaces share `CareRelationshipHeader`: the other
  person's avatar, name, available contact details, and relationship-specific
  navigation. Omit unavailable contact fields and use initials when no photo is
  supplied. Keep the same surfaces and selected state across roles; vary the
  actions, not the component. Unimplemented actions are disabled and marked Soon.

- Directly manipulable controls use `cursor-grab` with `active:cursor-grabbing`, unless the control is disabled, waiting, or accepts text input.
- Search fields do not show an outer focus outline, ring, glow, or focus shadow when clicked or focused. Keep the existing field boundary and caret; use a restrained change to the existing border for focus visibility, rather than an additional surrounding highlight. In Tailwind, use `focus:outline-none focus-visible:border-stone-500` without ring or outline utilities. Text inputs can match `:focus-visible` even when clicked, so that selector alone does not suppress a click outline.
- For other controls, provide a visible evergreen focus outline with an offset where space permits. Hover should add a small surface or border change, not a dramatic color shift.
- Disabled controls retain their intent but lower contrast only enough to indicate their unavailable state; never make labels unreadable.

## Refinement checklist

When changing a component, inspect it in both themes and verify: its boundaries remain visible, muted text is comfortably readable, selected/hover/focus states are distinct, and any motion or blur supports comprehension rather than decoration.
