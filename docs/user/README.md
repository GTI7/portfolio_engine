# Portfolio Engine — User Guide

This is documentation for **using** Portfolio Engine — installing it, setting up a portfolio, adding transactions, and getting the dashboard working. If you're looking for how the integration is built (architecture, ADRs, calculator design), that's in the repository root and `docs/adr/` instead — those are for contributors, not for using the integration day to day.

## Guides

1. **[Installation](INSTALLATION.md)** — getting the integration onto your Home Assistant instance and configured.
2. **[Getting Started](GETTING_STARTED.md)** — creating your first portfolio, adding holdings, recording transactions, and what "snapshots" are.
3. **[Dashboards](DASHBOARDS.md)** — importing the official dashboard package, and what each view shows.
4. **[Importing from a Broker](BROKER_IMPORT.md)** — reading a broker export into a report (Generic CSV, Interactive Brokers Flex Query), and how to add the results to your log.
5. **[Backing Up a Portfolio](BACKUP_EXPORT.md)** — writing a complete JSON backup of a portfolio's holdings, transactions, and snapshot history.
6. **[Troubleshooting](TROUBLESHOOTING.md)** — what to do when something looks wrong, and what each Repair issue means.
7. **[FAQ](FAQ.md)** — short answers to common questions.

## The short version

Portfolio Engine tracks one or more investment portfolios by reading plain YAML files you maintain (`holdings.yaml`, optionally `transactions.yaml`) and computing everything else — current value, return metrics, dividend income, risk metrics — automatically. It does not connect to your broker, does not place trades, and does not require any account beyond Home Assistant itself. You are always the one who decides what's in your portfolio; the integration only calculates from what you tell it.

If you just want to see it working, the fastest path is:
1. [Install the integration](INSTALLATION.md).
2. [Create a `holdings.yaml`](GETTING_STARTED.md#your-first-portfolio) with what you actually own.
3. [Import the dashboard](DASHBOARDS.md).

Transactions, snapshots, and the analytics entities are all optional layers on top of that — the integration is useful with just a `holdings.yaml`, and gets more capable the more you feed it.
