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

13. **Observer Element behaviour**
- follow_step is intended to run on a preset interval
  add exception_step where [attribute]_read_tag is present and
  add_callback can be used with the Tag to generate a by exception update
  describe implementation approach asking questions where approach is unclear

98. **Elements with No Tests**
- Ramp, Noise, BidPeriod, inclass(), Canal, Observer

99. **Canal**
- this element has never worked

100. **Storage**
- add new test_storage function
- test function can be a simpler version of StorageRainEst
- will need additional storage elements
- check test
- review coverage
- iteratively improve coverage


