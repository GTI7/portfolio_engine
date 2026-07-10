# Installing Portfolio Engine

## Requirements

- A working Home Assistant instance (Home Assistant Core, Container, Supervised, or OS — any installation method that supports custom integrations).
- Home Assistant **2025.1 or newer** (see `docs/COMPATIBILITY_POLICY.md` for how this minimum is derived and what it means if you're on an older version).
- Access to your Home Assistant `config` directory (to place the integration's files, and to create the YAML files your portfolio is defined in).

Portfolio Engine does **not** require any external account, API key, or subscription. It fetches quotes and exchange rates from Yahoo Finance's public endpoints, which need no authentication.

## Step 1 — Copy the integration files

Copy the `custom_components/portfolio_engine/` folder from this repository into your Home Assistant config directory, so you end up with:

```
<your Home Assistant config directory>/
└── custom_components/
    └── portfolio_engine/
        ├── manifest.json
        ├── __init__.py
        ├── ... (everything else)
```

How you get the files onto your instance depends on how you access it:
- **Home Assistant OS / Supervised**: use the Samba add-on, the File Editor add-on's upload, or SSH.
- **Container / Core**: copy directly into the mounted config volume/directory.
- **HACS**: if this integration is published as a HACS custom repository, add it there instead — check the repository's README for the current HACS installation steps, since that process is HACS's own and not covered here.

## Step 2 — Restart Home Assistant

Custom integrations are only picked up on restart. Settings → System → Restart, or restart however you normally do for your installation type.

## Step 3 — Add the integration

1. Settings → Devices & Services → Add Integration.
2. Search for "Portfolio Engine".
3. You'll be asked for:
   - **Investments folder path** — a path *relative to your Home Assistant config directory* where your portfolio's YAML files live (e.g. `investments`). This folder doesn't need to exist yet with real data in it, but the path itself must exist — create an empty folder first if you haven't set up a portfolio yet (see [Getting Started](GETTING_STARTED.md)).
   - **Update interval** — how often (in minutes) to refresh prices and recompute everything. 15 minutes is a reasonable default; there's no benefit to setting this very low, since market quotes don't update faster than that anyway for most sources.
4. Submit. If the path doesn't exist, you'll get a clear error asking you to fix it — this is checked immediately, not discovered later as a broken integration.

## Step 4 — Confirm it worked

Settings → Devices & Services → Portfolio Engine should show a device per portfolio folder found under your investments path, each with its full set of entities (fourteen, as of this version — see `docs/ENTITY_CONTRACTS.md` for the complete list). If you haven't created a portfolio yet, you'll see nothing here — that's expected, and [Getting Started](GETTING_STARTED.md) covers creating one.

## Updating

Replace the `custom_components/portfolio_engine/` folder with the new version's files and restart Home Assistant. Your `holdings.yaml`/`transactions.yaml` files and snapshot history are stored separately (in your investments folder and Home Assistant's own storage respectively) and are never touched by an integration file update.

## Uninstalling

1. Settings → Devices & Services → Portfolio Engine → ⋮ → Delete, for each configured portfolio entry.
2. Delete the `custom_components/portfolio_engine/` folder.
3. Restart Home Assistant.

Your `holdings.yaml`/`transactions.yaml` files are untouched by uninstalling (they're just files in your investments folder — delete them yourself if you want them gone too). Snapshot history stored via Home Assistant's own storage is cleaned up automatically when you delete the config entry in step 1.
