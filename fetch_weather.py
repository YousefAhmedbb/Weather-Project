"""
Fetches 5-day / 3-hour forecast data for the capital city of every country
(pulled live from the REST Countries API) from OpenWeatherMap, and appends
each forecast interval as a row to weather_data.csv.

Each OpenWeatherMap API call returns ~40 rows (5 days x 8 three-hour slots)
per city. With ~195-250 countries, one run makes ~200-250 calls to OWM and
writes ~8,000-10,000 rows. That comfortably fits OpenWeatherMap's free tier
(60 calls/min, 1,000,000 calls/month) as long as we pace the requests, which
this script does automatically.

Run manually:
    OWM_API_KEY=your_key python fetch_weather.py

In GitHub Actions, OWM_API_KEY is injected from a repo secret (see the
workflow file).

Optional env vars:
    OWM_REQUEST_DELAY   Seconds to sleep between OWM calls (default 1.1,
                         safely under the 60 calls/min free-tier cap)
    MAX_CITIES           Cap the number of capitals fetched, for testing
                         (e.g. MAX_CITIES=10)
"""

import csv
import os
import time
from datetime import datetime, timezone

import requests

API_KEY = os.environ["OWM_API_KEY"]
REQUEST_DELAY = float(os.environ.get("OWM_REQUEST_DELAY", "1.1"))
MAX_CITIES = os.environ.get("MAX_CITIES")

CSV_FILE = "weather_data.csv"
REST_COUNTRIES_URL = "https://restcountries.com/v3.1/all"

FIELDNAMES = [
    "fetch_timestamp",  # when this run pulled the data
    "city",
    "country_code",
    "country",
    "forecast_datetime",  # the date/time this row's forecast applies to
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
    "pop",  # probability of precipitation, 0-1
    "rain_3h_mm",
    "snow_3h_mm",
    "weather_main",
    "weather_description",
    "part_of_day",  # d = day, n = night
]


def get_capital_cities() -> list[dict]:
    """
    Returns one dict per country: {"city": <capital name>, "country_code": <cca2>}.

    Pulled live from the REST Countries API so the list stays current and we
    don't have to hand-maintain ~250 country/capital pairs. Countries with no
    listed capital (a handful of territories) are skipped. Countries with
    multiple official capitals (e.g. South Africa) use the first one listed.
    """
    resp = requests.get(
        REST_COUNTRIES_URL,
        params={"fields": "capital,cca2,name"},
        timeout=15,
    )
    resp.raise_for_status()
    countries = resp.json()

    capitals = []
    for country in countries:
        capital_list = country.get("capital") or []
        cca2 = country.get("cca2")
        if not capital_list or not cca2:
            continue  # skip territories/entities with no capital or code
        capitals.append({"city": capital_list[0], "country_code": cca2})

    # Sort for stable, readable run order
    capitals.sort(key=lambda c: c["city"])

    if MAX_CITIES:
        capitals = capitals[: int(MAX_CITIES)]

    return capitals


def fetch_city_forecast(city: str, country_code: str) -> list[dict]:
    url = "https://api.openweathermap.org/data/2.5/forecast"
    # "City,CC" disambiguates same-named cities in different countries
    # (there are multiple "San Jose"s, "Georgetown"s, etc.)
    params = {"q": f"{city},{country_code}", "appid": API_KEY, "units": "metric"}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    fetch_time = datetime.now(timezone.utc).isoformat()
    country = data.get("city", {}).get("country", country_code)

    rows = []
    for entry in data["list"]:
        main = entry["main"]
        wind = entry.get("wind", {})
        weather = entry["weather"][0]
        rows.append({
            "fetch_timestamp": fetch_time,
            "city": city,
            "country_code": country_code,
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
    print("Fetching capital city list from REST Countries API...")
    cities = get_capital_cities()
    print(f"Got {len(cities)} capital cities to fetch.")

    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        total = 0
        failed = []
        for i, entry in enumerate(cities, start=1):
            city = entry["city"]
            cc = entry["country_code"]
            try:
                rows = fetch_city_forecast(city, cc)
                writer.writerows(rows)
                total += len(rows)
                print(f"[{i}/{len(cities)}] Fetched {len(rows)} rows for {city}, {cc}")
            except Exception as e:
                # Don't let one failed city kill the whole run
                failed.append(city)
                print(f"[{i}/{len(cities)}] Failed for {city}, {cc}: {e}")

            # Pace requests to stay under OpenWeatherMap's free-tier
            # 60 calls/minute rate limit.
            if i < len(cities):
                time.sleep(REQUEST_DELAY)

        print(f"\nTotal rows written this run: {total}")
        if failed:
            print(f"Failed cities ({len(failed)}): {', '.join(failed)}")


if __name__ == "__main__":
    main()
    
