# EduTeacher Frontend

Vue 3 + Vite SPA for the EduTeacher Workbench.

## Features

- **组卷 (Compose)**: Intelligent test paper generation
- **知识点出题 (Knowledge Point)**: Generate questions based on knowledge points
- **Real-time chat interface** with streaming responses
- **Live outline editing** with markdown preview
- **Progress tracking** with slot-based kanban cards
- **Open Design style** design system

## Design System

Uses custom CSS design tokens matching the Open Design style:

- Warm terracotta accent (`#c96442`)
- Soft backgrounds (`#faf9f7`, `#fdfcfa`)
- Smooth animations (200ms enter, 140ms exit)
- Custom easing (`cubic-bezier(0.23, 1, 0.32, 1)`)

## Development

```bash
npm install
npm run dev
```

The dev server proxies `/api` requests to `http://localhost:3001`.

## Build

```bash
npm run build
```

Output goes to `../static/` for serving by the FastAPI backend.

## Project Structure

```
src/
├── api/
│   └── client.ts          # API wrapper with SSE support
├── composables/
│   ├── useSession.ts      # Session state management
│   ├── useSSE.ts          # SSE event subscription
│   └── useArtifact.ts     # Artifact fetching
├── components/
│   ├── ChatLog.vue        # Message list
│   ├── ChatMessage.vue    # Single message (user/assistant)
│   ├── Composer.vue       # Message input
│   ├── OutlineEditor.vue  # Markdown outline editor
│   ├── SlotKanban.vue     # Progress cards
│   ├── SlotCard.vue       # Single slot status
│   └── StateBadge.vue     # FSM state indicator
├── views/
│   ├── HomeView.vue       # Landing page
│   └── SessionView.vue    # Main chat session
├── style.css              # Design tokens + base styles
├── main.ts                # App entry with router
└── App.vue                # Root component
```

## API Integration

The frontend integrates with the FastAPI backend via:

- REST API endpoints for sessions, messages, outlines
- Server-Sent Events (SSE) for real-time updates
- Artifact fetching for generated content

See `src/api/client.ts` for the full API interface.
