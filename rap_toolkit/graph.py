from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .errors import DependencyCycleError, DuplicateStageError, MissingDependencyError
from .stage import Stage


@dataclass
class StageGraph:
    """
    Represents an order to run stages.

    Holds an order that stages need to run in based on dependencies and logic.

    Parameters
    ----------
    ``stages`` : list of ``Stage`` class items
    """

    stages: list[Stage] = field(default_factory=list)

    @classmethod
    def from_stages(cls, stages: Iterable[Stage]) -> StageGraph:
        """
        This is the primary constructor for StageGraph, which performs validation and normalization of the stage list.

        Parameters
        ----------
        ``stages`` : Iterable of ``Stage`` class instances

        Returns
        -------
        The ``stages`` parameter as a list.
        """
        return cls(list(stages))

    def validate(self) -> None:
        """
        Validate the stage graph for issues such as duplicate stage names, missing dependencies, and cycles.

        Raises
        ------
        ``DuplicateStageError``
            If the stage name appears multiple times in the stage list.
        ``MissingDependencyError``
            If there are unknown dependencies.
        """

        # Check for duplicate stages
        names = [stage.name for stage in self.stages]
        seen = set()
        duplicates = []
        for name in names:
            if name in seen and name not in duplicates:
                duplicates.append(name)
            seen.add(name)

        if duplicates:
            raise DuplicateStageError(
                "Duplicate stage names are not allowed: {0}".format(
                    ", ".join(sorted(duplicates))
                )
            )

        # Check for defined dependencies which are not present in the stage list
        stage_names = set(names)
        missing = []
        for stage in self.stages:
            for dependency in stage.dependencies:
                if dependency not in stage_names:
                    missing.append("{0} -> {1}".format(stage.name, dependency))

        if missing:
            raise MissingDependencyError(
                "Unknown stage dependencies: {0}".format(", ".join(missing))
            )

        self.topological_order()

    def topological_order(self) -> list[Stage]:
        """
        Return the stages in an order that respects their dependencies.

        In graph terms, this is a *topological sort*: if stage ``B`` depends on
        stage ``A``, then ``A`` will always appear before ``B`` in the returned
        list. The word "topological" here does not refer to geographic maps or
        terrain; it means we are arranging nodes in a dependency-safe order.

        The implementation works by repeatedly selecting stages that currently
        have no unmet dependencies. Those stages are "ready" to run because
        nothing else needs to happen first. After a ready stage is placed in the
        output order, the algorithm removes it from the dependency lists of the
        stages that depend on it. That may free up more stages, which are then
        added to the ready list.

        Returns
        -------
        A list of stages ordered in the way that they need to be run through the
        pipeline.

        Raises
        ------
        ``DependencyCycleError``
            If the algorithm cannot place every stage, the graph contains either a
            cycle or a dependency that could not be resolved.
        """
        stage_by_name = {stage.name: stage for stage in self.stages}
        incoming: dict[str, set[str]] = {
            stage.name: set(stage.dependencies) for stage in self.stages
        }
        dependents: dict[str, set[str]] = {stage.name: set() for stage in self.stages}

        for stage in self.stages:
            for dependency in stage.dependencies:
                if dependency not in dependents:
                    raise MissingDependencyError(
                        f"Unknown stage dependency: {stage.name} -> {dependency}"
                    )
                dependents[dependency].add(stage.name)

        original_order = [stage.name for stage in self.stages]
        ready = [name for name in original_order if not incoming[name]]
        ordered: list[str] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)

            for dependent in dependents[current]:
                incoming[dependent].discard(current)

            for name in original_order:
                if name in ordered or name in ready:
                    continue
                if not incoming[name]:
                    ready.append(name)

        if len(ordered) != len(self.stages):
            unresolved = [name for name in original_order if name not in ordered]
            raise DependencyCycleError(
                "Stage graph contains a cycle or unresolved dependencies: {0}".format(
                    ", ".join(unresolved)
                )
            )

        return [stage_by_name[name] for name in ordered]
