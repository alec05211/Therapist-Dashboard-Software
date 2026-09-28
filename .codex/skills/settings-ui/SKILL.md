---
name: settings-ui
description: Create or refine settings and permissions interfaces in Therapist Dashboard Software, including toggle behavior, fixed access, dependency rules, and server-enforced client sharing.
---

# Settings UI

Read `docs/PROJECT_VISION.md` and `docs/DESIGN_LANGUAGE.md` before changing settings.

## Interaction model

- Use native checkbox inputs with `role="switch"` for independent boolean preferences so checked state, keyboard behavior, and change events remain browser-managed. Give each switch an accessible label, keyboard focus treatment, and a visible on/off state in both themes.
- Group related settings inside a bordered `rounded-xl` surface with dividers. Keep the label and concise consequence together; avoid helper copy that merely repeats the label.
- Show only editable permissions. Do not spend settings-page space on fixed product access.
- Use `cursor-grab` and `active:cursor-grabbing` for enabled controls. Use `cursor-not-allowed` for disabled or waiting states.
- When one setting depends on another, disable the dependent toggle and clear its value when the prerequisite is turned off.

## Client-care permissions

- Schedule, Documents, and Chat are always visible to the client and are omitted from the permissions UI.
- Completed-session labels, Transcript, recording playback, Clinical Note, Insights, and Prescriptions are therapist-controlled.
- Recording playback requires transcript access.
- Treat UI visibility as presentation only. Enforce every sensitive-material permission in the API, fail closed for configurable categories, and return only authorized fields.
- Keep generated clinical notes visibly labeled `Clinical Note` with `Draft — review before use` immediately beside the title.

## Validation

Check keyboard behavior, disabled dependencies, persistence after reload, API filtering, and light/dark rendering. Update permission tests and `docs/CLIENT_SHARING.md` whenever the access model changes.
