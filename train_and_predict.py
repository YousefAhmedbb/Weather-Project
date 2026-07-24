"""
Trains a temperature-forecasting model on weather_data_features.csv and
writes out predictions for the dashboard.

This is a script version of the "Temperature prediction model" section of
EDA_and_anomaly_detection.ipynb / WeatherFinalProject.ipynb. The modeling
logic (features, split, pipeline, model choice) is kept identical to the
notebook on purpose -- only the surrounding plumbing (I/O, logging, exit
codes) has been added so it can run unattended in CI.

Reads:
    weather_data_features.csv   (produced by process_weather.py)

Writes:
    linear_weather_model.pkl    - the trained model, retrained fresh each run
    weather_predictions.csv     - weather_data_features.csv + predicted_temp_3h,
                                   the file the dashboard reads

Run manually:
    python train_and_predict.py

In GitHub Actions, this runs as a step right after process_weather.py in the
same job (see the workflow file).

Exit codes:
    0 - success
    1 - unrecoverable problem (input file missing, too few rows to train/
        evaluate, or a required column is missing)
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FEATURES_PATH = Path("weather_data_features.csv")
MODEL_PATH = Path("linear_weather_model.pkl")
PREDICTIONS_PATH = Path("weather_predictions.csv")

# Same feature lists as the notebook.
NUMERIC_FEATURES = [
    "temp_c", "feels_like_c", "temp_min_c", "temp_max_c", "pressure",
    "humidity", "wind_speed", "wind_deg", "wind_gust", "clouds_pct",
    "visibility", "pop", "rain_3h_mm", "snow_3h_mm", "hour", "month",
    "temp_range_c", "feels_like_delta_c", "temp_rolling_avg_9h",
]
CATEGORICAL_FEATURES = [
    "city", "weather_main", "part_of_day", "is_raining", "is_snowing", "is_daytime",
]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "target_temp_3h"

# Minimum rows needed before a train/test split + model fit is meaningful.
MIN_ROWS_TO_TRAIN = 20


def load_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run process_weather.py first.")
    df = pd.read_csv(path)
    print(f"Loaded {len(df):,} rows from {path}")
    return df


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Mirrors the notebook's target-construction cells:
    sort by city/time, shift temp_c by -1 within each city to get the
    'next reading' as the 3h-ahead target, then drop rows with no target
    (the last reading per city, which has nothing to predict).
    """
    df = df.copy()
    df["forecast_datetime"] = pd.to_datetime(df["forecast_datetime"])
    df = df.sort_values(["city", "forecast_datetime"])

    df[TARGET] = df.groupby("city")["temp_c"].shift(-1)
    df = df.dropna(subset=[TARGET])

    return df


def make_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", LinearRegression()),
    ])


def train(df_train: pd.DataFrame) -> Pipeline:
    X = df_train[ALL_FEATURES]
    y = df_train[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = make_pipeline()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print("\n--- Holdout evaluation (Linear Regression) ---")
    print(f"  MAE : {mae:.3f}")
    print(f"  RMSE: {rmse:.3f}")
    print(f"  R2  : {r2:.3f}")

    return model


def main() -> int:
    try:
        df = load_features(FEATURES_PATH)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    missing_cols = [c for c in ALL_FEATURES + ["forecast_datetime", "temp_c"] if c not in df.columns]
    if missing_cols:
        print(f"ERROR: weather_data_features.csv is missing required columns: {missing_cols}", file=sys.stderr)
        return 1

    df_train = build_training_frame(df)
    print(f"{len(df_train):,} rows have a valid target after building (city, next-reading) pairs")

    if len(df_train) < MIN_ROWS_TO_TRAIN:
        print(
            f"ERROR: only {len(df_train)} trainable rows (need >= {MIN_ROWS_TO_TRAIN}). "
            "Let weather_data.csv accumulate more history before training.",
            file=sys.stderr,
        )
        return 1

    model = train(df_train)

    joblib.dump(model, MODEL_PATH)
    print(f"\nSaved trained model to {MODEL_PATH}")

    # Predict on the full features file, same as the notebook's
    # "Predict New Data" section (re-reads the features file and scores it).
    X_all = df[ALL_FEATURES]
    df_predictions = df.copy()
    df_predictions["predicted_temp_3h"] = model.predict(X_all)

    df_predictions.to_csv(PREDICTIONS_PATH, index=False)
    print(f"Wrote {len(df_predictions):,} rows with predictions to {PREDICTIONS_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
