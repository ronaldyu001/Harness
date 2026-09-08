"""Weather snapshot identity, missing data, and time invariants."""

import unittest
from datetime import UTC, date, datetime, timedelta, timezone

from domain.entities import (
    DailyWeatherForecast,
    WeatherConditions,
    WeatherForecast,
    WeatherLocation,
)


class WeatherForecastTests(unittest.TestCase):
    def snapshot(self, **values):
        return WeatherForecast(
            forecast_id="forecast-1",
            location=WeatherLocation(39.74, -104.99, "America/Denver"),
            fetched_at=datetime(2026, 9, 8, tzinfo=UTC),
            source="open-meteo",
            **values,
        )

    def test_missing_measurements_are_distinct_from_zero(self):
        current = WeatherConditions(
            valid_at=datetime(2026, 9, 8, tzinfo=UTC),
            interval_seconds=900,
            precipitation_mm=0,
        )
        forecast = self.snapshot(current=current)
        self.assertEqual(forecast.current.precipitation_mm, 0)
        self.assertIsNone(forecast.current.precipitation_probability_percent)
        self.assertIsNone(forecast.issued_at)

    def test_naive_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            WeatherConditions(datetime(2026, 9, 8), 3600)

    def test_repeated_local_hour_with_different_offsets_is_valid(self):
        hours = tuple(
            WeatherConditions(
                datetime(2026, 11, 1, 1, tzinfo=timezone(timedelta(hours=offset))),
                3600,
            )
            for offset in (-6, -7)
        )
        self.assertEqual(len(self.snapshot(hourly=hours).hourly), 2)
        with self.assertRaisesRegex(ValueError, "increasing timestamps"):
            self.snapshot(hourly=tuple(reversed(hours)))

    def test_duplicate_daily_dates_are_rejected(self):
        day = DailyWeatherForecast(date(2026, 9, 8))
        with self.assertRaisesRegex(ValueError, "increasing dates"):
            self.snapshot(daily=(day, day))

    def test_polar_day_does_not_require_sunrise_or_sunset(self):
        day = DailyWeatherForecast(date(2026, 6, 21), daylight_duration_seconds=86400)
        self.assertIsNone(day.sunrise)
        self.assertIsNone(day.sunset)

    def test_inverted_temperature_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "minimum temperature"):
            DailyWeatherForecast(date(2026, 9, 8), temperature_min_c=20, temperature_max_c=10)
