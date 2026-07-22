"""
Fetches 5-day / 3-hour forecast data for a list of cities from OpenWeatherMap
and appends each forecast interval as a row to weather_data.csv.

Each API call returns ~40 rows (5 days x 8 three-hour slots) per city, so
tracking 8 cities gives ~320 rows in a SINGLE run.

Run manually:
    OWM_API_KEY=your_key python fetch_weather.py

In GitHub Actions, OWM_API_KEY is injected from a repo secret (see the workflow file).
"""

import csv
import os
from datetime import datetime, timezone

import requests

API_KEY = os.environ["OWM_API_KEY"]

# Edit this list to track whichever cities you want.
# More cities = more rows per run (each city adds ~40 rows).
CITIES = [
    "Cairo", "London", "New York", "Tokyo",
    "Paris", "Dubai", "Sydney", "Berlin",
]

CSV_FILE = "weather_data.csv"
FIELDNAMES = [
    "fetch_timestamp",     # when this run pulled the data
    "city",
    "country",
    "forecast_datetime",   # the date/time this row's forecast applies to
    "temp_c",
    "feels_like_c",
    "temp_min_c",
    "temp_max_c",
    "pressure",
    "humidity",
    "wind_speed",
    "wind_deg",
    "wind_gust",
    "clouds_pct",
    "visibility",
    "pop",                 # probability of precipitation, 0-1
    "rain_3h_mm",
    "snow_3h_mm",
    "weather_main",
    "weather_description",
    "part_of_day",         # d = day, n = night
]


def fetch_city_forecast(city: str) -> list[dict]:
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": API_KEY, "units": "metric"}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    fetch_time = datetime.now(timezone.utc).isoformat()
    country = data.get("city", {}).get("country", "")
    rows = []

    for entry in data["list"]:
        main = entry["main"]
        wind = entry.get("wind", {})
        weather = entry["weather"][0]
        rows.append({
            "fetch_timestamp": fetch_time,
            "city": city,
            "country": country,
            "forecast_datetime": entry["dt_txt"],
            "temp_c": main["temp"],
            "feels_like_c": main["feels_like"],
            "temp_min_c": main["temp_min"],
            "temp_max_c": main["temp_max"],
            "pressure": main["pressure"],
            "humidity": main["humidity"],
            "wind_speed": wind.get("speed", ""),
            "wind_deg": wind.get("deg", ""),
            "wind_gust": wind.get("gust", ""),
            "clouds_pct": entry.get("clouds", {}).get("all", ""),
            "visibility": entry.get("visibility", ""),
            "pop": entry.get("pop", ""),
            "rain_3h_mm": entry.get("rain", {}).get("3h", 0),
            "snow_3h_mm": entry.get("snow", {}).get("3h", 0),
            "weather_main": weather["main"],
            "weather_description": weather["description"],
            "part_of_day": entry.get("sys", {}).get("pod", ""),
        })

    return rows


def main():
    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        total = 0
        for city in CITIES:
            try:
                rows = fetch_city_forecast(city)
                writer.writerows(rows)
                total += len(rows)
                print(f"Fetched {len(rows)} rows for {city}")
            except Exception as e:
                # Don't let one failed city kill the whole run
                print(f"Failed for {city}: {e}")

        print(f"Total rows written this run: {total}")


if __name__ == "__main__":
    main()
