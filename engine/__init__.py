"""Portfolio Engine — HA-independent calculation core.

See docs/adr/ for the reasoning behind this package's boundaries.

Versioned independently of the Home Assistant integration that will embed
it (see docs/adr/0007-independent-engine-versioning.md) — this package can
evolve, release, and be tested on its own release cadence.

1.0.0 (Milestone 10): a deliberate stability declaration, not a code
change - the engine hasn't been touched since Milestone 7 (three
consecutive milestones: 8, 9, 10, all "consume the platform, don't extend
it"). The calculation API (models, calculators, Calculator interface) is
considered stable from this point forward; a future breaking change to
any of it should bump the major version, per normal semver expectations.
"""

__version__ = "1.0.0"
