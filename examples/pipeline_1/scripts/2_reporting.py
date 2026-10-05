from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def load_orders(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    ordered_rows = sorted(rows, key=lambda row: row["order_date"])
    revenue_by_region: dict[str, float] = defaultdict(float)
    orders_by_region: dict[str, int] = defaultdict(int)
    units_by_product: dict[str, int] = defaultdict(int)
    revenue_by_product: dict[str, float] = defaultdict(float)

    for row in ordered_rows:
        region = row["region"]
        product = row["product"]
        quantity = int(row["quantity"])
        order_value = float(row["order_value"])

        revenue_by_region[region] += order_value
        orders_by_region[region] += 1
        units_by_product[product] += quantity
        revenue_by_product[product] += order_value

    total_revenue = round(sum(revenue_by_region.values()), 2)
    top_region = (
        max(revenue_by_region, key=revenue_by_region.get) if revenue_by_region else None
    )
    top_product = (
        max(revenue_by_product, key=revenue_by_product.get)
        if revenue_by_product
        else None
    )

    return {
        "total_orders": len(ordered_rows),
        "total_revenue": total_revenue,
        "revenue_by_region": {
            region: round(amount, 2)
            for region, amount in sorted(revenue_by_region.items())
        },
        "orders_by_region": dict(sorted(orders_by_region.items())),
        "units_by_product": dict(sorted(units_by_product.items())),
        "revenue_by_product": {
            product: round(amount, 2)
            for product, amount in sorted(revenue_by_product.items())
        },
        "top_region": top_region,
        "top_product": top_product,
        "first_order_date": ordered_rows[0]["order_date"] if ordered_rows else None,
        "last_order_date": ordered_rows[-1]["order_date"] if ordered_rows else None,
    }


def write_summary(summary_path: Path, summary: dict[str, object]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_region_breakdown(region_path: Path, summary: dict[str, object]) -> None:
    region_path.parent.mkdir(parents=True, exist_ok=True)
    with region_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["region", "orders", "revenue"])
        writer.writeheader()
        for region, revenue in summary["revenue_by_region"].items():
            writer.writerow(
                {
                    "region": region,
                    "orders": summary["orders_by_region"][region],
                    "revenue": revenue,
                }
            )


def main(context=None) -> dict[str, object]:
    output_root = context.resolve_output_root(path_type="path")
    clean_path = context.resolve_given_path(
        stage_name="1_preprocessing",
        path_name="clean_path",
        file_name="1_clean_orders.csv",
        root=output_root,
        path_type="path",
        add_folder="interim",
    )
    summary_path = output_root / "processed" / "2_sales_summary.json"
    region_breakdown_path = output_root / "processed" / "2_revenue_by_region.csv"

    rows = load_orders(clean_path)
    summary = build_summary(rows)
    write_summary(summary_path, summary)
    write_region_breakdown(region_breakdown_path, summary)

    return {
        "clean_path": str(clean_path),
        "report_path": str(summary_path),
        "region_breakdown_path": str(region_breakdown_path),
        "total_orders": summary["total_orders"],
        "total_revenue": summary["total_revenue"],
        "top_region": summary["top_region"],
        "top_product": summary["top_product"],
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
