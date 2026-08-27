# How Each Module Works

Read the help!
```bash
pymscada -h
pymscada module -h
```

## checkout

Creates the configuration folders and sets up so you can use systemd.
Provides tools to let you compare and change elements of the files.

Select and create a user for MobileSCADA.
Create a .venv, activate it and install pymscada.
This venv is detected by `checkout` for setting up systemd executables.
Create an empty folder for your configuration.
`cd` to the folder and create a `pymscada.md` file .

Minimally, and for _a single instance only_ you can:

```bash
source /my/python/.venv/bin/activate
cd /path/to/config
touch pymscada.md
pymscada checkout
```

Running `pymscada checkout --overwrite --site My_Site` will set the site
name while also **wiping** any custom edits. So do this early or manually
edit the service files.

## bus

Must run.

Runs the MobileSCADA tag value exchange bus. This is required. If it stops
ensure all client modules are stopped. systemd files are set to stop all
other modules when this happens.

```bash
su -
systemctl start ms-bus
```

## wwwserver

Runs the web server for the user interface. Required for init values for tags.

While the web server port can serve pages directly, preferred setup is to use
apache to provide user logins, gzip files, and generally interface to the wider
network.

# Module Architecture

A module's parts follow the Single Responsibility Principle. Not every
module needs every part below, and a part may be repeated (e.g. once per
external connection) where that keeps its responsibility single.

This document describes a state the code is being migrated towards. Many
modules presently fail to comply with this structure.

## Orchestration

Instantiate the module. Own the `BusClient` connection. Construct the
separate parts of the module. Start the asynchronous methods, almost
all modules await forever after returning.

### Process entry point

`ModuleFactory`/`ModuleDefinition` construct the module from parsed CLI
options, then call `start()`.

`BusClient` must be constructed before any `TagTyped` tag anywhere in
the module — construction, not `start()`, registers the callback tags
require; creating a tag first raises `SystemExit`.

Tag-change callbacks should be attached only after `start()` and
`get_history()` complete, not at construction, so history backfill
isn't mistaken for a live change.

### Command-line/config wiring

`--config` and `--tags` files are loaded and passed as constructor
kwargs (e.g. `tag_info`). Orchestration must know the config's structure
well enough to route each section to the part it constructs (tag
definitions to the Tags namespace, one config entry per instance to
each Connection/session instance, the remainder to Module logic), but
it should not read or act on the meaning of values within a section —
that stays with the part the section is routed to.

### bus_ip validation

Resolve `bus_ip` with `socket.gethostbyname` before connecting, raising
on failure; `bus_ip=None` is accepted only to allow constructing a
module for testing without a bus connection.

### RTA (Request To Author) tags

A request/response tag registered directly on the `BusClient`
(`add_callback_rta`, `add_tag`), separate from any tag-change callbacks
owned by the module logic.

### History fill

Where module logic needs prior tag history before it can react
correctly, the orchestrator fills it (`history_tag`, `get_history()`)
between connecting the bus and starting the logic.

## Tag namespace

The tags a module uses, either declared as named attributes when the set
is fixed by the module's code, or built from configuration data when the
tag set is site-defined. The tags may be collected for bulk operations
(e.g. waiting until no tag value is `None`).

## Module logic

The module's own behaviour, driven by tag-change callbacks and/or a
periodic poll. Depends only on the tag namespace, never touches the bus
directly.

## Connection/session management

When a module talks to independent external endpoints, each endpoint's
state (connected/offline, in-flight requests, its own poll) is a
responsibility of its own, kept separate per endpoint rather than merged
into one shared state.

## Protocol encoding/decoding

When a module bridges to another wire protocol, translating that
protocol's wire format is its own responsibility: it has no knowledge of
tags or the bus, and the module logic has no knowledge of the wire
format.
