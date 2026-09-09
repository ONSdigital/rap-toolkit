import pandas as pd


def check_variables(df, expected_variables):
    missing = []
    for i in expected_variables:
        if i in df.columns:
            pass
        else:
            missing.append(i)
    if missing == []:
        print("All variables present")
    print(f"Missing the following variables: {missing}")


def remove_identifiable(df, identifiable_cols):
    for i in identifiable_cols:
        if i in df.columns:
            df = df.drop(i, axis=1)
        else:
            pass
    return df


def standardise_columns(df):
    df.columns = [col.lower() for col in df.columns]
    df.columns = [col.capitalize() for col in df.columns]
    for item in df.columns:
        df[item] = df[item].apply(lambda x: x.lower() if isinstance(x, str) else x)
        df[item] = df[item].apply(lambda x: x.strip() if isinstance(x, str) else x)
    return df


def main(context=None):
    # Load stage configuration
    config = context.get_stage_config("0_clean_data")

    # Calculate location for run outputs
    output_root = context.resolve_output_root()
    full_output_location = output_root / "orders_cleaned.csv"

    # Calculate location of data input
    data_dir = context.get_data_dir()
    orders = pd.read_csv(data_dir / "orders.csv")

    # Source variable lists from stage configuration
    expected_variables = config["expected_variables"]
    identifiable_cols = config["identifiable_cols"]

    # Run functions required for this stage
    check_variables(orders, expected_variables)
    print(orders.dtypes)
    orders = remove_identifiable(orders, identifiable_cols)
    orders = standardise_columns(orders)

    # Save cleaned data to run specific output location defined earlier in function
    orders.to_csv(full_output_location, index=False)

    return {
        "output_location": str(full_output_location),
        "expected_variables": expected_variables,
        "identifiable_cols": identifiable_cols,
        "record_count": len(orders),
        "columns": list(orders.columns),
    }


if __name__ == "__main__":
    main(context=None)
