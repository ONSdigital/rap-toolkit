from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from onsrap import ExecutionContext


def load_orders(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_text(value: object) -> str:
    return str(value).strip()


def normalize_title_case(value: object) -> str:
    return normalize_text(value).lower().title()


def parse_int(value: object) -> int:
    return int(normalize_text(value))


def parse_float(value: object) -> float:
    return float(normalize_text(value))


def parse_date(value: object) -> str:
    return date.fromisoformat(normalize_text(value)).isoformat()


def clean_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    cleaned_rows: list[dict[str, object]] = []

    for row in rows:
        quantity = parse_int(row["quantity"])
        unit_price = round(parse_float(row["unit_price"]), 2)
        cleaned_rows.append(
            {
                "order_id": normalize_text(row["order_id"]),
                "customer_name": normalize_title_case(row["customer_name"]),
                "region": normalize_title_case(row["region"]),
                "product": normalize_title_case(row["product"]),
                "order_date": parse_date(row["order_date"]),
                "quantity": quantity,
                "unit_price": unit_price,
                "order_value": round(quantity * unit_price, 2),
            }
        )

    return cleaned_rows


def write_clean_rows(clean_path: Path, rows: list[dict[str, object]]) -> None:
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "order_id",
        "customer_name",
        "region",
        "product",
        "order_date",
        "quantity",
        "unit_price",
        "order_value",
    ]

    with clean_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(
    source_path: Path, clean_path: Path, rows: list[dict[str, object]]
) -> dict[str, object]:
    total_revenue = round(sum(float(row["order_value"]) for row in rows), 2)
    return {
        "source_path": str(source_path),
        "clean_path": str(clean_path),
        "row_count": len(rows),
        "total_revenue": total_revenue,
        "average_order_value": round(total_revenue / len(rows), 2) if rows else 0.0,
        "regions": sorted({str(row["region"]) for row in rows}),
        "products": sorted({str(row["product"]) for row in rows}),
    }


def main(context: ExecutionContext = None) -> dict[str, object]:
    data_root = context.get_data_dir(path_type="path")
    output_root = context.resolve_output_root(path_type="path")
    raw_path = context.resolve_given_path(
        stage_name="0_data_validation",
        path_name="raw_path",
        file_name="orders.csv",
        path_type="path",
        root=data_root,
    )
    clean_path = output_root / "interim" / "1_clean_orders.csv"

    rows = load_orders(raw_path)
    cleaned_rows = clean_rows(rows)
    write_clean_rows(clean_path, cleaned_rows)
    summary = build_summary(raw_path, clean_path, cleaned_rows)

    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
