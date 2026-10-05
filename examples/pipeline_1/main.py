from __future__ import annotations

from pathlib import Path

from rap_toolkit import Pipeline, PipelineConfig

PIPELINE_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
DATA_DIR = PIPELINE_ROOT / "data"
LOG_DIR = PIPELINE_ROOT / "logs"


def build_pipeline() -> Pipeline:
    stage_files = [
        SCRIPTS_DIR / "0_data_validation.py",
        SCRIPTS_DIR / "1_preprocessing.py",
        SCRIPTS_DIR / "2_reporting.py",
    ]

    dependencies = {
        "1_preprocessing": ("0_data_validation",),
        "2_reporting": ("1_preprocessing",),
    }

    config = PipelineConfig(
        name="pipeline_1",
        backend="python",
        work_dir=PIPELINE_ROOT,
        project_root=PIPELINE_ROOT,
        output_dir=PIPELINE_ROOT,
        data_dir=DATA_DIR,
        log_dir=LOG_DIR,
        metadata={
            "example": "retail-orders",
            "description": "Validate, clean, and summarize a small orders dataset.",
        },
    )

    return Pipeline.from_files(
        stage_files,
        name="pipeline_1",
        backend="python",
        config=config,
        dependencies=dependencies,
    )


def main() -> None:
    run = build_pipeline().run()
    report = run.manifest.outputs["2_reporting"]

    print(
        f"Pipeline '{run.manifest.rap_name}' completed with {len(run.stage_results)} stages."
    )
    print(f"Summary report written to: {report['report_path']}")
    print(f"Cleaned data written to: {report['clean_path']}")


if __name__ == "__main__":
    main()
