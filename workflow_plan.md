# Workflow Plan

This workflow plan defines the changes to be made with me. This plan sets the rules
that must be followed for changes in this project. Maintain the accuracy of this plan
in accordance with my instructions. Observe changes I make to the plan on each review.
The details in this plan are more important that the chat history and other rules.

---
# Requirements

## Rules

- Commands require my explicit permission to run EVERY TIME!
- Focus on the immediate objective, do not pro-actively expand
- Only modify files that are listed in the **Working Files** section of this plan.
- Suggest updates to **Working Files** section if a file appears to be missing
- Never delete a file or directory
- Never create a new file or directory
- Never claim something is working
- Never complement me
- Never pro-actively edit code
- Never add empty lines
- Never add, edit, or remove comments unless I specifically request
- Always ask permission for ```import``` statements
- Do not attempt fully working code in one step

## Preferences

- Code should be:
  - Concise - as a minimal expression of logic necessary to achieve functionality
  - Clear - readable with good separation of responsibilities (SRP)
  - Correct - right types and values and without defensive programming styles
- Respect an 80 character line limit
- Aim to meet linter rules, but only for code within the scope of change
- Test Driven Development (TDD) is preferred, however tests will also follow code
- Use the bash alias command ```activate``` in command-line to set the correct ```python``` venv
- Use broad error catching in ```try except``` blocks
- ```coverage``` with ```pytest``` shall achieve 98% at completion of the plan

## Documentation

Refer to the files in /docs/ for documentation. Advise any that are incorrect. Pay particular
attention to:
- /docs/raised_errors.md
- /docs/tags.md

Some of the codebase is preferred or has a preferred style, including:
- /src/pymscada/bus_client.py
- /src/pymscada/bus_client_tags.py

## Process

Observe the rules, preferences and documentation. Consider the **Context** and then identify
the changes needed to meet the **Objective**. Update the **Execution Plan**. Carry out changes
when I instruct you to proceed.

---
# Task

## Working Files

Update this list as needed:

- /src/pymscada/observer.py
- /tests/test_observer.py
- /src/pymscada/demo/observer.yaml

## Context

Observer has been imported from an earlier version of this codebase with differences in environment,
coding style, and without a good set of tests. This code is not in production so changes to both
code and tests to achieve good style is intended.

## Objective

Fix inconsistencies in the code, add tests for Observer Elements.

## Execution Plan

Steps:

5. **StorageRainEst**
   - confirm test passes
   - identify needed corrections
   - review coverage
   - identify plan to achieve coverage with concise tests

5. **Elements with No Tests**
   - Storage, Generator, RadialGate, FlapGate, Ramp, Noise, BidPeriod, inclass(), Canal, Observer

