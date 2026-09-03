from pathlib import Path
from textwrap import dedent

import pytest

from onsrap.errors import StageDependencyError
from onsrap.file_system_setup import FileSystemFactory, FileSystemSetUp
from onsrap.stage import Stage, StageConfigurationError, _normalize_dependencies


class TestNormalizeDependencies:
    def test_normalize_dependencies_none(self) -> None:
        """
        Tests that None values return empty tuple.
        """
        assert _normalize_dependencies(None) == ()

    def test_normalize_dependencies_str(self) -> None:
        """
        Tests single string and list of string values including
        where whitespace appears before and after main text body
        """
        assert _normalize_dependencies("stage_1.py") == ("stage_1.py",)
        assert _normalize_dependencies("   stage_1.py") == ("stage_1.py",)
        assert _normalize_dependencies(
            ["Stage_1.py", "   Stage_2.py", "Stage_3.py   "]
        ) == ("Stage_1.py", "Stage_2.py", "Stage_3.py")

    def test_normalize_dependencies_dedupe(self) -> None:
        """
        Tests that duplicate values are removed from the normalized dependencies
        whilst preserving first seen order.
        """
        assert _normalize_dependencies(["Stage_1.py", "Stage_2.py", "Stage_1.py"]) == (
            "Stage_1.py",
            "Stage_2.py",
        )

        assert _normalize_dependencies(
            ["Stage_2.py", "Stage_1.py", "Stage_2.py", "Stage_1.py"]
        ) == ("Stage_2.py", "Stage_1.py")

    def test_normalize_dependencies_whitespace_handling(self) -> None:
        """
        Tests that whitespace only or blank dependency values are removed from
        the normalised dependencies.
        """
        assert _normalize_dependencies(["   ", ""]) == ()

    def test_normalize_dependencies_type_check(self) -> None:
        """
        Tests that normalize_dependencies works with other iterables such as tuples
        and sets, and raises a TypeError for non-iterable types.
        """
        assert _normalize_dependencies(("Stage_1.py", "Stage_2.py")) == (
            "Stage_1.py",
            "Stage_2.py",
        )

        result = _normalize_dependencies({"Stage_1.py", "Stage_2.py"})
        assert set(result) == {"Stage_1.py", "Stage_2.py"}

        with pytest.raises(TypeError):
            _normalize_dependencies(11)

    def test_normalize_dependencies_mixed_types(self) -> None:
        """
        Tests that normalize_dependencies stringifies non-string types in a
        dependency iterable.
        """
        assert _normalize_dependencies(["Stage_1.py", 11, "Stage_2.py"]) == (
            "Stage_1.py",
            "11",
            "Stage_2.py",
        )


@pytest.fixture
def example_function():
    """
    Test function to pass as a callable stage for stage testing.
    """
    return example_function


@pytest.fixture
def stage_test(example_function) -> Stage:
    """
    Stage object for testing Stage class methods and construction.
    """
    return Stage("callable_stage", example_function, ["stage_1"], {"info": "example"})


class TestStage:
    def test_stage_creation_callable(self, stage_test, example_function) -> None:
        """
        Tests that attributes have been appropriately assigned to Stage class.

        Parameter
        ---------
        stage_test : Stage
            A ``Stage`` object created with a callable source for testing.
        """
        assert stage_test.name == "callable_stage"
        assert stage_test.source == example_function
        assert stage_test.dependencies == ("stage_1",)
        assert stage_test.metadata == {"info": "example"}
        assert stage_test.entrypoint is None
        assert stage_test.backend == "python"

    def test_stage_name_error(self, example_function) -> None:
        """
        Tests that a StageConfigurationError is raised if the name is left blank
        in a Stage class instance. This also includes whitespace only names.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.

        Raises
        ------
        ``StageConfigurationError``
            If the name is left blank or entirely whitespace in a ``Stage`` class
            instance.
        """
        with pytest.raises(StageConfigurationError):
            Stage("", example_function, ["stage_1"], {"info": "example"})

        with pytest.raises(StageConfigurationError):
            Stage("      ", example_function, ["stage_1"], {"info": "example"})

    def test_stage_source_type(self) -> None:
        """
        Tests that a non-valid source type returns a StageConfigurationError.

        Raises
        ------
        ``TypeError``
            If source is not a callable and cannot be turned into a FileSystemSetUp
            instance.
        """
        with pytest.raises(TypeError):
            Stage("callable_stage", 11, ["stage_1"], {"info": "example"})

    def test_stage_backend(self, example_function) -> None:
        """
        Tests that backend can be any string, None, and corrects for whitespace.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        stage_diff = Stage(
            "callable_stage",
            example_function,
            ["stage_1"],
            {"info": "example"},
            backend="java",
        )
        stage = Stage(
            "callable_stage",
            example_function,
            ["stage_1"],
            {"info": "example"},
            backend="",
        )
        stage_white_space = Stage(
            "callable_stage",
            example_function,
            ["stage_1"],
            {"info": "example"},
            backend="python   ",
        )
        assert stage_diff.backend == "java"
        assert stage.backend == "python"
        assert stage_white_space.backend == "python"

    def test_stage_backend_irregular_values(self, example_function) -> None:
        """
        Tests that backend defaults with a None or whitespace only string to "python"
        and converts any non-string type (other than None) to a string.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        stage_none = Stage(
            "callable_stage",
            example_function,
            ["stage_1"],
            {"info": "example"},
            backend=None,
        )

        stage_blank = Stage(
            "callable_stage",
            example_function,
            ["stage_1"],
            {"info": "example"},
            backend="   ",
        )
        stage_non_string = Stage(
            "callable_stage",
            example_function,
            ["stage_1"],
            {"info": "example"},
            backend=11,
        )

        assert stage_none.backend == "python"
        assert stage_blank.backend == "python"
        assert stage_non_string.backend == "11"

    def test_stage_constructor_expands_string_source_with_home(
        self, monkeypatch, tmp_path
    ):
        """
        Check that a string source is converted to a Path and expanded with
        expanduser(). This uses fake environmental variables to make sure that the
        tests are not dependent on the actual user's home directory.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for temporary modification of environment
            variables and other attributes during testing.
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        """
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))

        stage = Stage(
            name="string_source_stage",
            source="~/scripts/my_stage.py",
            dependencies=[],
            metadata={},
        )

        expected = FileSystemSetUp.file_system_setup_factory(
            fake_home / "scripts" / "my_stage.py", path_type="file"
        )
        assert isinstance(stage.source, FileSystemSetUp)
        assert stage.source == expected

    def test_stage_constructor_expands_path_source_with_home(
        self, monkeypatch, tmp_path
    ):
        """
        Check that a Path source is expanded with expanduser(). This uses fake
        environmental variables to make sure that the tests are not dependent on the
        actual user's home directory.

        Parameters
        ----------
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for temporary modification of environment
            variables and other attributes during testing.
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        """
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))

        stage = Stage(
            name="path_source_stage",
            source=Path("~/scripts/my_stage.py"),
            dependencies=[],
            metadata={},
        )

        expected = FileSystemSetUp.file_system_setup_factory(
            fake_home / "scripts" / "my_stage.py", path_type="file"
        )
        assert isinstance(stage.source, FileSystemSetUp)
        assert stage.source == expected

    def test_normalise_dependencies_within_stage_init(self, example_function) -> None:
        """
        Thin smoke test to check that _normalize_dependencies is called within the Stage
        post_init method.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        stage = Stage(
            name="test_stage",
            source=example_function,
            dependencies=["dep1", "dep2", "dep1", "   dep3   ", "", "   "],
            metadata={},
        )
        assert stage.dependencies == ("dep1", "dep2", "dep3")

    def test_source_path(
        self, stage_test, tmp_path, example_function, temp_script
    ) -> None:
        """
        Tests whether source_path detects a path vs other valid and invalid source
        types.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        script, _ = temp_script(filename="temp_script.py")
        stage_test.source = script
        assert stage_test.source_path == script.create_path()
        stage_test.source = 11
        assert stage_test.source_path is None
        stage_test.source = FileSystemSetUp.file_system_setup_factory(
            "not a file path", path_type="file"
        )
        assert stage_test.source_path is None
        stage_test.source = example_function
        assert stage_test.source_path is None

    def test_source_label(self, stage_test, tmp_path, example_function) -> None:
        """
        Tests that source_label is created if the source is a Path or a callable
        and is None if it is another type. This also checks that if the callable
        has no name attribute, the stage name is used as the source label.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        stage_test.source = tmp_path / "fake_file.py"
        temp_path_str = str(tmp_path / "fake_file.py")
        assert stage_test.source_label == temp_path_str

        stage_test.source = example_function
        assert stage_test.source_label == "tests.test_stage.example_function"

        stage_test.source = 11
        assert stage_test.source_label is None

        class NoName:
            def __call__(self):
                pass

        stage_test.source = NoName()
        assert stage_test.source_label == f"tests.test_stage.{stage_test.name}"

    def test_metadata_copy_safely(self) -> None:
        """
        Checks that if the original metadata dictionary is modified after the Stage
        instance is created, the Stage instance's metadata remains unchanged.
        """
        # TODO: do we want this to be how it works? Or would the user assume that if
        # they modify the original dict, it modifies the Stage instance.
        original_metadata = {"info": "example"}
        stage = Stage(
            name="callable_stage",
            source=lambda: None,
            dependencies=[],
            metadata=original_metadata,
        )
        original_metadata["info"] = "modified"
        assert stage.metadata["info"] == "example"

    def test_repr_function(self) -> None:
        """
        Tests that the __repr__ function returns a string representation of the Stage
        instance with the correct attributes.
        """
        stage = Stage(
            name="callable_stage",
            source=lambda: None,
            dependencies=["stage_1"],
            metadata={"info": "example"},
            entrypoint="main",
            backend="python",
        )
        expected_repr = (
            "Stage(name=callable_stage, "
            "source=tests.test_stage.<lambda>, "
            "dependencies=('stage_1',), "
            "metadata={'info': 'example'}, "
            "entrypoint=main, "
            "backend=python)"
        )
        assert repr(stage) == expected_repr

    def test_str_function(self) -> None:
        """
        Tests that the __str__ function returns a string representation of the Stage
        instance with the correct attributes.
        """
        stage = Stage(
            name="callable_stage",
            source=lambda: None,
            dependencies=["stage_1"],
            metadata={"info": "example"},
            entrypoint="main",
            backend="python",
        )
        expected_str = (
            "    Name: callable_stage\n"
            "    Source: tests.test_stage.<lambda> \n"
            "    Dependencies: ('stage_1',)\n"
            "    Metadata: {'info': 'example'} \n"
            "    Entrypoint: main \n"
            "    Backend: python"
        )
        assert str(stage) == expected_str


class TestValidateStage:
    def test_validate(self, stage_test, tmp_path) -> None:
        """
        Tests whether an error is raised if the source file isn't suitable.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.

        Raises
        ------
        ``StageConfigurationError``
            If the source is not a valid callable or file path in a ``Stage`` class
            instance. In this instance, it raises if the source is None, an empty
            string, or a Path object that is not a file.
        """
        stage_test.source = None
        with pytest.raises(StageConfigurationError):
            stage_test.validate()
        not_file_path = tmp_path
        stage_test.source = not_file_path
        with pytest.raises(StageConfigurationError):
            stage_test.validate()
        stage_test.source = ""
        with pytest.raises(StageConfigurationError):
            stage_test.validate()

    def test_validate_successes(
        self, stage_test, example_function, temp_script
    ) -> None:
        """
        Tests that validate successfully approves of callables and file paths as
        sources for a stage instance.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        ``temp_script`` : callable
            A fixture factory that creates temporary Python scripts.
        """
        stage_test.source = example_function
        assert stage_test.validate() is None

        setup, fs_setup = temp_script(filename="valid_script.py")

        stage_test.source = FileSystemSetUp.file_system_setup_factory(
            setup, path_type="file"
        )
        assert stage_test.validate() is None


class TestWithDependencies:
    def test_with_dependencies_list(self, stage_test) -> None:
        """
        Tests adding different types of dependencies when the original dependency is
        a list. Also checks that the original stage_test instance is not modified when
        with_dependencies is called.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        """
        new_deps = ["stage2", "stage3"]
        new_deps_blank = []
        original_deps = stage_test.dependencies

        stage_test_list = stage_test.with_dependencies(new_deps)
        stage_test_blank = stage_test.with_dependencies(new_deps_blank)
        assert stage_test_list.dependencies == ("stage_1", "stage2", "stage3")
        assert stage_test_blank.dependencies == ("stage_1",)
        stage_test_2 = stage_test.with_dependencies("stage2", "stage3")
        assert stage_test_2.dependencies == ("stage_1", "stage2", "stage3")

        stage_test.with_dependencies("stage2", "stage3")
        assert stage_test.dependencies == original_deps

    def test_with_dependencies_errors(self, stage_test) -> None:
        """
        Tests that a StageDependencyError is raised if a nested list is
        provided in dependencies.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        """
        with pytest.raises(StageDependencyError):
            stage_test.with_dependencies(["stage2", ["nested_stage"]])

    def test_with_dependencies_list_positional_args(self, stage_test) -> None:
        """
        Tests that with_dependencies can accept a list and positional arguments in the
        same call and combine them into a single normalized dependencies tuple.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        """
        new_deps = ["stage2", "stage3"]
        stage_test_combined = stage_test.with_dependencies(new_deps, "stage4")
        assert stage_test_combined.dependencies == (
            "stage_1",
            "stage2",
            "stage3",
            "stage4",
        )

    def test_with_dependencies_duplicates(self, stage_test) -> None:
        """
        Tests that when the same dependency is added through with_dependencies,
        it is not duplicated in the dependencies tuple of the new Stage instance.

        Caution that this only deduplicates due to Stage post_init calling
        _normalize_dependencies however if that moves,
        test_normalise_dependencies_within_stage_init will capture the issue.

        Parameters
        ----------
        ``stage_test`` : Stage
            A ``Stage`` object created with a callable source for testing.
        """
        new_stage = stage_test.with_dependencies(["stage_1"])
        assert new_stage.dependencies == ("stage_1",)


# TEST NOT CODED FOR RUN() AS ASSUMED THIS IS COVERED IN PIPELINE_ARCHITECTURE TEST


@pytest.fixture
def temp_script(tmp_path):
    """
    Fixture factory that creates temporary Python scripts.

    Usage:
        script = temp_script("def main(): pass")
        script = temp_script("def process(): return 42", "processor.py")
    """

    def _create_script(content="def main(): pass\n", filename="temp_script.py"):
        script = FileSystemSetUp.file_system_setup_factory(
            tmp_path / filename, path_type="file"
        )
        script_fs = FileSystemFactory.create(script)
        script_fs.write_text(content, encoding="utf-8")
        return script, script_fs

    return _create_script


class TestStageFactories:
    """
    Parent class for tests which create Stage class instances from different methods.
    """


class TestStageFromFile(TestStageFactories):
    """
    Class which tests the creation of Stage class instances from a file path.
    """

    def test_stage_instance_from_file(self, temp_script) -> None:
        """
        Tests that a Stage instance is created from a filepath where name is either
        default value from file stem or a user defined name.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        """
        test_stage, test_stage_fs = temp_script(
            dedent(
                """
                def main():
                    variable = "Hello world"
                    return variable
                """
            ).strip()
            + "\n",
            "test_stage.py",
        )

        assert Stage.from_file(test_stage, entrypoint="main") == Stage(
            "test_stage.py",
            test_stage_fs.resolve(type="data"),
            (),
            {},
            "main",
            "python",
        )

        assert Stage.from_file(test_stage, name="Stage_1", entrypoint="main") == Stage(
            "Stage_1", test_stage_fs.resolve(type="data"), (), {}, "main", "python"
        )

    def test_stage_from_files_error(self, tmp_path: Path) -> None:
        """
        Tests that if the file doesn't exist, a StageConfigurationError is raised.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.

        Raises
        ------
        ``StageConfigurationError``
            If the source file doesn't exist when attempting to create a
            ``Stage`` instance
        """
        source_file = FileSystemSetUp.file_system_setup_factory(
            tmp_path / "not_an_actual_file.py", path_type="file"
        )
        with pytest.raises(StageConfigurationError):
            Stage.from_file(source_file)

    def test_from_file_resolves_relative_to_absolute(self, temp_script, monkeypatch):
        """
        Tests that a relative path passed to from_file is resolved to a
        FileSystemSetUp instance on the Stage source attribute. Checks that
        this FileSystemSetUp can be resolved to an absolute path.

        Parameters
        ----------
        ``temp_script`` : callable
            A fixture factory that creates temporary Python scripts.
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for temporary modification of environment
            variables and other attributes during testing.
        """
        script, script_fs = temp_script()

        monkeypatch.chdir(script_fs.parent(path_type="data"))

        stage = Stage.from_file(script)

        resolved = script_fs.resolve(type="data")

        assert isinstance(stage.source, FileSystemSetUp)
        assert resolved is not None

    def test_from_file_expands_source_path(self, tmp_path, monkeypatch):
        """
        Tests that a path with a tilde (~) is expanded to the user's home directory
        when passed to from_file. Uses monkeypatch to set a fake home directory for
        testing purposes.

        Parameters
        ----------
        ``tmp_path`` : Path
            A temporary path provided by pytest for testing file creation and
            manipulation.
        ``monkeypatch`` : pytest.MonkeyPatch
            A pytest fixture that allows for temporary modification of environment
            variables and other attributes during testing.
        """
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))

        script = fake_home / "scripts" / "my_stage.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("def main(): pass\n", encoding="utf-8")

        tilde_path = "~/scripts/my_stage.py"

        stage = Stage.from_file(
            FileSystemSetUp.file_system_setup_factory(tilde_path, path_type="file")
        )

        expected = fake_home / "scripts" / "my_stage.py"
        assert stage.source == FileSystemSetUp.file_system_setup_factory(
            expected, path_type="file"
        )


class TestStageFromCallable(TestStageFactories):
    """
    Class which tests the creation of Stage class instances from a callable object.
    """

    def test_stage_from_callable_name(self, example_function) -> None:
        """
        Tests that a stage name is extracted from a callable object stage.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        test = Stage.from_callable(example_function)
        assert test.name == "example_function"

    def test_from_callable_fallback_name(self):
        """
        Tests that a fallback name is assigned to a stage instance if the callable
        object does not have a name attribute.
        """

        class NoName:
            def __call__(self):
                pass

        stage = Stage.from_callable(NoName())
        assert stage.name == "stage"

    def test_from_callable_explicit_name(self, example_function) -> None:
        """
        Tests that an explicit name is assigned to a stage instance if provided.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        test = Stage.from_callable(example_function, name="explicit_name")
        assert test.name == "explicit_name"


class TestStageFromDict(TestStageFactories):
    """
    Class which tests the creation of Stage class instances from a dictionary.
    """

    def test_from_dict_callable_sources(self, example_function) -> None:
        """
        Tests that callable sources are correctly used to create a stage instance
        from a dictionary regardless of whether the key is source or callable.
        Also validates that the name is correctly assigned from the dictionary or
        derived from the callable.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """

        data = {"name": "test_Stage", "callable": example_function}
        stage = Stage.from_dict(data)
        assert stage.source == example_function
        assert stage.name == "test_Stage"

        data = {"source": example_function}
        stage = Stage.from_dict(data)
        assert stage.source == example_function
        assert stage.name == "example_function"

    def test_from_dict_aliases(self, temp_script) -> None:
        """
        Tests that a stage instance is created from a dictionary item with aliases
        source and path as source options.

        Parameters
        ----------
        ``temp_script`` : callable
            A fixture factory that creates temporary Python scripts.
        """
        script, script_fs = temp_script(
            dedent(
                """
                def main():
                    variable = "Hello world"
                    return variable
                """
            ).strip()
            + "\n",
            "test_stage.py",
        )

        data = {
            "name": "test_Stage",
            "source": script,
            "entrypoint": "main",
        }

        data_2 = {
            "name": "test_Stage2",
            "path": script,
            "entrypoint": "main",
        }
        stage = Stage.from_dict(data)
        stage_2 = Stage.from_dict(data_2)
        assert stage.source == FileSystemSetUp.file_system_setup_factory(
            script, path_type="file"
        )
        assert stage.name == "test_Stage"
        assert stage_2.source == FileSystemSetUp.file_system_setup_factory(
            script, path_type="file"
        )
        assert stage_2.name == "test_Stage2"

    def test_from_dict_errors(self) -> None:
        """
        Tests that a StageConfigurationError is raised if the dictionary does not
        contain a valid source or callable key.

        Raises
        ------
        ``StageConfigurationError``
            If the dictionary does not contain a valid source or callable key.
        """
        data = {"name": "test_Stage"}
        with pytest.raises(StageConfigurationError):
            Stage.from_dict(data)

    def test_all_keys_from_dict_in_stage(self, example_function) -> None:
        """
        Checks that from_dict does not change the originally parsed dictionary so
        that if the dictionary is needed later, it is not permanently changed when
        creating a stage instance from it.

        Parameters
        ----------
        ``example_function`` : callable
            A callable function to pass as a source for a ``Stage`` class instance.
        """
        data = {
            "name": "test_Stage",
            "source": example_function,
            "dependencies": ["dep1", "dep2"],
            "metadata": {"info": "example"},
            "entrypoint": "main",
            "backend": "python",
        }
        original = dict(data)
        Stage.from_dict(data)
        assert original == data
