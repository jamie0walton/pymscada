# Workflow Plan

This workflow plan defines the changes to be made with me. This plan sets the rules
that must be followed for changes in this project.

# Rules

- Focus on the immediate objective
- Do not expand the scope
- Only modify files that are listed in the **Working Files** section of this plan.
- Suggest updates to **Working Files** section if a file appears to be missing
- Never delete a file or directory
- Never create a new file or directory
- Never claim something is working
- Never complement me
- Never add empty lines
- Never add, edit, or remove comments unless I explicitly request a change to comments
- Always ask permission for ```import``` statements
- Do not attempt fully working code in one step
- Code should be concise, minimum necessary to achieve functionality
- Code should have clear separation of responsibilities (SRP)
- Code should be correct, pass lint tests and exclude defensive programming
- Respect an 80 character line limit
- Mix between Test Driven Development and writing code then tests
- Use the bash alias command ```activate``` in command-line to set the correct ```python``` venv
- Use broad error catching in ```try except``` blocks

# Documentation

See files:
- ~/docs/raised_errors.md
- ~/docs/tags.md

Most code must work well with the following files:
- ~/src/pymscada/bus_client.py
- ~/src/pymscada/bus_client_tags.py

Older modules use the deprecated option in tags.py instead of bus_client_tags.py.

# Working Files

Working files are:
- ~/src/pymscada/observer.py
- ~/tests/test_observer.py
- ~/src/pymscada/demo/observer.yaml

# Steps

5. **StorageRainEst**
   - confirm test passes
   - identify needed corrections
   - review coverage
   - identify plan to achieve coverage with concise tests

5. **Elements with No Tests**
   - Storage, Generator, RadialGate, FlapGate, Ramp, Noise, BidPeriod, inclass(), Canal, Observer

