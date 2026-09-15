from __future__ import annotations

import csv
import json
from pathlib import Path

from onsrap import ExecutionContext

REQUIRED_COLUMNS = (
    "order_id",
    "customer_name",
    "region",
    "product",
    "quantity",
    "unit_price",
    "order_date",
)


def load_orders(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def is_blank(value: object) -> bool:
    return not str(value or "").strip()


def parse_positive_number(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (AttributeError, TypeError, ValueError):
        return None

    return number if number > 0 else None


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    issues: list[str] = []

    for row_number, row in enumerate(rows, start=2):
        for column in REQUIRED_COLUMNS:
            if is_blank(row.get(column)):
                issues.append(f"row {row_number}: missing {column}")

        if parse_positive_number(row.get("quantity")) is None:
            issues.append(f"row {row_number}: quantity must be positive")

        if parse_positive_number(row.get("unit_price")) is None:
            issues.append(f"row {row_number}: unit_price must be positive")

    return issues


def build_report(
    raw_path: Path, rows: list[dict[str, str]], issues: list[str]
) -> dict[str, object]:
    order_dates = sorted(
        row["order_date"].strip() for row in rows if not is_blank(row.get("order_date"))
    )
    unique_regions = sorted(
        {
            str(row.get("region", "")).strip().title()
            for row in rows
            if not is_blank(row.get("region"))
        }
    )

    return {
        "source_path": str(raw_path),
        "record_count": len(rows),
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "required_columns": list(REQUIRED_COLUMNS),
        "first_order_date": order_dates[0] if order_dates else None,
        "last_order_date": order_dates[-1] if order_dates else None,
        "unique_regions": unique_regions,
    }


def write_report(report_path: Path, report: dict[str, object]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(context: ExecutionContext = None) -> dict[str, object]:
    data_root = context.get_data_dir()
    output_root = context.resolve_output_root()
    raw_path = data_root / "orders.csv"
    report_path = output_root / "interim" / "0_validation_report.json"

    rows = load_orders(raw_path)
    issues = validate_rows(rows)
    report = build_report(raw_path, rows, issues)
    write_report(report_path, report)

    return {
        "raw_path": str(raw_path),
        "report_path": str(report_path),
        "record_count": len(rows),
        "issue_count": len(issues),
        "passed": not issues,
        "issues": issues,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
