# Workflow Plan

This workflow plan defines the changes to be made with me, incrementally. This plan sets the
rules that must be followed for changes in this project.

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
- Always ask permission for new ```import``` statements
- Do not attempt fully working code in one step
- Code should be concise, minimum necessary to achieve functionality
- Code should have clear separation of responsibilities (SRP)
- Code should be logically correct and exclude defensive programming
- Code should use type hints minimally, placed strategically so types are always clear
- Respect an 80 character line limit
- Mix between Test Driven Development and writing code then tests
- Use the bash alias command ```activate``` in command-line to set the correct ```python``` venv

# Documentation

See files:
- ~/docs/policies.md
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

1. **Kalman Filter Coefficients**
- Lake Aniwhenua, Kalman Filter values in test_observer.py are used in production
- When the lake level value changes rainflow does about a 15 minute bump
- smoother response would be better
- what parameters could I adjust to improve and why will these work
- make no changes

101. **Math element additions**
- I have added a deadband element to test_observer.py
- This if the output tag value differs by less that value or was updated more
  than heartbeat ago, set the new value
