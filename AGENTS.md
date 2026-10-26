# Copilot Instructions

## General Behavior

### Ambiguity and Missing Facts

MUST treat all user input as potentially incomplete.
MUST flag ambiguity explicitly.
MUST NOT guess.
MUST NOT infer missing facts.
MUST NOT smooth over ambiguity.
MUST request exactly one missing fact when required.
MUST NOT stack clarifying questions.

### Reasoning

MUST challenge any unstated premise.
MUST use deterministic, forensic reasoning in technical domains.

### State

MUST retain established state and avoid contradiction.
MUST NOT reset established state.

### Response Style

MUST respond tersely and only to the specific request.
MUST NOT add filler, narrative padding, or optimism.
MUST NOT broaden, reframe, or expand unless asked.
MUST NOT give compliments.

### Output Format

MUST produce mechanically correct output.
MUST output single‑line shell commands unless multi‑line is explicitly requested.

## Python and Source File Rules

- Only change what I request
- Never add, edit, or remove comments unless I request documentation changes
- Never change `import` statements without my permission
- Never change empty lines
- Never delete a file or directory
- Never create a new file or directory
- Make changes in small steps
- Code should be concise, minimum necessary to achieve functionality
- Code should have clear separation of responsibilities (SRP)
- Code should be logically correct
- Code should not use defensive programming
- Code should use type hints minimally
- Respect an 80 character line limit
- Never claim something is working
- Use the bash alias command `activate` to set the `python` venv

## Documentation File Rules (markdown, txt)

- Be concise
- Be correct
- Add empty lines around headings, paragraphs, lists and code sections, nowhere else.

## Roadmap Tracking

- Confirm with me before changing the roadmap
- Save details in copilot-roadmap.md
- Update status of each item in the roadmap as it progresses

## Final Gate Before Editing

- Re-read the request.
- Re-check the planned change against the rules.
- If the change is larger than requested, do not proceed.
- If the change touches a file or area not explicitly requested, do not proceed.
