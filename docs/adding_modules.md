## Adding Modules

Modules are separate processes started by the `pymscada` CLI. Each module
typically connects to the message bus (via `BusClient`) and either polls
an external system or serves local logic/web requests.

Modules are configured from YAML files loaded by `pymscada` and, when
applicable, by a `tags.yaml` schema file.

## How modules are added

1. Implement the module class: add a new Python module under
   `src/pymscada/` (often `src/pymscada/iodrivers/<name>.py`), implement a
   class that can be constructed as `ClassName(**config_dict)`, and provide
   `async def start(self):`. `pymscada` injects config keys from `--config`
   (or the default `<module>.yaml`) when `config=True`, and injects `tag_info`
   from `--tags` when `tags=True` in the module definition.

2. Register the module with the CLI: edit `src/pymscada/module_config.py` and
   add a new `ModuleDefinition(...)` entry in `create_module_registry()`.
   Choose `name` for the CLI subcommand (and default config filename),
   set `module_class` to `'<python.module.path>:<ClassName>'`, and set
   `config`/`tags` to match how your module consumes configuration.

3. Add demo config and service files (so `pymscada checkout` works): add a
   default YAML config under `src/pymscada/demo/` with the same name as the
   module (e.g. `<name>.yaml`). If you use systemd, also add/update a service
   template under `src/pymscada/demo/` (for example
   `pymscada-io-<name>.service`). Then run `pymscada checkout` to copy the demo
   files into your local `config/` folder where systemd reads them.

## Standard usage

Run a module directly with:
`pymscada <module_name> [--config file] [--tags tags.yaml] [--verbose]`

Notes:
- The `--config` default is `<module_name>.yaml` when the module
  definition has `config=True`.

- The `--tags` argument is only added when the module definition has
  `tags=True` (otherwise the module is typically configured with its
  own `tags:` section in `<module_name>.yaml`).

## Where to look in the code

Key wiring points:
- `src/pymscada/main.py`: CLI entry point (selects the module and calls
  `module.start()`).

- `src/pymscada/module_config.py`: module registry and
  `ModuleFactory` (how configuration/tag_info are injected).
  
- `src/pymscada/config.py`: how YAML config files are loaded (including
  environment variable expansion for `${VAR}`).
