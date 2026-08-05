#!/bin/sh
# SessionStart primer for the SellerClaw plugin.
# A short, one-time orientation. It does NOT tell the agent to inspect every command — the bundled
# skills carry ready-to-run sellerclaw_run examples, so the agent runs directly and only inspects
# schemas as a fallback. Best-effort: prints context to stdout and always exits 0; a failure must
# never break the session.
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"SellerClaw is connected via the sellerclaw_groups / sellerclaw_describe / sellerclaw_run / sellerclaw_guide tools. Use the SellerClaw skills -- they carry ready-to-run sellerclaw_run examples, so run commands directly rather than inspecting every one; sellerclaw_guide serves the same recipes if a skill is not loaded. Reach for sellerclaw_describe only for a command no skill covers, or when a call returns a field error (the error names the fix). Channel commands need a store id in positionals -- get it from sellerclaw_run(group='channels', command='list'). Some writes (email, ad/Klaviyo campaigns) need the owner's approval, which is expected. If a call returns an auth error, sign in the way this client connects: in Claude Code run `sellerclaw auth login` in a terminal; in the Claude Desktop extension call the sellerclaw_login tool; on claude.ai or Cowork reconnect the SellerClaw connector in settings."}}
JSON
