# Configuration

This document describes how configuration flows through the `rap-toolkit` pipeline
architecture, from the initial input accepted at construction time through to the
point where individual stage scripts read their own variables at execution time.

---

## Overview

`rap-toolkit` uses three distinct levels of configuration.

| Level | Object | Scope |
|---|---|---|
| Pipeline | `PipelineConfig` | Execution environment, directories, backend, run metadata |
| Global | `GlobalConfig` | Variables shared across stages, with per-stage exclusions |
| Stage | `StageConfig` | Per-stage variables injected at execution time |

Both objects are constructed during `Pipeline` initialisation and are immutable
for the duration of a run. They are kept separate so that pipeline orchestration
concerns (where to write logs, which Python interpreter to use) never bleed into
the domain logic a stage script contains.

---

## Configuration Objects

### `PipelineConfig`

Defined in `rap_toolkit/models.py`. Holds every setting that controls how the runner
behaves.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str \| None` | `None` | Pipeline name. Back-filled from the `Pipeline.name` argument when absent. |
| `backend` | `str` | `"python"` | Execution backend. Currently only `"python"` is implemented. |
| `work_dir` | `Path` | `Path.cwd()` | Working directory used for stage file discovery and subprocess execution. |
| `project_root` | `Path \| None` | `None` → falls back to `work_dir` | Root used to construct `runs/<run_id>` output directories. |
| `log_dir` | `Path` | `Path("logs")` | Directory where `rap-toolkit.log` is written. |
| `data_dir` | `Path` | `Path("data")` | Conventional location for input data. Not enforced by the runner; available to stages via `context.config.data_dir`. |
| `output_dir` | `Path \| None` | `None` | Conventional location for pipeline outputs. Not enforced by the runner; available to stages via `context.config.output_dir`. |
| `allow_subprocess_fallback` | `bool` | `True` | When `True`, stage files without a recognised entrypoint function (`run`, `main`, `execute`) are executed as plain scripts via subprocess. Set to `False` to require entrypoints everywhere. |
| `python_executable` | `str \| None` | `None` → `sys.executable` | Python interpreter used in subprocess fallback mode. |
| `metadata` | `dict[str, Any]` | `{}` | Arbitrary additional values. Any unrecognised key from a raw config mapping is absorbed here rather than raising an error. |

`PipelineConfig` can be constructed directly in code, loaded with
`PipelineConfig.from_any()`, or produced automatically by `Pipeline._resolve_config()`
from a raw mapping or YAML file.

### `StageConfig`

Defined in `rap_toolkit/models.py`. Holds every setting that should be visible to one
specific stage script.

| Attribute | Access | Description |
|---|---|---|
| `name` | `stage_config.name` | The stage name this config belongs to. |
| `_variables` | `.get(key)`, `.require(key)`, `.variables`, `.get_variables(...)` | Arbitrary key/value pairs — the main carrier for stage parameters. All YAML keys not named `datasets` or `metadata` end up here. |
| `datasets` | `stage_config.datasets` | Mapping of dataset identifiers to their properties (e.g. file path, format). |
| `metadata` | `stage_config.metadata` | Supporting metadata about the stage configuration itself (e.g. purpose, owner). |

Accessing variables from stage code:

```python
# Optional: returns default if the key is absent
value = context.stage_config.get("years_to_run")
value = context.stage_config.get("years_to_run", default=2020)

# Mandatory: raises StageConfigurationError if the key is absent
value = context.stage_config.require("target_variable")

# All variables at once
all_vars = context.stage_config.variables  # returns a copy

# Selected subset (raises if any are missing)
subset = context.stage_config.get_variables(["years_to_run", "target_variable"])
```

---

## Entry Points

`Pipeline` is the single public entry point for all configuration. Four class
methods accept configuration in different ways.

```
Pipeline(config=...)          — direct constructor; most flexible
Pipeline.from_config(path)    — preferred when a composite config file defines everything
Pipeline.from_files([...], config=...)  — explicit stage file list with optional config
Pipeline.from_dict({...})     — construct from an in-memory mapping
```

All four funnel into `Pipeline.__init__`, which calls `_resolve_config()` as its
first action. That single call produces the three objects the pipeline needs before
execution can start: `PipelineConfig`, `dict[str, StageConfig]`, and
`list[Stage]`.

---

## Supported Config Input Types

`Pipeline._resolve_config()` and `Pipeline._load_config_mapping()` together
handle the following types for the `config` parameter.

| Type | Behaviour |
|---|---|
| `None` | Constructs a fully-defaulted `PipelineConfig`. No stage configs. |
| `PipelineConfig` instance | Used directly. Stage configuration may optionally be embedded in `config.metadata["stage_configuration"]` (backwards-compatibility path; emits a `StageConfigurationWarning`). |
| `Mapping[str, Any]` | Parsed as a composite or flat config payload (see below). |
| `str` / `Path` | Read and YAML-parsed; the resulting mapping is treated as above. Only `.yaml` / `.yml` files are accepted. |

---

## Config Payload Formats

A raw mapping (or YAML file loaded into a mapping) is classified by
`_split_config_sections()` into one of two shapes.

### Composite format (recommended)

Used when any of the keys `pipeline_variables`, `stage_configuration`, or
`stage_config` are present at the top level. This is the format used by
`examples/pipeline_2/conf.yaml`.

```yaml
pipeline_variables:
  name: "My Pipeline"
  backend: python
  working_dir: "path/to/pipeline"   # alias for work_dir
  project_root: "path/to/pipeline"
  log_dir: "path/to/pipeline/logs"
  data_dir: "path/to/pipeline/data"
  output_dir: "path/to/pipeline/output"
  stages:
    - 0_data_validation:
        location: ""         # empty → scripts/0_data_validation.py
        run: true
        dependencies: []
    - 1_preprocessing:
        location: ""
        run: true
        dependencies:
          - 0_data_validation
  metadata:
    description: "Example pipeline"

stage_configuration:
  0_data_validation:
    years_to_run: 2017
    time_col: "order_date"
    target_variable: "classification"
    datasets:
      orders:
        path: "data/orders.csv"
    metadata:
      purpose: "validate raw inputs"
  1_preprocessing:
    drop_columns: ["id", "notes"]
```

In this format:
- Everything under `pipeline_variables` becomes `PipelineConfig`.
- Everything under `stage_configuration` becomes the `stage_configs` mapping.
- Any key at the top level outside these two sections is **ignored**.

### Flat format

Used when none of the composite section markers are present. The entire mapping
is treated as pipeline config; an optional nested `stage_configuration` or
`stage_config` key within it carries the stage-level config.

```python
Pipeline.from_files(
    ["scripts/0_data_validation.py", "scripts/1_preprocessing.py"],
    config={
        "work_dir": tmp_path,
        "project_root": tmp_path,
        "log_dir": tmp_path / "logs",
        "stage_configuration": {
            "0_data_validation": {
                "years_to_run": 2017,
                "target_variable": "classification",
            }
        },
    },
)
```

---

## Pipeline-Level Parsing Flow

```
config input (any supported type)
          │
          ▼
Pipeline._resolve_config()
          │
          ├─ None ─────────────────────────────► PipelineConfig()  (defaults)
          │
          ├─ PipelineConfig instance ──────────► used as-is
          │   (stage config read from .metadata if present)
          │
          └─ everything else
                    │
                    ▼
          Pipeline._load_config_mapping()
          Normalises input to dict[str, Any]:
            Mapping    → dict(mapping)
            str / Path → yaml.safe_load(file)
                    │
                    ▼
          Pipeline._split_config_sections()
          Detects composite vs flat shape.
          Returns (pipeline_payload, stage_config_payload).
                    │
                    ▼
          Pipeline._normalize_pipeline_payload()
          Maps recognised field aliases:
            working_dir → work_dir  (only when work_dir absent)
          Pops the stages list before handing payload on.
                    │
                    ▼
          PipelineConfig.from_mapping(pipeline_payload)
          Extracts recognised fields; remaining keys
          are absorbed into PipelineConfig.metadata.
```

### Recognised `pipeline_variables` keys

`name`, `backend`, `work_dir` / `working_dir`, `project_root`, `log_dir`,
`data_dir`, `output_dir`, `allow_subprocess_fallback`, `python_executable`,
`metadata`, `stages`.

Any other key is silently absorbed into `PipelineConfig.metadata`. This is
intentional — it allows pipelines to carry arbitrary project metadata — but it
also means a typo in a recognised key name will not raise an error.

---

## Stage Configuration Parsing Flow

```
stage_configuration section (Mapping[str, Any])
          │
          ▼
Pipeline._build_stage_configs()
Iterates every stage name in the mapping.
For each stage:
          │
          ▼
StageConfig.from_mapping(stage_name, stage_payload)
Splits the stage payload into three buckets:
  datasets  → StageConfig.datasets
  metadata  → StageConfig.metadata
  everything else → StageConfig._variables
          │
          ▼
Pipeline.stage_configs  (dict[str, StageConfig])
One entry per configured stage. Stages without an
explicit entry get a default empty StageConfig via
Pipeline._sync_stage_configs().
```

---

## Stage Definition Parsing Flow

When stages are listed under `pipeline_variables.stages` in a composite YAML,
`Pipeline._build_stages_from_config()` converts each entry into a `Stage` object.

```
stages: list (each entry one of several forms)
          │
          ▼
Pipeline._stage_from_config_definition()
Dispatches on the type of the entry:

  Stage instance ─────────────────────────────► returned as-is
  str / Path / callable ──────────────────────► Pipeline._coerce_stage()
  Mapping with name/source/path/callable keys ► Stage.from_dict()
  {stage_name: {...}} single-key mapping ─────► stage_name-keyed form (most common in YAML)
          │
          ▼ (for single-key YAML form)
Extracts from the inner mapping:
  run          → if false, stage is skipped entirely
  location     → source file path (alias: source, path)
  dependencies → list of prerequisite stage names
  entrypoint   → explicit function name (optional)
  metadata     → stage metadata dict
  all others   → merged into metadata
          │
          ▼
Pipeline._resolve_stage_source(stage_name, location, work_dir)
  location is None or "" ─► work_dir / "scripts" / "<stage_name>.py"
  absolute path ──────────► used as-is
  relative, exists ───────► used as-is
  relative, absent ───────► work_dir / location tried first
  neither exists ─────────► raw candidate returned (Stage.validate() will fail later)
          │
          ▼
Stage.from_file(source, name, dependencies, metadata, entrypoint, backend)
Expands the path, verifies it exists, stores resolved absolute path.
```

---

## Config Consumption at Execution Time

`PipelineRunner.run()` is the bridge between the `Pipeline` object (which holds
all parsed configuration) and the actual execution of stage scripts.

```
Pipeline.stage_configs (dict[str, StageConfig])
          │
          │  copied at run start
          ▼
PipelineRunner.run()
  Creates ExecutionContext with:
    config       = pipeline.config        (PipelineConfig)
    stage_configs = dict(pipeline.stage_configs)
          │
          │  for each stage in topological order
          ▼
context.set_active_stage(stage.name)
  Sets ExecutionContext.active_stage_name
          │
          ▼
stage.run(context, executor)
  → PythonStageExecutor.execute(stage, context)
    → loads stage module; calls entrypoint(context)

Within the stage function:
  context.stage_config              # StageConfig for THIS stage
  context.stage_config.get(key)     # optional variable lookup
  context.stage_config.require(key) # mandatory variable lookup
  context.stage_config_for(name)    # any other stage's StageConfig
  context.config                    # PipelineConfig (directories etc.)
  context.run_dir                   # project_root/runs/<run_id>
  context.result_for(name)          # StageResult from an earlier stage
          │
          ▼
context.set_active_stage(None)      # reset after stage finishes
```

### What stages can read

| `context` attribute | Type | Contains |
|---|---|---|
| `context.config` | `PipelineConfig` | Directories, backend, subprocess settings |
| `context.stage_config` | `StageConfig \| None` | This stage's variables, datasets, metadata |
| `context.stage_config_for(name)` | `StageConfig \| None` | Any stage's config by name |
| `context.stage_configs` | `dict[str, StageConfig]` | All stage configs |
| `context.run_id` | `str` | Unique run identifier |
| `context.run_dir` | `Path` | `project_root / "runs" / run_id` |
| `context.result_for(name)` | `StageResult \| None` | Output of a previously run stage |
| `context.stage_outputs` | `dict[str, Any]` | All outputs from stages run so far |

---

## Validation Model

Configuration parsing and execution validation are intentionally separate phases.

| Phase | When | What is checked |
|---|---|---|
| **Parse** | `Pipeline.__init__` | Type validity; YAML syntax; that stage source files exist (`Stage.from_file` calls `path.exists()`); `StageConfig` is built for each configured stage name |
| **Validate** | `Pipeline.validate()`, called automatically at the start of every `Pipeline.run()` | Stage source files still exist; dependency graph is acyclic and complete; every name in `stage_configuration` matches a real stage |

Calling `pipeline.validate()` explicitly before `pipeline.run()` is safe and
useful in test suites or CI pipelines.

---

## Manifest Serialisation

When a pipeline run completes, `Pipeline._manifest_parameters()` serialises the
full configuration state into `RunManifest.parameters`. This includes the
`PipelineConfig` fields and a nested `stage_configuration` block containing every
`StageConfig.to_dict()`. This means the exact parameters used for any given run
are reproducible from the manifest alone.

---

## Known Pitfalls

### 1 — Relative paths are resolved against the process working directory

`work_dir`, `log_dir`, `data_dir`, and `output_dir` are stored as `Path` objects
constructed directly from whatever string is in the config. A value like
`"examples/pipeline_2"` is therefore resolved relative to wherever Python is
running when the pipeline is constructed, not relative to the YAML file's
location.

**Mitigation**: Use absolute paths in YAML configs, or construct `PipelineConfig`
in Python code where you can use `Path(__file__).parent` to anchor paths relative
to the config module.

### 2 — Unrecognised `pipeline_variables` keys are silently absorbed into metadata

`PipelineConfig.from_mapping()` pops every recognised field and then calls
`metadata.update(remaining_payload)`. A typo such as `log_dirs:` instead of
`log_dir:` will not raise; instead the default `Path("logs")` will be used and
the misspelled key will appear in `pipeline.config.metadata`.

**Mitigation**: When debugging unexpected defaults, inspect
`pipeline.config.metadata` to see which keys were not recognised.

### 3 — Stage configs are not cross-checked until `validate()` runs

`Pipeline.__init__` does not validate that every stage named in
`stage_configuration` has a matching stage in the `stages` list. That check runs
in `_validate_stage_configs()`, which is called inside `validate()`, which is
called at the start of `run()`. A name mismatch (e.g., a renamed stage script)
will therefore only surface when the pipeline is actually executed.

**Mitigation**: Call `pipeline.validate()` explicitly after construction in
environments where you want early failure.

### 4 — Keys outside `pipeline_variables` in a composite YAML are ignored

When the composite format is detected, `_split_config_sections()` reads only
`pipeline_variables` and `stage_configuration` / `stage_config`. Any other top-level
key in the YAML file is silently discarded.

```yaml
pipeline_variables:
  name: "my-pipeline"
work_dir: "/path/that/will/be/ignored"   # ← this key is outside pipeline_variables
stage_configuration: ...
```

### 5 — `allow_subprocess_fallback` as a quoted YAML string

YAML `false` (unquoted) parses to Python `False`. The quoted string `"false"` 
parses to Python `"false"`. Because `PipelineConfig` now explicitly checks for 
string values and maps common representations to booleans, a quoted `"false"` 
will emit a `UserWarning` and be interpreted as `False`. However, to avoid any 
ambiguity, use unquoted YAML booleans:

```yaml
allow_subprocess_fallback: false   # correct — unquoted YAML boolean
allow_subprocess_fallback: "false" # warns — will be treated as False
```

### 6 — Passing a composite YAML to `PipelineConfig.from_file()` directly

`PipelineConfig.from_file()` (and `PipelineConfig.from_any()` when given a path)
does not understand the `pipeline_variables` / `stage_configuration` structure.
If a composite YAML is loaded this way, `pipeline_variables` and
`stage_configuration` are treated as unknown keys and absorbed into
`PipelineConfig.metadata`. The resulting `PipelineConfig` will have default
values for all fields.

**Mitigation**: Always pass composite YAML files to `Pipeline.from_config()` or
as the `config=` argument to `Pipeline(...)`. Reserve `PipelineConfig.from_file()`
for flat, pipeline-only YAML files.

### 7 — Stage source resolution for relative non-existent paths

`_resolve_stage_source()` tries the literal path, then `work_dir / path`. If
neither exists it returns the raw candidate. `Stage.from_file()` then calls
`path.exists()` and raises `StageConfigurationError`. This means a typo in a
`location` field is caught at construction time, not silently deferred, but the
error message will point to the stage file rather than the config key.

### 8 — Unknown stage definition keys are absorbed into `Stage.metadata`

In `_stage_from_config_definition()`, any key under a stage entry that is not
`run`, `location` / `source` / `path`, `dependencies`, `entrypoint`, or
`metadata` is merged into `Stage.metadata`. This is intentional — it lets you
attach arbitrary properties to a stage definition (e.g. `owner: analytics`) —
but it also means a misspelled reserved key such as `dependancies` will silently
appear in metadata rather than being recognised as a dependency list.

---

## Extensibility

Stage configuration scales linearly: `_build_stage_configs()` iterates every
key in the `stage_configuration` mapping and constructs one `StageConfig` per
entry. Adding a new stage to the pipeline requires:

1. Adding the stage entry to `pipeline_variables.stages` in the YAML (or passing
   it to `from_files`).
2. Adding the corresponding entry to `stage_configuration` in the YAML (or
   passing it in the flat config mapping).

No other changes are needed. `Pipeline._sync_stage_configs()` ensures that every
stage that does not have an explicit entry still receives an empty `StageConfig`
so that `context.stage_config` is never `None` during execution.
