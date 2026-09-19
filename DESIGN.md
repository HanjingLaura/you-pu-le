# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-09-18
- Primary product surfaces: single-page transcribe tool
- Evidence reviewed: 职到了 paper workspace; piano-video-to-score brief

## Brand
- Name: 有谱了
- Personality: quiet practice-room tool, same family as 职到了, not an O了 clone
- Trust signals: honest draft-score disclaimer, file formats, duration limit
- Avoid: AI-purple glow, graph-paper marketing hero, floating upload square, Inter, em-dashes

## Product goals
- Goals: upload a solo piano video or audio file, get MIDI + MusicXML, see a grand staff in the browser
- Non-goals: pop-song accompaniment, PDF export, account system, multi-instrument scores
- Success signals: a 1-3 minute piano clip becomes a readable draft score with downloadable MIDI/MusicXML

## Personas and jobs
- Primary personas: pianists, teachers, students who recorded themselves
- User jobs: 扒谱 — turn a recording into something they can edit in MuseScore
- Key contexts of use: desktop browser after practice

## Information architecture
- Primary navigation: product name in the work panel
- Core routes/screens: `/` work panel and result paper
- Content hierarchy: work surface first, helper copy second

## Design principles
- Principle 1: the score paper is the product
- Principle 2: tell the user this is a draft before they download
- Tradeoffs: beauty of the paper > marketing chrome

## Visual language
- Color: white `#ffffff`, ink `#151515`, muted `#86868b`. No accent color.
- Typography: system UI / PingFang / YaHei
- Spacing/layout rhythm: left work panel, 32px page padding, 职到了-like heading stack
- Shape/radius/elevation: 12px drop well, 14px action button
- Motion: border darken on drag only
- Imagery/iconography: faint staff lines in the drop well; Phosphor downloads on the result bar

## Components
- Existing components to reuse: none
- New/changed components: DropWell, JobProgress, ScoreViewer, ResultBar
- Variants and states: idle, dragging, uploading, extracting, transcribing, scoring, done, error
- Token/component ownership: CSS variables in `app/globals.css`

## Accessibility
- Target standard: WCAG AA
- Keyboard/focus behavior: drop well is a labeled button, downloads are real links
- Contrast/readability: white paper, ink `#151515`, muted `#86868b`
- Screen-reader semantics: status region for job progress
- Reduced motion and sensory considerations: disable enter animations

## Responsive behavior
- Supported breakpoints/devices: mobile first, desktop comfortably around 640px work column
- Layout adaptations: stack heading and sample on small screens
- Touch/hover differences: full-width drop well on touch

## Interaction states
- Loading: staged labels, not a generic spinner as the only cue
- Empty: drop well with accepted formats
- Error: inline message, keep the file chooser
- Success: paper with score plus MIDI/MusicXML downloads
- Disabled: ignore extra drops while a job is running
- Offline/slow network, if applicable: poll until done or error

## Content voice
- Tone: direct, Chinese UI, no hype
- Terminology: 有谱了, 扒一下, 草稿谱, 大谱表, MIDI, MusicXML
- Microcopy rules: no em-dashes; say limits in numbers

## Implementation constraints
- Framework/styling system: Next.js App Router + Tailwind v4
- Design-token constraints: CSS variables, no accent
- Performance constraints: OSMD is client-only; model runs in Python
- Compatibility constraints: desktop Chrome first
- Test/screenshot expectations: work panel, progress, score paper, error state

## Open questions
- [ ] Whether v2 adds MuseScore PDF export
- [ ] Whether teachers need batch upload
