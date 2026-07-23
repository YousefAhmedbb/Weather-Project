"""
Fetches the current weather for the capital city of every country
and appends one row per city to weather_data.csv.

Run manually:
    OWM_API_KEY=your_key python fetch_weather.py

Optional env vars:
    OWM_REQUEST_DELAY   Seconds to sleep between API calls (default 1.1)
    MAX_CITIES          Limit the number of cities for testing
"""

import csv
import os
import time
from datetime import datetime, timezone

import requests
import pandas as pd

API_KEY = os.environ["OWM_API_KEY"]
REQUEST_DELAY = float(os.environ.get("OWM_REQUEST_DELAY", "1.1"))
MAX_CITIES = os.environ.get("MAX_CITIES")

CSV_FILE = "weather_data.csv"
REST_COUNTRIES_URL = "https://restcountries.com/v3.1/all"

FIELDNAMES = [
    "fetch_timestamp",
    "city",
    "country_code",
    "country",
    "observation_datetime",
    "temp_c",
    "feels_like_c",
    "temp_min_c",
    "temp_max_c",
    "pressure",
    "humidity",
    "sea_level",
    "grnd_level",
    "wind_speed",
    "wind_deg",
    "wind_gust",
    "clouds_pct",
    "visibility",
    "rain_1h_mm",
    "snow_1h_mm",
    "weather_main",
    "weather_description",
    "weather_icon",
    "sunrise",
    "sunset",
    "lat",
    "lon",
]


def get_capital_cities():
    """Return list of capital cities with country codes."""

    response = requests.get(
        REST_COUNTRIES_URL,
        params={"fields": "capital,cca2,name"},
        timeout=20,
    )

    response.raise_for_status()

    countries = response.json()

    capitals = []

    for country in countries:
        capital = country.get("capital")
        code = country.get("cca2")

        if capital and code:
            capitals.append(
                {
                    "city": capital[0],
                    "country_code": code,
                }
            )

    capitals.sort(key=lambda x: x["city"])

    if MAX_CITIES:
        capitals = capitals[: int(MAX_CITIES)]

    return capitals


def fetch_city_weather(city, country_code):
    """Fetch current weather for one city."""

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": f"{city},{country_code}",
        "appid": API_KEY,
        "units": "metric",
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()

    main = data.get("main", {})
    wind = data.get("wind", {})
    weather = data["weather"][0]
    coord = data.get("coord", {})
    sys = data.get("sys", {})

    return {
        "fetch_timestamp": datetime.now(timezone.utc).isoformat(),

        "city": city,
        "country_code": country_code,
        "country": sys.get("country", country_code),

        "observation_datetime":
            datetime.fromtimestamp(
                data["dt"],
                tz=timezone.utc
            ).isoformat(),

        "temp_c": main.get("temp"),
        "feels_like_c": main.get("feels_like"),
        "temp_min_c": main.get("temp_min"),
        "temp_max_c": main.get("temp_max"),
        "pressure": main.get("pressure"),
        "humidity": main.get("humidity"),
        "sea_level": main.get("sea_level", ""),
        "grnd_level": main.get("grnd_level", ""),

        "wind_speed": wind.get("speed", ""),
        "wind_deg": wind.get("deg", ""),
        "wind_gust": wind.get("gust", ""),

        "clouds_pct": data.get("clouds", {}).get("all", ""),
        "visibility": data.get("visibility", ""),

        "rain_1h_mm": data.get("rain", {}).get("1h", 0),
        "snow_1h_mm": data.get("snow", {}).get("1h", 0),

        "weather_main": weather.get("main"),
        "weather_description": weather.get("description"),
        "weather_icon": weather.get("icon"),

        "sunrise":
            datetime.fromtimestamp(
                sys.get("sunrise", 0),
                tz=timezone.utc
            ).isoformat()
            if sys.get("sunrise")
            else "",

        "sunset":
            datetime.fromtimestamp(
                sys.get("sunset", 0),
                tz=timezone.utc
            ).isoformat()
            if sys.get("sunset")
            else "",

        "lat": coord.get("lat"),
        "lon": coord.get("lon"),
    }


def main():

    print("Fetching capital city list...")

    cities = get_capital_cities()

    print(f"Found {len(cities)} capital cities.")

    existing_keys = set()

if file_exists:
    try:
        existing = pd.read_csv(
            CSV_FILE,
            usecols=["city", "observation_datetime"]
        )

        existing_keys = set(
            zip(
                existing["city"],
                existing["observation_datetime"]
            )
        )

        print(f"Loaded {len(existing_keys)} existing records.")

    except Exception:
        pass

    with open(
        CSV_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES
        )

        if not file_exists:
            writer.writeheader()

        total = 0
        failed = []

        for i, item in enumerate(cities, start=1):

            city = item["city"]
            cc = item["country_code"]

            try:
                row = fetch_city_weather(city, cc)

key = (
    row["city"],
    row["observation_datetime"]
)

if key not in existing_keys:

    writer.writerow(row)

    existing_keys.add(key)

    total += 1

    print(
        f"[{i}/{len(cities)}] "
        f"{city}, {cc} ✓ Added"
    )

else:

    print(
        f"[{i}/{len(cities)}] "
        f"{city}, {cc} ✓ Duplicate skipped"
    )
                

            except Exception as e:

                failed.append(city)

                print(
                    f"[{i}/{len(cities)}] "
                    f"{city}, {cc} ✗ {e}"
                )

            if i < len(cities):
                time.sleep(REQUEST_DELAY)

    print(f"\nFinished.")

    print(f"Rows added: {total}")

    if failed:
        print(f"Failed cities ({len(failed)}):")
        print(", ".join(failed))


if __name__ == "__main__":
    main()
