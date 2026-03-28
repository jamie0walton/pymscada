# Transpower dispatch (WS) — reference for `tds.py`

## Endpoints (polling)

- **`GET …/instructions/latest`**  
  Returns JSON: an **array** of the latest dispatch instructions for the
  endpoint (one entry per subscribed dispatch group in normal cases;
  **voltage** can yield more than one instruction).

- **`PUT …/acknowledgements`**  
  Sends **one** acknowledgement per HTTP request (`ackType`,
  `dispatchGroupName`, `sequenceNumber`).  
  Multiple instructions in one GET may require **several** PUTs.

## Correlation-Id

- Each dispatch instruction includes **`correlationId`** in the body; the same
  value appears as the **`Correlation-Id`** response header on
  **`GET /instructions/latest`** (when applicable).

- For **`PUT /acknowledgements`**, the client **must** set **`Correlation-Id`**
  to the **`correlationId`** of the dispatch being acknowledged (ACK, ACKA,
  ACKQ, ACKR all use that same id for that instruction).

- For the **initial** `GET /instructions/latest`, the spec says the client
  **should generate** a **`Correlation-Id`** (e.g. UUID). It must **not** be
  reused as a generic placeholder across all polls if you want proper
  end-to-end tracing.

## Sequence number

- **`sequenceNumber`** is **per dispatch endpoint + dispatch group**
  (`dispatchGroupName`), monotonic (max 9999), with a defined **reset to 1**
  case.

- **ACK** must reference the **`sequenceNumber`** (and group) of the
  instruction being acknowledged.

- **Non-voltage** groups: a newer instruction **supersedes** older ones for
  that group; acknowledging one instruction effectively covers prior ones for
  that group (except where the spec treats voltage differently).

## ACK types (relevant to implementation)

- **ACK** — receipt (automatic / system-level).

- **ACKA** — business acceptance (“will comply”).

- **ACKQ** — business query.

- **ACKR** — reject (where applicable, e.g. DNx).

Timing and escalation windows are defined in the guideline; implement ACK
then ACKA/ACKQ as your process requires.

## Payload shape — `energy` (`energyDispatch`)

- Present when **`dispatchGroupName`** is **`energy`**.

- Structure: **`energyDispatch`** with **`blocks`** and **`nodes`**, each with
  **`primaryValues`** (e.g. **MW**, **RESF**, **RESS**, **DD**) and optional
  secondary fields per OpenAPI.

- Floating values are typically **2 decimal places**; times are **ISO 8601
  with zone**.

## Payload shape — `voltage` (`voltageDispatch`)

- Present when **`dispatchGroupName`** is **`voltage`**.

- Structure: **`voltageDispatch`** with **`blocks`** / **`nodes`**; each node
  has **`primaryValues`** with at most one primary at a time — **`VOLT`** or
  **`MVAR`** (the other may be **null** and should be ignored).

- Voltage can be **per-node**; “latest” may return **multiple** voltage
  instructions (one per node/block as configured), each needing its own
  acknowledgement path (group + sequence + correlation).

## Cross-check for `tds.py`

- Poll: **`GET /instructions/latest`** with JWT **`Authorization`**, and a
  **client-generated `Correlation-Id`** per poll where you want traceability.

- Parse: for each array element, read **`dispatchGroupName`**,
  **`sequenceNumber`**, **`correlationId`**, and either **`energyDispatch`**
  or **`voltageDispatch`**.

- Ack: **`PUT /acknowledgements`** with body
  **`{ ackType, dispatchGroupName, sequenceNumber }`** and header
  **`Correlation-Id`** = that instruction’s **`correlationId`**.

## Source

[GL-SD-1045 Market Dispatch Integration – ICCP and Web Services
Guideline](https://static.transpower.co.nz/public/bulk-upload/documents/GL-SD-1045%20Market%20Dispatch%20Integration%20-%20ICCP%20and%20Web%20Services%20Guideline.pdf?VersionId=1TseCSWjUG_8vZgQy2GzNSIPUNK5IsWB)
(WS sections and OpenAPI appendix).
