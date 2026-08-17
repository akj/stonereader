# Distribution: an unsigned per-user installer, GitHub Releases as the update feed

## Status

Accepted (design contract, 2026-08-16). Builds on ADR-0014 — update consent
is an Offer in the asking grammar. Otherwise this is the first ADR about
shipping StoneReader rather than building it.

## Context

StoneReader ships to screen-reader users on Windows as a frozen build; a User
installs an artifact, not a Python environment. Releases matter more here than
for most desktop apps: the card database is whatever `hearthstone-data`
version the build bundled, so when Hearthstone patches, Users read stale cards
until a new StoneReader release reaches them. Distribution and updating are
therefore part of the product, not an afterthought — and whatever protocol the
first shipped client speaks, every later release must keep answering.

## Decision

### The artifact is a per-user Inno Setup installer

Releases ship a PyInstaller one-dir build wrapped in an Inno Setup installer
that installs per-user: no UAC prompt at install time and — the real reason —
none at update time, so the app can replace itself without an elevation dance.
Start Menu shortcut, no autostart, no desktop icon by default. Inno's wizard
is fully accessible to NVDA, which is what makes an installer the right shape
for this audience at all.

### GitHub Releases is the update feed

There is no update server and no manifest file. The repo is public; the
protocol is the GitHub Releases API itself: the app asks `releases/latest`,
compares the tag to its own version, and downloads the attached installer.
That makes two things permanent wire contract — the repo stays public, and
tags stay `vX.Y.Z` with the tag matching the `pyproject.toml` version (CI
enforces the match; the app reads its version via package metadata). Old
clients in the field will query this shape forever.

### Updates prompt; they never happen silently

An async check on startup (never blocking launch) plus a manual "Check for
updates" item. If a release is newer, the app says so and waits — as an
**Offer** in the asking grammar (ADR-0014): "StoneReader {version} is
available — press Control Enter to update", ignorable for free, never a
dialog. Only after the User accepts does the app download the installer, run
it `/SILENT`, and exit; the installer relaunches the app. Consent once at the
Offer — the wizard ceremony is reserved for the first manual install. Stable
releases only; no prerelease channel.

### The build is unsigned, deliberately

First-time downloaders hit SmartScreen and the release notes document the
bypass. Updates do not: the app launches the downloaded installer as a plain
subprocess, and SmartScreen lives in the shell-execution path that route never
traverses. Download integrity rests on TLS to GitHub — adequate for this
threat model. Signing (Azure Trusted Signing is the cheap route) is a
first-impression fix to buy when strangers hitting the SmartScreen wall is a
real funnel problem, not before.

## Alternatives considered and rejected

- **An update framework** (Velopack, Squirrel, the late PyUpdater). Rejected:
  delta patches, channels, and staged rollouts are machinery for a scale this
  project doesn't have. "Download the installer, run it" is the entire
  protocol, and Inno already knows how to upgrade in place.
- **A one-file exe instead of an installer.** Rejected: slower every-launch
  self-extraction, the highest antivirus false-positive rate, and no
  Start Menu presence — and "unzip and find the exe" is a worse story for
  non-technical Users than an accessible wizard.
- **Silent background auto-update.** Rejected: the app changing under a
  screen-reader User mid-session is exactly the kind of surprise this audience
  cannot glance at.
- **Keeping the code private behind a public shadow releases repo.** Rejected:
  two repos to maintain so that one can stay hidden, for a tool whose whole
  point is that its audience finds and updates it.
- **Per-machine install.** Rejected: every update would demand elevation,
  which kills unattended self-update.
- **Code signing from day one.** Deferred, not refused — cost and CI secret
  ceremony against an audience that currently follows the repo.
