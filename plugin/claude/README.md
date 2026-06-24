# `claude/` — Claude-family overlay

Files here are merged on top of `../shared/` for **every** Claude target (claude-code, claude-desktop,
claude-web, claude-cowork) but not for any non-Claude consumer. Use it for skills, hooks, or assets
that should ship to all Claude surfaces yet stay out of the generic shared core.

Layout mirrors a plugin root, e.g. `skills/<name>/SKILL.md`, `hooks/hooks.json`. Empty today — the
shared core already covers everything; this is the seam for Claude-only additions.
