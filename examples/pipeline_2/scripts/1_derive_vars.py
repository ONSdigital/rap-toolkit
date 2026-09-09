import numpy as np
import pandas as pd


def correct_date_time(df):
    df["Order_date"] = pd.to_datetime(df["Order_date"])
    return df


def estimate_delivery(df, delivery_times):
    df["Estimated_delvery_date"] = df["Order_date"] + pd.to_timedelta(
        df["Region"].map(delivery_times), unit="D"
    )
    df["Delivery_day"] = df["Estimated_delvery_date"].dt.day_name()
    return df


def total_cost(df):
    df["Total_cost"] = df["Quantity"] * df["Unit_price"]
    return df


def order_date_values(df):
    df["Order_day"] = df["Order_date"].dt.day_name()
    df["Order_month"] = df["Order_date"].dt.month_name()
    return df


def size_order_alert(df):
    df["Large_order"] = df["Quantity"] > df["Quantity"].quantile(0.75)
    df["Small_order"] = df["Quantity"] < df["Quantity"].quantile(0.25)
    return df


def postage_cost(df):
    df["Postage"] = np.select(
        [df["Large_order"], df["Small_order"]], [5.00, 1.00], default=2.50
    )
    return df


def production_cost(df):
    df["Total_production_cost"] = np.select(
        [
            df["Product"] == "notebook",
            df["Product"] == "pen",
            df["Product"] == "folder",
        ],
        [(1.00 * df["Quantity"]), (0.3 * df["Quantity"]), (0.75 * df["Quantity"])],
        default=0,
    )
    return df


def profit_per_order(df):
    df["Order_profit"] = df["Total_cost"] - df["Total_production_cost"] - df["Postage"]
    return df


def main(context=None):
    # Get stage configuration for this stage
    config = context.get_stage_config("1_derive_vars")

    # Source data path for previous stage results which are required
    # for this stage and read those in
    data_path = context.resolve_given_path(
        "0_clean_data", "output_location", "orders_cleaned.csv", context.get_data_dir()
    )
    df = pd.read_csv(data_path)

    # Source variable list from stage configuration for this stage
    delivery_times = config["delivery_times"]

    # Run relevant functions for this stage
    df = correct_date_time(df)
    df = estimate_delivery(df, delivery_times)
    df = total_cost(df)
    df = order_date_values(df)
    df = size_order_alert(df)
    df = postage_cost(df)
    df = production_cost(df)
    df = profit_per_order(df)

    # Save results to output location calculated based on run_directory
    output_root = context.resolve_output_root()
    df.to_csv(output_root / "orders_prepped.csv", index=False)

    return {
        "output_location": str(output_root / "orders_prepped.csv"),
        "record_count": len(df),
        "columns": list(df.columns),
    }


if __name__ == "__main__":
    main()
