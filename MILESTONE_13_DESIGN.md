# MILESTONE_13_DESIGN.md — Dashboard & User Experience

Design pass before implementation, matching `MILESTONE_11_DESIGN.md`/`MILESTONE_12_DESIGN.md`'s scope. **No code, YAML, or entities have been written for this milestone.** This document and ADR-0019 are the proposal.

## Starting position — this is not a greenfield dashboard

Portfolio Engine already ships a dashboard: `dashboards/portfolio_engine_dashboard.yaml`, a 7-view Lovelace YAML package (Overview, Performance, Allocation, Transactions, Analytics, Health, Import/Backup) built entirely from core card types (`entities`, `glance`, `markdown`, `gauge`) — no custom cards, no HACS dependency — documented in `docs/user/DASHBOARDS.md`. Milestone 13 is **not** "design a dashboard from scratch" — it's "take the existing, already-functional package to production/polished quality," closing its one real usability gap and reconciling its structure with a cleaner hierarchy.

**The existing package's one real gap:** every entity ID in the file is hardcoded with a `demo_portfolio` prefix, and the documented workflow is "find-and-replace `demo_portfolio` with your portfolio's folder name before importing." This is manual, one-time-per-install editing — it directly conflicts with this milestone's own "require minimal manual editing" and "scale from one portfolio to multiple portfolios" goals, since a second portfolio (created via Milestone 12's `create_portfolio` service or guided Config Flow) requires hand-duplicating and re-editing dashboard sections.

## Goals

- Close the find-and-replace gap — importing the package should require no per-install entity-ID editing.
- Scale automatically from one portfolio to N portfolios, including one added after the dashboard was first imported.
- Stay within core Lovelace card types — no custom cards, no HACS dependency, no frontend build tooling (see ADR-0019 for why).
- Reconcile the existing 7-view structure with a cleaner information architecture (below), without losing any currently-shown data.
- Improve mobile presentation of the wider tables (holdings, transactions).
- Identify, but do not fix, any backend (entity/service) gaps this review surfaces.

## Non-goals

- No new entities, sensors, or services in this milestone — see "Backend gaps discovered" below for what was found; those become their own future milestone if pursued.
- No custom Lovelace card, no custom Dashboard Strategy, no JS/frontend resource (ADR-0019).
- No multi-portfolio *engine* changes — the integration remains single-portfolio-per-config-entry under the hood (per `update_logic.py`'s existing scope); the dashboard's multi-portfolio support is a frontend-only capability layered on top of however many config entries/devices already exist.
- No portfolio *picker* UI (a dropdown to switch which single portfolio's detail is shown) — see "Risks" for why this is deferred.

## Entity inventory

All 15 entities Portfolio Engine currently exposes (`custom_components/portfolio_engine/sensor.py`), grouped as requested. Every entity already groups under one HA device per portfolio (`_PortfolioEntityBase.device_info`), which is exactly the grouping the dashboard's auto-discovery (ADR-0019) relies on.

| Group | Entity | Key attributes | Dashboard-ready today? |
|---|---|---|---|
| **Portfolio** | `sensor.<p>_value` | — | Yes — headline number |
| | `sensor.<p>_total_invested` | — | Yes |
| | `sensor.<p>_total_profit` | — | Yes |
| | `sensor.<p>_roi` | — | Yes — used in a gauge today |
| | `sensor.<p>_cash_balance` | — | Yes |
| **Holdings** | `sensor.<p>_positions` | `positions` (full table), `portfolio_id`, `portfolio_name`, `symbols_missing_quotes`, `fx_rates_missing` | Yes — the one attribute-only entity; today's Allocation view's holdings table is built entirely from this |
| | `sensor.<p>_concentration` | `largest_position`, `largest_winner`, `largest_loser`, `top5_concentration_pct`, `diversification_score`, `herfindahl_index`, `holding_count` | Yes |
| **Cash** | `sensor.<p>_cash_balance` | — | Yes (also listed under Portfolio — same entity, two natural groupings) |
| **Performance** | `sensor.<p>_roi` | — | Yes |
| | `sensor.<p>_money_weighted_return` | `status`, `cash_flow_count`, `as_of` | Yes |
| | `sensor.<p>_time_weighted_return` | `status`, `periods_used`, `as_of`, `annualized_pct` | Yes |
| **Analytics** | `sensor.<p>_dividend_income` | `status`, `lifetime`, `current_year`, `dividend_yield_pct`, `average_monthly_dividend`, `as_of` | Yes |
| | `sensor.<p>_drawdown` | `status`, `maximum_drawdown_pct`, `peak_value`, `peak_date`, `recovery_status`, `as_of` | Yes |
| | `sensor.<p>_volatility` | `status`, `daily_volatility_pct`, `observation_period_days`, `sample_count`, `as_of` | Yes |
| **Import** | `sensor.<p>_transaction_count` | `recent` (10 most recent transactions) | Yes |
| | `sensor.<p>_last_import` | `status`, `provider`, `as_of`, `transactions_read`, `imported`, `duplicates`, `rejected`, `warnings` | Yes |
| **Diagnostics** | `sensor.<p>_reconciliation` | `discrepancies`, `transactions_considered` | Yes |

**Redundant entities:** none found — each of the 15 has a distinct purpose and no two overlap in meaning. **Missing presentation entities:** see "Backend gaps discovered" below — this is where the real findings are.

## Backend gaps discovered (identified only — not implemented)

1. **No entity surfaces "today's change" despite it already being computed every refresh.** `PerformanceCalculator` (registered in `coordinator.py`, runs every cycle) produces `PerformanceResult.day_change_pct`, present in `coordinator.data["performance"]` — but no sensor reads it. The dashboard hierarchy this milestone was asked to evaluate explicitly wants "Today's change" on the Overview; today, nothing can show it. A future `PortfolioDayChangeSensor` (or an attribute on an existing entity, per `ENTITY_API_POLICY.md`'s "prefer adding entities over repurposing existing ones" rule) would close this — not built now.
2. **No entity surfaces the allocation breakdown despite it already being computed every refresh.** `AllocationCalculator` (`group_by="type"`) also runs every cycle; its result (`coordinator.data["allocation"]`) is discarded the same way. Today's "Allocation" view fakes a breakdown by iterating the raw `positions` attribute in Jinja rather than reading a purpose-built grouped result. A future entity/attribute would let the dashboard show a real by-type allocation table (and a pie-style visual, if ApexCharts is present) without re-deriving it in template logic.
3. **`PortfolioLastImportSensor` has no `docs/ENTITY_CONTRACTS.md` entry.** That doc's own governance rule states an entity "is not considered shipped until it has an entry here." All 14 other entities have one; this one (added Milestone 9) does not. A documentation-only fix, unrelated to code, flagged here since it surfaced during this review.
4. **`apply_import`/`create_portfolio` are not deregistered in `__init__.py`'s last-entry-unload cleanup.** Unrelated to the dashboard, but discovered while inventorying services for this design pass — flagged for completeness, not fixed here.

None of these are fixed in this milestone. Items 1–2, if pursued, would be their own future milestone (new entities need a design pass and `ENTITY_CONTRACTS.md` entries per ADR-0006/`ENTITY_API_POLICY.md` — not something to add as a side effect of a dashboard-only milestone).

## Dashboard technology — Option A vs B vs C, and the recommendation

- **Option A — pure Lovelace YAML.** What exists today. Zero frontend risk, but the shipped file still requires the find-and-replace step.
- **Option B — a dashboard package included with the integration.** Also already true today (`dashboards/portfolio_engine_dashboard.yaml` ships in the repo) — the gap isn't "is it included," it's "does importing it require manual editing."
- **Option C — a generated dashboard.** Two sub-options exist here, worth separating:
  - **C-full: a real custom Dashboard Strategy** (a `strategy:` key backed by a frontend JS resource that programmatically builds the dashboard from the HA entity registry at load time). Genuinely zero-config, but introduces a new artifact type (bundled JS), a new resource-registration step, and a new failure mode this project has no test coverage for.
  - **C-lite: Jinja auto-discovery inside plain Lovelace YAML.** HA's built-in template functions — `integration_entities('portfolio_engine')` (every entity this integration owns, across every device/config entry) and `device_id(entity_id)` (which device/portfolio an entity belongs to) — let a `markdown`/`template` card enumerate every configured portfolio and render one section per device, entirely inside Option A/B's existing plain-YAML approach. No custom card, no JS, no build step.

**Recommendation: Option A/B refined with C-lite** — see **ADR-0019** for the full reasoning. This gets the actual outcome "zero-configuration" was asking for (import once, never edit again, new portfolios appear automatically) without taking on C-full's frontend-build/test/distribution cost, which is disproportionate to a project that has never shipped any frontend JS and is still single-portfolio-per-install in practice. C-full is not rejected permanently — ADR-0019 names it as a future option if C-lite's per-view Jinja logic ever becomes unwieldy.

## Answer to the explicit question: zero-config vs. distributed package?

**Both, via C-lite — not a contradiction.** The package stays something a user imports once (Option B, distributed with the repo, following the exact "Raw configuration editor" flow `docs/user/DASHBOARDS.md` already documents) — that one-time import step isn't eliminated, and shouldn't be: HA has no mechanism for an integration to auto-create a user-visible dashboard without the user's explicit action, and doing so silently would be a worse UX than one documented import step. What *is* eliminated is every step after that first import: no find-and-replace, no per-portfolio duplication, no re-editing when a portfolio is added or renamed. That's the realistic, honest meaning of "zero-configuration" available here without adopting C-full.

## Dashboard hierarchy

The existing 7 views already cover the requested hierarchy closely. Proposed reconciliation — six views, merging Health + Import/Backup into one Administration view (matching the hierarchy sketch's own grouping) and renaming Allocation → Holdings (since it already contains the holdings table, not just allocation stats):

```
Overview        — headline numbers, returns, status, one block per portfolio
Holdings        — positions table, concentration/allocation stats
Performance     — ROI/MWR/TWR, annualized CAGR, plain-language explanation
Transactions    — recent activity table, total count
Analytics       — dividends, drawdown, volatility
Administration  — reconciliation health, data availability, last import, backup, diagnostics pointer
```

This is a rename/reorganization of existing views, not a new structure — every card that exists today has a home in this hierarchy; nothing is dropped.

## Dashboard Design Principles

Each view exists to answer one question a portfolio owner actually asks, not to showcase a category of data. Naming the question keeps every future card-placement decision simple: a new card belongs on a view if it helps answer that view's question, and belongs somewhere else (or nowhere yet) if it doesn't.

- **Overview — "How am I doing, right now, across everything I own?"** The landing view. A user opens this first, most often, and should be able to answer "am I up or down, and is anything wrong" without tapping into a second view. It's the only view that shows every configured portfolio at once (via C-lite discovery) — the moment a second portfolio exists, this is where "how's *everything* doing" gets answered in one scroll.
- **Holdings — "What do I actually own, and how concentrated am I in any one bet?"** A user comes here to check a specific position, or to sanity-check that they haven't drifted into an uncomfortable concentration in one symbol. This is inspection, not headline monitoring — it's the second view, not the first.
- **Performance — "How well is my money working, and by which measure?"** Distinct from Overview's "am I up or down" because it exists to explain *why* three different return numbers (ROI, MWR, TWR) can legitimately disagree, and which one answers which question. A user comes here when they want to understand their returns, not just glance at them.
- **Transactions — "What has actually happened in this account recently?"** An activity log, not a metric. Answers "did that dividend post," "when did I last buy," "how many events have there been" — audit-style questions, not performance questions.
- **Analytics — "What income am I generating, and how much risk am I carrying?"** Groups the two questions that are neither "current state" (Overview) nor "raw activity" (Transactions) nor "what do I own" (Holdings) — dividends and volatility/drawdown are both about the portfolio's *behavior over time*, one on the income side, one on the risk side.
- **Administration — "Can I trust this data, and what do I do if I can't?"** Not a portfolio question at all — a tooling question. A user comes here after Overview raises a concern (a reconciliation discrepancy, a missing quote), or when they're about to run an import/backup/export action. Deliberately separated from every other view so the five "portfolio" views stay free of operational clutter.

## Card Priority

Every card proposed for the six views, classified by how central it is to the view's own question (above) — Tier 1 is what a user should see without scrolling or expanding anything; Tier 2 is one glance/scroll away; Tier 3 is optional depth for a user who specifically wants it.

| View | Card | Tier | Why |
|---|---|---|---|
| Overview | At a Glance (value/invested/profit/ROI/cash) | **1** | Directly answers "how am I doing right now" |
| Overview | Returns (MWR/TWR) | 2 | Important, but a refinement of ROI already shown in Tier 1 |
| Overview | Status (reconciliation/positions/transactions) | 2 | A quick health check, not the headline number |
| Holdings | Holdings table | **1** | Directly answers "what do I own" |
| Holdings | Concentration gauge | 2 | The single most important allocation risk signal |
| Holdings | Concentration detail (diversification score, best/worst performer) | 3 | Depth for a user specifically auditing concentration |
| Performance | ROI gauge | **1** | The one number most users mean by "performance" |
| Performance | Return metrics table (ROI/MWR/TWR) | **1** | Core to the view's own question — why three numbers exist |
| Performance | CAGR markdown | 2 | A refinement (annualized) of a Tier-1 number |
| Performance | "What these numbers mean" explanation | 3 | Educational — read once, rarely again |
| Transactions | Recent activity table | **1** | Directly answers "what happened recently" |
| Transactions | Summary (total count) | 2 | Context for the table, not the point of the view |
| Analytics | Income & Risk entities (dividend/drawdown/volatility) | 2 | Important but not a daily-glance concern for most users |
| Analytics | Dividend detail | 3 | Depth for a user specifically tracking income |
| Analytics | Drawdown detail | 3 | Depth for a user specifically tracking risk history |
| Administration | Data integrity (reconciliation) | **1** | Trust is a precondition for believing every other view |
| Administration | Data availability (missing quotes/FX) | 2 | An actionable warning, but secondary to the reconciliation signal |
| Administration | Last import summary | 2 | Relevant only around when an import was actually run |
| Administration | Reconciliation discrepancy detail | 3 | Depth only needed once Tier 1 signals a problem |
| Administration | Import/backup instructions | 3 | Reference material, not a glance card |
| Administration | Diagnostics pointer | 3 | Reference material, not a glance card |

No card is dropped for being Tier 3 — this classification informs card *ordering* within each view (Tier 1 first, Tier 3 last), not what ships.

## Card layout mockups

### Overview (repeats once per configured portfolio, via C-lite discovery)

```
┌─────────────────────────────────────────────────┐
│  <Portfolio Name>              updated 4m ago    │
├─────────────────────────────────────────────────┤
│ At a Glance                                      │
│   Value             124,532.10                   │
│   Total Invested     98,000.00                   │
│   Total Profit       26,532.10                    │
│   ROI                    27.1 %                    │
│   Cash Balance        2,140.55                     │
├─────────────────────────────────────────────────┤
│ Returns                                          │
│   MWR (XIRR)             18.4 %                    │
│   TWR (cumulative)       22.9 %                    │
├─────────────────────────────────────────────────┤
│ Status                                           │
│   Reconciliation           ok                     │
│   Positions                 12                     │
│   Transactions               84                     │
└─────────────────────────────────────────────────┘
        (repeats again here if a 2nd portfolio exists)
```

### Holdings

```
┌───────────────────────────────────────────────────┐
│ Holdings                                           │
│  Symbol    Shares    Value        Gain %           │
│  AAPL       10       1,845.20     +12.4%            │
│  VWCE.DE    25       3,210.00     + 8.1%             │
│  ...                                                │
├───────────────────────────────────────────────────┤
│ Concentration                        [gauge 0-100] │
│  Largest position     AAPL (34%)                    │
│  Top-5 concentration  78%                            │
│  Diversification      62 / 100                        │
│  Best performer       AAPL (+12.4%)                    │
│  Worst performer      XYZ (-3.2%)                       │
└───────────────────────────────────────────────────┘
```

### Performance — unchanged from today's shipped view (gauge + return-metrics table + CAGR + plain-language explanation markdown).

### Transactions — unchanged (summary + 10-most-recent table).

### Analytics — unchanged (dividend/drawdown/volatility entities-card + two detail markdown cards).

### Administration (merges today's Health + Import/Backup)

```
┌─────────────────────────────────────────────────┐
│ Data Integrity                                   │
│  Reconciliation        ok                         │
│  Missing quotes        none                        │
│  Missing FX rates      none                          │
├─────────────────────────────────────────────────┤
│ Import / Backup                                  │
│  Last import: 12 imported, 2026-07-01              │
│  Run import_transactions / apply_import /            │
│  export_portfolio_data via Developer Tools -> Actions │
├─────────────────────────────────────────────────┤
│ Diagnostics                                      │
│  Settings -> Devices & Services -> Portfolio        │
│  Engine -> Download Diagnostics                       │
└─────────────────────────────────────────────────┘
```

## Navigation proposal

One dashboard, six views (tabs across the top, matching the existing package's `views:` structure and icons exactly — no change to HA's native view-tab navigation). Overview is the landing view and, via C-lite discovery, is the one place that shows every configured portfolio at a glance; the other five views show per-portfolio detail, repeating the same block once per device when more than one portfolio exists (stacked vertically, portfolio name as a section header) — no dropdown/picker required for the common single-portfolio case, and no extra setup (no `input_select` helper) needed for the multi-portfolio case either.

## Mobile responsiveness

No new mechanism needed — every card type this package uses (`entities`, `glance`, `markdown`, `gauge`) already reflows to Lovelace's default single-column mobile layout, and view tabs already collapse into the Companion App's standard bottom/side navigation. Two concrete adjustments worth making during implementation:
- The holdings and transactions markdown-table cards are the widest content in the package (4–5 columns) — on a narrow viewport these scroll horizontally inside the card rather than reflowing, which is acceptable but worth confirming looks reasonable on an actual phone during Phase 2's manual verification (per `MANUAL_VALIDATION_RUNBOOK.md`'s existing scope — this is exactly the kind of "real device, real screen" check that suite already flags as manual-only).
- Multiple stacked per-portfolio Overview blocks (C-lite discovery) should each start with a clear portfolio-name heading so scrolling past several portfolios on a phone stays orientable.

## Implementation phases (proposed — not started)

Every phase below edits the same single file, `dashboards/portfolio_engine_dashboard.yaml`, in place — none creates a parallel or alternative dashboard, and none changes any entity ID, service, or attribute shape a user's existing customized copy might depend on.

```
Phase 1 — Improve the existing shipped dashboard (no second dashboard, no breaking changes)
  Constraints, stated explicitly since this is the phase every later one depends on:
    - Improve dashboards/portfolio_engine_dashboard.yaml in place. Do not create a
      second/parallel dashboard file — there is exactly one official package,
      before and after this milestone.
    - Preserve backward compatibility: a user who already imported today's
      hardcoded-demo_portfolio file keeps a working dashboard whether or not they
      ever re-import the new version. Nothing about this phase changes any entity
      ID, service, or attribute shape that the old file (or a user's own hand-edited
      copy of it) depends on - ADR-0006's entity-ID stability guarantee is what
      makes this possible.
    - Re-importing is opt-in, not automatic. HA has no mechanism to silently update
      a dashboard a user already pasted in - the improved file is adopted the same
      documented way the original was (docs/user/DASHBOARDS.md's existing "Raw
      configuration editor" steps), just without the find-and-replace step once
      adopted.
  Scope of the improvement itself: rewrite the Overview view's Jinja to use
  integration_entities('portfolio_engine')/device_id(...) grouping instead of
  hardcoded demo_portfolio entity IDs. This is where the hardest, most novel Jinja
  work happens; every later phase reuses the same discovery pattern and the same
  three constraints above.

Phase 2 — Holdings dashboard
  Merge today's Allocation view's holdings table + concentration cards under the
  new discovery pattern.

Phase 3 — Performance dashboard
  Port the existing Performance view to the discovery pattern (least Jinja change
  needed — it's already close to entity-agnostic).

Phase 4 — Analytics + Transactions dashboards
  Port both remaining detail views to the discovery pattern.

Phase 5 — Administration dashboard
  Merge Health + Import/Backup into one view under the discovery pattern; update
  docs/user/DASHBOARDS.md to remove the find-and-replace instructions and describe
  the new single-import, auto-scaling behavior.
```

Each phase is independently shippable and testable by hand against a real HA instance with 1 and 2+ configured portfolios (no automated test coverage is possible or expected here — dashboard YAML isn't exercised by `tests_ha/`).

## Risks

- **Jinja auto-discovery correctness is verified only by hand**, not by the automated suite — a mistake in the `integration_entities`/`device_id` grouping logic could silently show the wrong portfolio's data under the wrong heading. Mitigate by testing explicitly with 2+ portfolios configured before calling any phase done, not just 1.
- **A portfolio *picker* (dropdown to view one portfolio at a time instead of stacked blocks)** was deliberately left out of this design — for 2-3 portfolios, stacked blocks are simpler and need no extra HA helper entities; if a future user has many more portfolios than that, revisit with an `input_select` + Jinja filter, or reconsider C-full (a real Dashboard Strategy) at that point.
- **HA version drift in template function availability** — `integration_entities`/`device_id` are established, stable Jinja functions, but any future HA core change to their behavior would affect every view at once, not just one. Worth a quick recheck against `hacs.json`'s `"homeassistant": "2025.1.0"` minimum during implementation.

## Future enhancements

- New `PortfolioDayChangeSensor`/allocation-breakdown entity (or attributes) — see "Backend gaps discovered" #1–2 — would let Overview show "today's change" and Holdings show a real allocation-by-type table, once designed and given `ENTITY_CONTRACTS.md` entries.
- A real custom Dashboard Strategy (C-full, ADR-0019) if the Jinja-discovery approach's per-view logic ever becomes unmanageable, or if HA's frontend template-function support is ever reduced.
- ApexCharts-based visual allocation/performance charts (already mentioned as an optional, non-required add-on in `docs/user/DASHBOARDS.md` — unaffected by this milestone).

## Acceptance criteria (proposal stage — none built yet)

- [ ] No entity, service, or config-flow behavior changes as part of this milestone — confirmed against the "no code changes" constraint.
- [ ] Exactly one official dashboard file exists before and after this milestone — no second/parallel dashboard created.
- [ ] A user's existing, already-imported (and possibly hand-edited) copy of today's dashboard keeps working unmodified — nothing in this milestone requires re-import to avoid breakage.
- [ ] `dashboards/portfolio_engine_dashboard.yaml` requires zero entity-ID editing after import, for both 1-portfolio and 2+-portfolio installs.
- [ ] Every card/view present in the current shipped package has a home in the new 6-view hierarchy — nothing dropped.
- [ ] `docs/user/DASHBOARDS.md` updated to remove the find-and-replace instructions once Phase 5 lands.
- [ ] Both backend gaps (day-change, allocation-breakdown entities) are documented as explicit future-milestone candidates, not built here.
