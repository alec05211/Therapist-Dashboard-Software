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

- Default to headings and controls without explanatory subtext above or below them. Avoid routine subtitles, eyebrow labels, and instructions that repeat an obvious action. Add supporting copy only when requested or needed for a meaningful error, empty state, consent, or otherwise unclear decision.
- Search fields use a concise placeholder and an accessible name; do not add a redundant visible label or helper sentence.

## Interaction details

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
