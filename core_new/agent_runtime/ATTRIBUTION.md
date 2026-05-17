# Attribution

This package is a minimal local adapter inspired by and partially adapted from
DeepTutor's Apache-2.0 licensed runtime components:

- `deeptutor.tutorbot.agent.tools.base.Tool`
- `deeptutor.tutorbot.agent.tools.registry.ToolRegistry`
- `deeptutor.tutorbot.agent.loop.AgentLoop`
- `deeptutor.tutorbot.agent.context.ContextBuilder`
- `deeptutor.tutorbot.agent.skills.SkillsLoader`

The full upstream source and license are kept under `reference/DeepTutor/` in
this repository. This adapter intentionally excludes DeepTutor's channel,
heartbeat, web UI, default shell/web tools, and general question-generation
business logic.
