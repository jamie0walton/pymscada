# WITS offer client — iodriver refactor (working plan)

## Working Files
- working_plan.md
- src/pymscada/iodrivers/wits_client.py

## Objective

Port the working POC in `src/pymscada/poc/witsclient_mel.py` into
`src/pymscada/iodrivers/wits_client.py` as **WITSClient** + **WITSConnector**,
mirroring the **split** in `src/pymscada/iodrivers/tds_client.py` (**TDSClient**
/ **TDSConnector**): outer class connects the bus and starts the connector;
inner class owns HTTP lifecycle and tag I/O. **WITS is not a polling service:**
unlike **TDS** (e.g. **`Periodic` every 10 s**), **WITS** reacts when the bid
tag (**`tags.bid`**, demo **`MW_plan`**) **updates**, via a **callback**
(**`in_pub`** or equivalent on that **`TagDict`**). On each such event the
client **recomputes** the offer from **`MW_plan`** plus **`window`** /
**`horizon`** (and related config); it **POSTs** only when that outcome **differs**
from what should already be reflected at WITS (same idea as POC
**`currentTagDict`** vs **`futureTagDict`**, including shifts driven by **time
window** / **horizon**). **Most callbacks are no-ops** (nothing to send). If an
operator sets **`state`** to **`RESET`**, **treat `MW_plan` as changed** and
**send** (forced refresh). **`_wits_state`** must be **wired** so that change
(e.g. **`RESET`**) **runs the same evaluation** as an **`MW_plan`** update (not
only the bid tag callback). Behaviour should
stay equivalent to the POC (build CSV offer from bid periods, POST multipart
upload, update status tags), **except POC `dryrun`, which is removed**, while
adopting pymscada iodriver conventions:
**no `requests`**, **`BusClient` instead of `BusApp`**, flat config keys as in
`src/pymscada/demo/witsclient.yaml` (`bus_ip` / `bus_port` plus top-level WITS
and offer fields), and register the module in `src/pymscada/module_config.py`
(new `ModuleDefinition`, same pattern as `tdsclient`). The POC **`control`**
tag is **removed**; the configured **`state`** tag (`tags.state` →
`_wits_state` in the demo YAML) **replaces** it and covers **the same operator
/ lifecycle duties** (idle, busy, operator trigger, off, send gating, etc.—
exact value map still to pin in Execute). **`state` also carries host
switching**: **primary** vs **`alt_host`** follows the same *idea* as TDS (try
primary, on **POST** failure switch to alt, recover), merged into that single
bus tag. **Operator `RESET`** (see above) is **force-send**, not the same wording
as every **host** sub-state — **Execute** reconciles the full **`TagInt`**
layout. **Host switching** applies on **POST** paths; **idle work** is **not** a
fixed-interval poll.

## Source behaviour (`witsclient_mel.py`)

- **Config (POC)**: nested `wits` and `offer` dicts; **`witsclient.yaml`** is
  flat — map fields into the connector (same semantics, different layout).
- **`current_tag_update(tags, utcSeconds)`**: uses `bid_period` / `bid_time`
  (POC: `ms`); builds `currentTagDict` keyed by trading date and bid period from
  `tags['MW_plan']`-style structure (`period` / `setpoint` lists, DST edge cases
  for periods 47–50).
- **`build_offer`**: CSV rows per trading period; `None` → `11`.
- **`send_request`**: `requests` + `MultipartEncoder` POST; session with initial
  delay; sets `_wits_status`, `_wits_upload_id`, `_wits_status_code`,
  `_wits_errors` from JSON body or errors.
- **`send`**: builds offer, updates `_wits_sent`, maintains `futureTagDict` vs
  `currentTagDict` gating (caller in POC decides when to send). POC **`dryrun`**
  is **dropped** in the iodriver (always real POST when send runs).

## Orchestration today (`poc/witsclient.py`, for reference only)

- **`BusApp`**, queue + executor, **`control`** tag values `0/1/2/3` (idle,
  busy, operator trigger, off), health tag mod-60 for timed runs. Commented line
  shows old name `_wits_control`. **Refactor: drop `control` entirely.** Use only
  **`tags.state` / `_wits_state`** via **`BusClient`** + typed tags: it should
  do **what `control` did**, **plus** reflect or drive **host / `alt_host`**
  switching (one tag, not a second “conn state” tag unless implementation
  detail requires a private non-bus field for transient sub-states).

## Template to match (`tds_client.py`)

- **Imports**: `aiohttp`, `BusClient`, typed tags (`TagInt`, etc.). **`Periodic`**
  is **TDS-specific** for ~10 s polling; **WITS** does **not** use that pattern as
  its main driver (see Objective); drop **`Periodic`** from **WITS** if unused.
- **TDSConnector**: `ClientSession`, host selection from **`state_tag`** and
  `failed_time` / 60s threshold, `poll` loop via `Periodic`, `start()` sets
  initial state (TDS **`state_tag`** is **connection-only** on the bus).
- **WITS (this work)**: bus-facing **`tags.state`** replaces **`control`** and
  subsumes **host switching** (see Objective). **No** **`poll`** every N
  seconds: drive work from **`MW_plan`** (**`tags.bid`**) **callbacks**; **TDS**
  stays **active** on an interval, **WITS** is **usually idle** after deciding
  no send is needed.
- **TDSClient**: `__init__(bus_ip, bus_port, **kwargs)` stores `Config(...)`
  dict, optional `BusClient`, `start()` awaits `busclient.start()` then
  connector `start()`.
- **Config loading**: CLI loads YAML via `Config` in `module_config.create_module`
  — top-level keys become `kwargs`. **`witsclient.yaml`** now uses the same bus
  keys as **`tds.yaml`**: `bus_ip`, `bus_port`; remaining connector fields are
  also top-level (no nested `wits` / `offer` objects).

## Target config (`demo/witsclient.yaml`)

Flat YAML (single document): **`bus_ip`**, **`bus_port`**, then WITS endpoint
**`host`**, **`alt_host`**, path **`put`**, **`user`**, **`password`** (env
placeholders expanded by `Config`). Offer-related scalars at the same level:
**`window`** (was hardcoded `3660` in POC), **`horizon`**, **`timeZone`**,
**`bus`**, **`site`**, **`startPeriod`**, **`maxOutput`**, **`maxRampUpRate`**,
**`maxRampDownRate`**, **`service_type`** (e.g. `MW`; replaces POC
`offer['services']` list — loop logic should treat this as the one service type
or extend schema if multiple types are needed again). **`clientCode`**. Nested
**`tags`**: `bid`, **`state`** (replaces **`control`**; includes host-switch
behaviour), `sent`, `status`, `upload_id`, `upload_time`, `status_code`,
`errors` — bind **`TagDict` / `TagStr` / `TagInt`** after `BusClient.start()`.
No **`dryrun`** / **`dry_run`** in YAML or code.

## Modules and functionality required (assessment)

1. **`pymscada.bus_client.BusClient`**: `start()` before typed tag construction;
  same pattern as `TDSClient` / `ModbusClient`.
2. **`pymscada.bus_client_tag`**: `TagInt`, `TagStr`, `TagDict` (for `MW_plan`-
  shaped bid tag and string status fields).
3. **`TagDict`** (**`tags.bid`** / **`MW_plan`**) **callback** (**`in_pub`** or
  **`BusClient`** pattern): on update, re-run **`current_tag_update`** logic and
  compare to last-sent / **future** snapshot; **POST** only when **content** or
  **window** / **horizon** implies a new offer. **`state` → `RESET`**: treat as
  **dirty**, **must send**; **`_wits_state`** must invoke the same evaluation
  path (not only **`MW_plan`** updates). Not **`Periodic`**-driven (contrast
  **TDS**).
4. **`aiohttp`**: `ClientSession`, POST with multipart body equivalent to
  `MultipartEncoder` fields `filename` + `order-type`; parse JSON response like
  POC.
5. **`pymscada.bid_period` / `pymscada.bid_time`** (from `misc` via package
  `__init__`): replace POC `ms` imports for period math (**import path is a
  user-gated change** per project rules — confirm before editing code).
6. **`json`**: response parsing (`upload_id`, `upload_errors`).
7. **`module_config.py`**: new entry e.g. `witsclient` →
  `pymscada.iodrivers.wits_client:WITSClient`, `tags=False` if tags only come
  from bus (same as `tdsclient`), epilog pointing at demo YAML path.
8. **`state` tag (single bus tag)**: encode **upload gating** (former
  **`control`** where relevant), **`RESET`** = **force send** (MW_plan treated as
  changed), **`currentTagDict` / `futureTagDict`** interaction, and **host /
  `alt_host` switching**
  (TDS-style transitions adapted to **POST** outcomes: non-200 or network error,
  threshold, session reset). Concrete **integer (or enum) layout** for all of
  that is **Execute-step detail**; there is **no separate `control`** and no
  requirement for a second YAML tag for failover unless code keeps a **private**
  mirror of sub-states.

## Gaps — missing steps / modules / components

- **`wits_client.py`**: behaviour **incomplete**; must implement **callback-led**
  send logic (not **TDS**-style **Periodic** poll).
- **`module_config.py`**: no **`witsclient`** `ModuleDefinition` (only
  **`witsapi`** exists); CLI cannot start the offer uploader.
- **`kwargs` hygiene**: `Config` loads a nested **`tags`** dict plus **`bus_ip`**
  / **`bus_port`**. **WITSConnector** must not receive those keys unless its
  `__init__` accepts them — plan an explicit **pop/split** (mirror how other
  clients separate bus/tags from device config).
- **`state` value encoding**: how **operator modes**, **busy/idle**, and
  **host-routing sub-states** share one **`TagInt`** (ranges, reserved values,
  or private helper fields) is still to be specified at implementation time;
  architecture is **one bus tag** (`tags.state`), **`control` deleted**.
- **Orchestration**: **MW_plan** callback is the **primary** path; POC **health
  mod 60** / **queue** are **not** carried forward as a timer poll. **`aiohttp`**
  is async; **executor** likely **unnecessary** unless something stays blocking.
- **Tag wiring**: **`MW_plan`** **`in_pub`** (or equivalent) is **required**;
  **`_wits_state`** needs a path so **operator `RESET`** triggers evaluation too;
  **host** sub-states — detail at Execute.
- **YAML fields unused by POC**: **`timeZone`**, **`startPeriod`**, and
  **`service_type`** (beyond assuming MW) have **no mapping** in
  `witsclient_mel.py` yet — either implement, ignore with intent, or drop from
  YAML.
- **HTTP details**: **URL** join (`host` + `put` slashes), optional **timeout**
  class, whether to keep POC’s **15s first-session delay**, and **session**
  reset on failure (POC nulled session on errors).
- **Dependencies**: remove reliance on **`requests`** / **`requests_toolbelt`**;
  **`aiohttp`** is already in **`pyproject.toml`** — no new dep for HTTP.
- **Logging**: POC **`ms.Log`** → iodriver **`logging`** (as **`tds_client`**).
- **Tests / docs**: no **`tests/iodrivers/test_wits_client.py`** (or similar);
  optional **`iodrivers` doc** (e.g. beside **`tds_client.md`**) not planned.

## Out of scope for this document

Implementation in `wits_client.py`, edits to `module_config.py`, further YAML
changes beyond the current demo shape, and tests — pending your next-step
approval and updated **Working Files** list.
