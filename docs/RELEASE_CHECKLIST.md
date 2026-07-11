# Release Checklist

This is what's left to actually publish Portfolio Engine, once it's in a real, public GitHub repository — none of this is achievable from a development sandbox without one, so it's written as a checklist for whoever has that access, not something already done.

## Before the first tagged release

- [x] Replace the placeholder URLs in `manifest.json` (`documentation`, `issue_tracker`) with the real repository's URLs — done for v1.0.1, now pointing at `github.com/GTI7/portfolio_engine`.
- [x] Replace the placeholder `codeowners` entry (`@example`) with the real GitHub username(s) — now `@GTI7`.
- [ ] Add a repository description on GitHub (HACS uses it) and topics (`home-assistant`, `hacs`, `custom-integration`, `portfolio`, `finance`, or similar — used for HACS store searchability, not displayed directly).
- [ ] Confirm the repository is public — HACS only works with public repositories.
- [ ] Update the copyright line in `LICENSE` if the actual copyright holder differs from the placeholder.

## Tagging a release

- [ ] Bump `manifest.json`'s `version` field to match the release tag (semver, no leading `v` inside the JSON value itself).
- [ ] Create a **GitHub release** (not just a git tag — HACS specifically requires a release, tags alone aren't picked up) tagged `vX.Y.Z` matching `manifest.json`'s version.
- [ ] Write release notes summarizing what changed — `CHANGELOG.md`'s corresponding entry is a good starting point, condensed for an end-user audience rather than the full contributor-facing detail.

## HACS

- [ ] Confirm `hacs.json` and `LICENSE` are present at the repository root (both already added — see this milestone's changes) and a README exists (already present).
- [ ] To make the repository installable as a **custom repository** in HACS immediately: nothing further needed once the above is done — users can add it via HACS's "Custom repositories" menu right after the first release.
- [ ] To pursue inclusion in the **HACS default store** (so users find it without adding a custom repository URL): follow HACS's own [inclusion process](https://www.hacs.xyz/docs/publish/include/) — open a PR against `hacs/default`, which runs automated checks (manifest validity, at least one release, active repository, etc.). This is optional and can happen well after the first release; a custom-repository listing is fully functional on its own.
- [ ] Consider a `home-assistant/brands` submission (an icon/logo) if pursuing a polished HACS store presence — see `docs/QUALITY_SCALE.md` for why this couldn't be done from this environment.

## Ongoing

- [ ] Each subsequent release: bump `manifest.json`'s `version`, tag a new GitHub release, update `CHANGELOG.md`.
- [ ] Re-run the full test suite (`tests/`, `tests_integration/`, `tests_ha/`) and `scripts/benchmark.py` before tagging — the same discipline every milestone in this project has followed, now applied to release cutting specifically.
- [ ] Periodically re-run `docs/QUALITY_SCALE.md`'s self-assessment as HA's own Quality Scale criteria evolve.
