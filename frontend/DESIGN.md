# EduTeacher Workbench — Design Contract (Refined Warm)

> Brand contract for the frontend. Anchored on **claude's** design system (same Terracotta `#c96442`).
> Every component MUST follow this. Tokens live in `src/style.css`.

## Identity
Warm neutrality + scarce Terracotta. A teacher's unhurried, trustworthy AI co-planner — not a cold command deck. The primary surface is *reading* (AI output, outlines, questions), so text breathes.

## Tokens (see style.css `:root`)
- **Neutrals are WARM** (cream/sand, yellow-brown undertone). Cool blue-grays (`#e1e5eb`/`#c9d0da`) are FORBIDDEN.
- **Terracotta `#c96442` is scarce** — exactly one accent per screen (primary CTA / active state / streaming signal).
- **Depth = rings, not drop shadows.** Prefer `0 0 0 1px var(--border)` hairlines + background steps; soft shadows (opacity ≤0.07) only for modals/popovers. Shadows tinted warm-brown `rgba(58,47,30,*)`.
- Type: body 14.5px / 1.6 line-height / 65ch max. Headings weight **500, never 700**. Serif (`--font-serif`) for view titles only.
- Radii: min 8px interactive, 12px containers, pill badges. Motion: enter 200ms ease-out, exit 140ms ease-out; animate only transform/opacity.

## Primitive classes (global, in style.css — USE THESE, don't redefine)
- `.btn .btn-primary` — accent bg, weight 500 (not 650), height 36, radius 8. Hover translateY(-1px); active scale(0.98).
- `.btn .btn-ghost` — transparent + 1px border. Default non-CTA.
- `.btn-icon` — 32×32 transparent, SVG stroke 1.75 currentColor.
- `.card` — bg `--bg-elevated` (#fffefb, never pure white), 1px `--border`, radius 8, shadow-xs hairline.
- `.badge` — pill, 11px/500, leading 6px dot. Semantic pairs (text/bg).
- `.skeleton` — shimmer block (layout-shaped), 1.5s linear sweep.
- `.empty-state` — radial accent tint + serif headline + body line + primary action.
- `.typing-dots` — 3× 6px accent dots, 160ms stagger pulse (pre-first-token).
- `.stream-cursor` — 7px×1.1em terracotta bar, `blink-stream 1.1s steps(2)` (during streaming).

## Component patterns
- **Chat — assistant**: NO bubble. Full-width document text (max 720px), bg transparent, 1.6 line-height. Markdown weight 500 headings, blockquote border-left 3px accent, code bg subtle.
- **Chat — user**: right-aligned warm-sand bubble `--bg-warm-sand` #e8e6dc (NOT gray), radius 12 with **square bottom-right corner** (4px) = "sent". Max min(80%,520px).
- **Slot tile**: vertical card, **3px left border color-coded** (accent=generating, blue=review, green=complete, red=error, transparent=pending). Header: slot-id mono 11px + badge. Progress rail (3px) when generating. SVG marks, NOT emoji.
- **Status badge**: dot + label, semantic pairs.
- **Home entry card**: left-aligned (not centered — that's an AI tell), 56px icon chip (accent-tint bg, 28px SVG), title, desc, bottom-aligned "开始 →". Hover lift -2px.

## State coverage (mandatory)
Every interactive element: hover / active(scale .98) / focus-visible(3px ring) / disabled(.5) / loading.
Every data container: empty / skeleton / error / success — never a bare "loading..." string.

## Backend wiring realities (respect these)
- Chat = NOT streamed server-side → simulate typewriter client-side over the full returned string.
- `slot_update` SSE is never emitted → simulate slot progress from a timer once `generating`.
- SSE failure event is `generation_error` (handle it; `error` is never emitted).
- `retry` = no backend endpoint → documented no-op / "coming soon".
- `view` → fetch artifact type `final` only (review/solution unsupported).
- outline endpoint returns plain text → consume `.text()`, not `.json()`.
- `createSession` has no `/api` handler (only v2) — pre-existing backend gap; flagged separately.
- `POST /generate` requires `state === 'approved'` else 400.

## AI-slop kills (do NOT ship)
Emoji-as-icon (⏳📝🎯🔄✅❌) → inline SVG. Purple/blue gradients. Glassmorphism. "Elevate/Seamless/Unleash" copy. Three-equal-card feature rows. Fake 99% stats.
