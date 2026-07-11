# Security Policy

## Supported versions

Only the latest released version (see `manifest.json`'s `version` field and [`CHANGELOG.md`](CHANGELOG.md) for what that is) is supported with security fixes. There is no long-term-support branch.

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.** Instead, use GitHub's private vulnerability reporting: go to the **Security** tab of this repository → **Report a vulnerability**. This opens a private advisory visible only to the maintainer until a fix is ready.

If private reporting isn't available for some reason, open an issue that says only "security issue, please contact me" with no details, and wait for a response before disclosing anything further.

Include, where relevant:

- The affected file(s)/version.
- Steps to reproduce, or a minimal example.
- What you'd expect to happen versus what actually happens.
- Whether the issue requires local file-system access, a specific Home Assistant configuration, or is remotely exploitable (e.g. via crafted broker-import files or API responses).

## Scope

This integration reads local YAML/CSV files the user points it at and calls Yahoo Finance's public quote endpoint (see `custom_components/portfolio_engine/yahoo_auth.py`) — it does not accept inbound network connections of its own. Reports about data handling (e.g. path traversal in import file handling, unsafe YAML loading) are very much in scope; reports about Home Assistant Core itself or third-party dependencies should go to their respective projects.

## Response

Reports are typically acknowledged within a few days. There's no dedicated security team — this is maintained by a single person, so response time depends on availability, not severity triage.
