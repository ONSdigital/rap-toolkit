from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp

from .errors import StageConfigurationError, StageLoadError
from .models import PipelineRun

PREFERRED_ENTRYPOINTS = ("run", "main", "execute")


def discover_python_entrypoint(
    path: FileSystemSetUp,
) -> str | None:
    """
    Inspect a Python stage file and return the preferred callable entrypoint name.

    onsrap stages are intentionally lightweight: a stage can be a plain Python
    file, but the execution layer still needs a concrete function to call when
    one is available. This helper does a shallow AST scan for the project's
    preferred entrypoints, ``run``, ``main``, and ``execute``, without importing
    the module. That keeps discovery fast and avoids running stage code just to
    learn how it should be invoked.

    Parameters
    ----------
    ``path`` : FileSystemSetUp
        File system setup for the stage being run.

    Returns
    -------
    String item containing the name of the ``PREFERRED_ENTRYPOINTS`` item relevant
    for the stages.
    ``None`` when the file exists but does not define a preferred
    callable, which signals to the executor that it should treat the file as a
    script-style stage instead.

    Raises
    ------
    ``StageConfigurationError``
        If the file path requested for the ``Stage`` does not exist.
    """

    file_system = FileSystemFactory.create(path)
    if not file_system.exists(type="data"):
        raise StageConfigurationError(
            "Stage source file does not exist in the data path: {0}".format(file_system)
        )

    try:
        tree = ast.parse(
            file_system.read_text(encoding="utf-8"), filename=str(path.create_uri())
        )
    except (OSError, SyntaxError) as exc:
        raise StageConfigurationError(
            "Unable to inspect Python stage file {0}: {1}".format(file_system, exc)
        ) from exc

    defined_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for candidate in PREFERRED_ENTRYPOINTS:
        if candidate in defined_functions:
            return candidate

    return None


def load_python_callable(path: FileSystemSetUp, entrypoint: str) -> Any:
    """
    Import a stage module and return the named callable from it.

    This is the bridge from the declarative stage model to execution. Once the
    pipeline has chosen a stage source and entrypoint, the runtime uses this
    helper to import the module exactly once and retrieve the function that will
    receive the execution context. It is kept separate from module loading so
    the executor can reuse the same import path for multiple runtime strategies.

    Parameters
    ----------
    ``path`` : FileSystemSetUp
        The file system setup for the stage being run.
    ``entrypoint`` : str
        The name of the entrypoint function defined in the stage script.

    Raises
    ------
    ``StageConfigurationError``
    If the chosen entrypoint does not exist or is not callable, because that means
    the stage definition and the executable surface no longer agree.

    Returns
    -------
    ``target``
        The ``entrypoint`` attribute of the module called to run the stage.
    """
    module = load_python_module(path)
    target = getattr(module, entrypoint, None)
    if not callable(target):
        raise StageConfigurationError(
            "Entry point '{0}' was not callable in '{1}'.".format(entrypoint, path)
        )

    return target


def load_python_module(path: FileSystemSetUp) -> ModuleType:
    """
    Import a Python stage file as an isolated module object.

    The architecture treats stage files as user-owned execution units, not as
    part of the package's own import graph. To preserve that boundary, this
    helper loads the file under a generated module name instead of importing it
    by package path. That lets onsrap execute local stage code without requiring
    the user to restructure it into an installed module.

    The generated name is derived from the file path so repeated loads of the
    same stage remain stable during a run, while still avoiding collisions with
    other Python modules.

    Parameters
    ----------
    ``path`` : str
        The path for the stage.

    Returns
    -------
    ``module``
        The set of code being run for the stage.

    Raises
    ------
    ``StageLoadError``
        If the file is unable to be imported so callers can report a stage-specific
        problem rather than a raw import exception.
    """
    file_system = FileSystemFactory.create(path)
    if path.file_name is None:
        raise StageLoadError(
            "No file name has been provided for the stage: {0}".format(file_system)
        )
    if not file_system.exists(type="data"):
        raise StageLoadError(
            "Stage source file does not exist in the data path: {0}".format(file_system)
        )

    module_name = "onsrap_stage_{0}_{1}".format(
        Path(path.file_name).stem,
        hashlib.sha256(
            str(file_system.resolve(type="data")).encode("utf-8")
        ).hexdigest()[:12],
    )
    spec = file_system.spec_from_file_location(module_name)
    if spec is None or spec.loader is None:
        raise StageLoadError(
            "Unable to create a module spec for {0}".format(file_system)
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise StageLoadError(
            "Failed to import Python stage file {0}: {1}".format(file_system, exc)
        ) from exc

    return module


def load_historical_run(run_dir: Path) -> PipelineRun:
    """
    Load a previously executed pipeline run from a YAML file.

    Returns
    -------
    ``PipelineRun``
        An instance of ``PipelineRun`` representing the historical run.
    """
    import glob

    files = glob.glob(str(run_dir / "pipeline_attributes_for_*.yaml"))
    if not files:
        raise StageLoadError(
            "Historical run file does not exist in: {0}".format(run_dir)
        )
    file_path = Path(files[0])

    import yaml

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return PipelineRun._pipeline_run_from_dict(data)
