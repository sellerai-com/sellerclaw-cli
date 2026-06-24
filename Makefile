# sellerclaw-cli — developer + release commands.
#
# Quick reference:
#   make install        Sync the dev environment (uv)
#   make lint           ruff + pyright
#   make test           Unit tests
#   make check          lint + test
#   make build          Build wheel + sdist into dist/
#   make plugin         Build the Claude plugin variants from plugin/ (TARGET=claude-code for one)
#   make mcpb           Build the Claude Desktop extension bundle (dist/sellerclaw.mcpb)
#   make release-check  Report whether a new release is needed
#   make release        Bump version, tag vX.Y.Z, push -> CI publishes to PyPI
#
# Release usage:
#   make release                 # bump minor from the latest v* tag (default)
#   make release PART=patch      # bump patch
#   make release PART=major      # bump major
#   make release VERSION=1.2.3   # tag an exact version
#   make release ALLOW_DIRTY=1   # skip the clean-working-tree check
#   make release FORCE=1         # tag even if shipped files are unchanged
# REMOTE defaults to origin.

UV ?= uv
REMOTE ?= origin
PART ?= minor

# Files that actually ship in the wheel/sdist (see [tool.hatch.build] in
# pyproject.toml). Diffing these against the last v* tag decides whether a new
# release is warranted — test/CI/docs-only churn doesn't require one.
SHIPPED_PATHS = sellerclaw_cli pyproject.toml README.md

.PHONY: install lint test check build plugin mcpb release-check release

install:
	$(UV) sync --group dev

lint:
	$(UV) run ruff check .
	$(UV) run pyright

test:
	$(UV) run pytest -m unit

check: lint test

build:
	$(UV) build

# Assemble the Claude plugin variants from plugin/ (shared core + claude overlay + per-target
# manifests). claude-code lands in the committed plugins/ tree (the marketplace references it);
# the rest are artifacts under dist/. Build just one with `make plugin TARGET=claude-code`.
plugin:
	$(UV) run python scripts/build_plugin.py $(if $(TARGET),--target $(TARGET),)

# Build the Claude Desktop Extension bundle (.mcpb). Assembles the desktop target from plugin/
# (stamps the version into manifest.json), then packs it -> dist/sellerclaw.mcpb. The bundle launches
# the *published* sellerclaw-cli[mcp] via uvx, so rebuild and re-upload it after a release that
# changes the desktop manifest.
mcpb:
	$(UV) run python scripts/build_plugin.py --target claude-desktop
	npx -y @anthropic-ai/mcpb pack dist/plugins/claude-desktop dist/sellerclaw.mcpb

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

# Bump the version, create an annotated tag vX.Y.Z, push the branch and the tag.
# Pushing a v*.*.* tag triggers .github/workflows/release.yml, which verifies,
# builds, and publishes to PyPI. Refuses to tag when the shipped CLI is unchanged
# since the last v* tag (nothing to publish) — override with FORCE=1.
release:
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
	echo "Pushed $$tag — release.yml will verify, build, and publish $$tag to PyPI."
