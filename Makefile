# sellerclaw-cli — developer + release commands.
#
# Quick reference:
#   make install        Sync the dev environment (uv)
#   make lint           ruff + pyright
#   make test           Unit tests
#   make lock-check     Verify uv.lock still matches pyproject.toml (writes nothing)
#   make check          lock-check + lint + test
#   make build          Build wheel + sdist into dist/
#   make plugin         Build the Claude plugin variants from plugin/ (TARGET=claude-code for one)
#   make plugin-check   Verify the committed plugins/ tree still matches plugin/ (writes nothing)
#   make mcpb           Build the Claude Desktop extension bundle (dist/sellerclaw.mcpb)
#   make web-zip        Pack the claude-web plugin for manual upload to claude.ai (dist/sellerclaw-claude-web.zip)
#   make plugin-bump    Bump plugin/VERSION + rebuild committed plugin (publish on push, no CLI release)
#   make release-check  Report whether a new release is needed
#   make release        Bump version, tag vX.Y.Z, push -> CI publishes to PyPI (runs `check` first)
#
# Plugin vs CLI versioning:
#   The Claude plugin/connector is versioned independently of the CLI via plugin/VERSION (build_plugin.py
#   stamps it into the manifests). Ship plugin/skill/manifest changes without a CLI release:
#     make plugin-bump            # bump minor (PART=patch|major or VERSION=X.Y.Z), rebuilds plugins/
#     git commit -am ... && git push   # ci.yml verifies, publish-plugin.yml cuts plugin-vX.Y.Z + bundles
#
# Release usage:
#   make release                 # bump minor from the latest v* tag (default)
#   make release PART=patch      # bump patch
#   make release PART=major      # bump major
#   make release VERSION=1.2.3   # tag an exact version
#   make release ALLOW_DIRTY=1   # skip the clean-working-tree check
#   make release FORCE=1         # tag even if shipped files are unchanged
#   make release SKIP_CHECKS=1   # skip the lint + unit-test gate (emergencies only)
# Every release path runs `make check` first — see release-preflight. REMOTE defaults to origin.

UV ?= uv
REMOTE ?= origin
PART ?= minor

# Files that actually ship in the wheel/sdist (see [tool.hatch.build] in
# pyproject.toml). Diffing these against the last v* tag decides whether a new
# release is warranted — test/CI/docs-only churn doesn't require one.
SHIPPED_PATHS = sellerclaw_cli pyproject.toml README.md

.PHONY: install lint test lock-check check build plugin plugin-check mcpb web-zip plugin-bump release-check release-preflight release release-latest release-beta

install:
	$(UV) sync --group dev

lint:
	$(UV) run ruff check .
	$(UV) run pyright

test:
	$(UV) run pytest -m unit

# Does the committed uv.lock still describe pyproject.toml? CI and release.yml install with
# `uv sync --locked`, so a dependency edit pushed without its lock update fails there — this catches
# it before the push. `uv lock --check` only reports; run `uv lock` (or any `make test`, which
# re-locks on the way in) to refresh, then commit uv.lock alongside the pyproject change.
lock-check:
	$(UV) lock --check

check: lock-check lint test

build:
	$(UV) build

# Assemble the Claude plugin variants from plugin/ (shared core + claude overlay + per-target
# manifests). claude-code lands in the committed plugins/ tree (the marketplace references it);
# the rest are artifacts under dist/. Build just one with `make plugin TARGET=claude-code`.
plugin:
	$(UV) run python scripts/build_plugin.py $(if $(TARGET),--target $(TARGET),)

# Is the committed plugins/ tree still what plugin/ produces? Nothing rebuilds it automatically, so
# an edit to plugin/ that was never followed by `make plugin` ships stale skills to every marketplace
# install — silently, with a green test suite. Rebuilds into a temp dir and diffs; writes nothing.
plugin-check:
	$(UV) run python scripts/build_plugin.py --check

# Build the Claude Desktop Extension bundle (.mcpb). Assembles the desktop target from plugin/
# (stamps the version into manifest.json), then packs it -> dist/sellerclaw.mcpb. The bundle launches
# the *published* sellerclaw-cli[mcp] via uvx, so rebuild and re-upload it after a release that
# changes the desktop manifest.
mcpb:
	$(UV) run python scripts/build_plugin.py --target claude-desktop
	npx -y @anthropic-ai/mcpb pack dist/plugins/claude-desktop dist/sellerclaw.mcpb

# Pack the claude-web plugin (skills + hooks + remote MCP declaration) into a single .zip whose
# files live under a `sellerclaw/` folder, for users who upload by hand at claude.ai
# (Customize -> Personal plugins -> Upload plugin) instead of adding the marketplace.
web-zip:
	$(UV) run python scripts/build_plugin.py --target claude-web --zip dist/sellerclaw-claude-web.zip

# Bump the independent plugin version (plugin/VERSION) and rebuild the committed marketplace plugin.
# Commit the result and push to main: ci.yml verifies the tree and publish-plugin.yml builds the
# Desktop .mcpb + claude-web .zip and cuts a plugin-vX.Y.Z release — no CLI release, no PyPI publish.
# PART=major|minor|patch (default minor), or pass VERSION=X.Y.Z for an exact version.
plugin-bump:
	@set -eu; \
	cur=$$(tr -d '[:space:]' < plugin/VERSION 2>/dev/null || echo 0.0.0); \
	if [ -n "$${VERSION:-}" ]; then \
	  new="$$VERSION"; \
	else \
	  major=$$(echo "$$cur" | cut -d. -f1); \
	  minor=$$(echo "$$cur" | cut -d. -f2); \
	  patch=$$(echo "$$cur" | cut -d. -f3); \
	  case "$(PART)" in \
	    major) new="$$((major+1)).0.0" ;; \
	    minor) new="$$major.$$((minor+1)).0" ;; \
	    patch) new="$$major.$$minor.$$((patch+1))" ;; \
	    *) echo "Unknown PART=$(PART) (use major|minor|patch)" >&2; exit 1 ;; \
	  esac; \
	fi; \
	printf '%s\n' "$$new" > plugin/VERSION; \
	$(UV) run python scripts/build_plugin.py --target claude-code; \
	echo "plugin/VERSION: $$cur -> $$new — committed plugins/ rebuilt. Commit & push to publish."

# Reports whether the shipped CLI differs from the last published release (the
# latest v* git tag). release.yml publishes to PyPI on v*.*.* tags.
release-check:
	@set -eu; \
	git fetch --tags --quiet $(REMOTE) 2>/dev/null || true; \
	last=$$(git tag --list 'v*' --sort=-v:refname | head -n1); \
	if [ -z "$$last" ]; then \
	  echo "sellerclaw-cli: no v* tag found — never released, first release needed (run: make release)."; \
	  exit 0; \
	fi; \
	ver=$${last#v}; \
	if git diff --quiet "$$last" -- $(SHIPPED_PATHS); then \
	  echo "sellerclaw-cli: up to date with last release $$last — no new release needed."; \
	else \
	  echo "sellerclaw-cli: local code differs from last release $$last — new release needed (run: make release)."; \
	  echo; \
	  git diff --stat "$$last" -- $(SHIPPED_PATHS); \
	fi

# Everything CI can fail a release on, run BEFORE the tag exists (~25s):
#   * lock-check  — uv.lock still matches pyproject.toml. Runs FIRST and is NOT skippable: release.yml
#     installs with `uv sync --locked`, so a stale lock rejects the tag build no matter how urgent the
#     release is — skipping it only turns a 1-second failure into a burnt tag (see v0.43.0b6). Order
#     matters inside `check` too: `uv run` re-locks on the way into the tests, so a stale lock would be
#     silently rewritten mid-release and resurface as a confusing "working tree is dirty" below.
#   * check       — ruff + pyright + unit tests, the same gate release.yml puts in front of PyPI.
#   * plugin-check — the committed plugins/ tree still matches plugin/. Not a test, and no test
#     covers it: `release` pushes the branch first, and a push to main both republishes the
#     marketplace plugin from that tree AND reddens ci.yml's drift job. Catching it here turns
#     "released, CI red, users on stale skills" into "run `make plugin` and commit".
# It is a *prerequisite* of `release`, so it runs before anything is tagged or pushed and a failure
# leaves no tag behind. (Prerequisite, not an in-recipe `$(MAKE)` call: make executes recipe lines
# that mention $(MAKE) even under `-n`, which would turn a dry-run `make -n release` into a real one.)
# Escape hatch: SKIP_CHECKS=1 (emergencies only — you are shipping unverified code, lock excepted).
release-preflight:
	@set -e; \
	echo "release-preflight: uv.lock must match pyproject.toml (not skippable)..."; \
	$(MAKE) --no-print-directory lock-check; \
	if [ -n "$${SKIP_CHECKS:-}" ]; then \
	  echo "release-preflight: SKIP_CHECKS=1 — skipping lint, unit tests and the plugin drift check. Shipping unverified."; \
	else \
	  echo "release-preflight: lint + unit tests + plugin drift check must pass before tagging..."; \
	  $(MAKE) --no-print-directory check plugin-check; \
	  echo "release-preflight: OK."; \
	fi

# Bump the version, create an annotated tag vX.Y.Z, push the branch and the tag.
# Pushing a v*.*.* tag triggers .github/workflows/release.yml, which verifies,
# builds, and publishes to PyPI. Refuses to tag when the shipped CLI is unchanged
# since the last v* tag (nothing to publish) — override with FORCE=1.
#
# Channel is decided by the version shape (see release.yml github-release job): a clean vX.Y.Z is a
# stable "Latest" release; a PEP 440 pre-release (bN / rcN / aN, no dot) is a GitHub "Pre-release"
# and a PyPI pre-release. PREFER the `release-latest` / `release-beta` wrappers below — they compute
# the number for you so the format can't be wrong. `release` is the low-level target they delegate to;
# call it directly only for an explicit one-off (make release VERSION=0.41.0rc1).
release: release-preflight
	@set -eu; \
	if [ -z "$${ALLOW_DIRTY:-}" ] && [ -n "$$(git status --porcelain)" ]; then \
	  echo "Working tree is dirty. Commit your changes or rerun with ALLOW_DIRTY=1." >&2; \
	  exit 1; \
	fi; \
	git fetch --tags --quiet $(REMOTE); \
	last=$$(git tag --list 'v*' --sort=-v:refname | head -n1); \
	if [ -z "$${FORCE:-}" ] && [ -n "$$last" ] && git diff --quiet "$$last" -- $(SHIPPED_PATHS); then \
	  echo "sellerclaw-cli: no changes since $$last — nothing to release." >&2; \
	  echo "Run 'make release-check' to inspect, or 'make release FORCE=1' to tag anyway." >&2; \
	  exit 1; \
	fi; \
	if [ -n "$${VERSION:-}" ]; then \
	  new="$$VERSION"; \
	else \
	  if [ -z "$$last" ]; then last="v0.0.0"; fi; \
	  base=$${last#v}; \
	  major=$$(echo "$$base" | cut -d. -f1); \
	  minor=$$(echo "$$base" | cut -d. -f2); \
	  patch=$$(echo "$$base" | cut -d. -f3); \
	  case "$(PART)" in \
	    major) new="$$((major+1)).0.0" ;; \
	    minor) new="$$major.$$((minor+1)).0" ;; \
	    patch) new="$$major.$$minor.$$((patch+1))" ;; \
	    *) echo "Unknown PART=$(PART) (use major|minor|patch)" >&2; exit 1 ;; \
	  esac; \
	fi; \
	tag="v$$new"; \
	if git rev-parse -q --verify "refs/tags/$$tag" >/dev/null; then \
	  echo "Tag $$tag already exists locally." >&2; exit 1; \
	fi; \
	if git ls-remote --exit-code --tags $(REMOTE) "refs/tags/$$tag" >/dev/null 2>&1; then \
	  echo "Tag $$tag already exists on $(REMOTE)." >&2; exit 1; \
	fi; \
	echo "Pushing branch and creating annotated tag $$tag on $(REMOTE)..."; \
	git push $(REMOTE) HEAD; \
	git tag -a "$$tag" -m "Release $$tag"; \
	git push $(REMOTE) "$$tag"; \
	echo "Pushed $$tag — release.yml will verify, build, and publish $$tag to PyPI."; \
	echo "To pin this build inside sellerclaw-agent, set runtime/edge-requirements.txt: sellerclaw-cli==$$new"

# Preferred entry points — you never type a version string, so you can't get the PEP 440
# format wrong. The number is computed from existing tags:
#   make release-beta     # from dev  -> X.Y.ZbN  (pre-release): "Pre-release" on GitHub, PyPI pre-release
#   make release-latest   # from main -> X.Y.Z    (stable):      "Latest" on GitHub, normal PyPI install
#
# Both share one "base" = the last STABLE tag bumped by PART (minor by default; PART=patch|major).
# release-beta cuts release candidates for that base (b1, b2, …); release-latest finalizes it to the
# clean X.Y.Z. Typical flow: `make release-beta` on dev (repeat as needed) → `make release-latest` on main.
# `b` is the PEP 440 beta spelling, so PyPI treats the build as a pre-release and a plain
# `pip install sellerclaw-cli` won't pick it up. Delegates to `release`, which does all the tag pushing.
release-latest release-beta:
	@set -eu; \
	git fetch --tags --quiet $(REMOTE); \
	last_stable=$$(git tag --list 'v*' --sort=v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$$' | tail -n1); \
	if [ -z "$$last_stable" ]; then last_stable="v0.0.0"; fi; \
	b=$${last_stable#v}; \
	major=$$(echo "$$b" | cut -d. -f1); \
	minor=$$(echo "$$b" | cut -d. -f2); \
	patch=$$(echo "$$b" | cut -d. -f3); \
	case "$(PART)" in \
	  major) base="$$((major+1)).0.0" ;; \
	  minor) base="$$major.$$((minor+1)).0" ;; \
	  patch) base="$$major.$$minor.$$((patch+1))" ;; \
	  *) echo "Unknown PART=$(PART) (use major|minor|patch)" >&2; exit 1 ;; \
	esac; \
	if [ "$@" = "release-beta" ]; then \
	  n=$$(git tag --list "v$${base}b*" | sed -E 's/.*b([0-9]+)$$/\1/' | grep -E '^[0-9]+$$' | sort -n | tail -n1); \
	  if [ -z "$$n" ]; then n=0; fi; \
	  new="$${base}b$$((n+1))"; \
	  echo "release-beta: base $$base (from last stable $$last_stable) -> pre-release $$new"; \
	  $(MAKE) --no-print-directory release VERSION="$$new"; \
	else \
	  if git tag --list "v$${base}b*" | grep -q .; then force="FORCE=1"; else force=""; fi; \
	  echo "release-latest: finalizing base $$base (from last stable $$last_stable) -> stable $$base"; \
	  $(MAKE) --no-print-directory release VERSION="$$base" $$force; \
	fi
