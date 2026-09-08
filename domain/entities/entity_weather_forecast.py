"""Provider-independent weather data for Maia's summaries and planning.

Measurements use Celsius, millimeters of precipitation water equivalent,
centimeters of snowfall, km/h wind at 10 m, meters of visibility, and percentages
on a 0–100 scale. Wind direction is degrees clockwise from north (where wind
comes from). None means unavailable, never zero or clear weather.

The subset is informed by https://open-meteo.com/en/docs. Provider field mapping,
unit conversion, and WMO-code translation belong in infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum


class WeatherCondition(StrEnum):
    """Summary categories; freezing precipitation remains distinct."""

    UNKNOWN = "unknown"
    CLEAR = "clear"
    MAINLY_CLEAR = "mainly_clear"
    PARTLY_CLOUDY = "partly_cloudy"
    OVERCAST = "overcast"
    FOG = "fog"
    FREEZING_FOG = "freezing_fog"
    DRIZZLE = "drizzle"
    FREEZING_DRIZZLE = "freezing_drizzle"
    RAIN = "rain"
    FREEZING_RAIN = "freezing_rain"
    SNOW = "snow"
    SNOW_GRAINS = "snow_grains"
    RAIN_SHOWERS = "rain_showers"
    SNOW_SHOWERS = "snow_showers"
    THUNDERSTORM = "thunderstorm"
    THUNDERSTORM_WITH_HAIL = "thunderstorm_with_hail"


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class WeatherLocation:
    """Forecast coordinates and IANA timezone used for local calendar days."""

    latitude: float
    longitude: float
    timezone: str
    name: str | None = None
    elevation_m: float | None = None

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if not self.timezone.strip():
            raise ValueError("timezone is required")


@dataclass(frozen=True, slots=True)
class WeatherConditions:
    """Current or hourly conditions at valid_at, which must include an offset.

    Precipitation amounts/probability and peak gusts describe the interval
    ending at valid_at; interval_seconds makes current versus hourly periods
    explicit. Other measurements describe conditions at valid_at. Current
    conditions may be model estimates, rather than station observations.
    """

    valid_at: datetime
    interval_seconds: int
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    temperature_c: float | None = None
    feels_like_c: float | None = None
    relative_humidity_percent: float | None = None
    dew_point_c: float | None = None
    precipitation_probability_percent: float | None = None
    precipitation_mm: float | None = None
    snowfall_cm: float | None = None
    wind_speed_kmh: float | None = None
    wind_gusts_kmh: float | None = None
    wind_direction_degrees: float | None = None
    cloud_cover_percent: float | None = None
    visibility_m: float | None = None
    uv_index: float | None = None
    is_day: bool | None = None

    def __post_init__(self) -> None:
        _require_aware(self.valid_at, "valid_at")
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")


@dataclass(frozen=True, slots=True)
class DailyWeatherForecast:
    """Outlook for one calendar date in the forecast location's timezone.

    Condition is the day's most severe condition. Precipitation probability
    is the maximum hourly probability, not the probability of rain all day.
    Sunrise/sunset can be unavailable during polar day or night.
    """

    date: date
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    feels_like_min_c: float | None = None
    feels_like_max_c: float | None = None
    precipitation_probability_max_percent: float | None = None
    precipitation_sum_mm: float | None = None
    snowfall_sum_cm: float | None = None
    precipitation_hours: float | None = None
    wind_speed_max_kmh: float | None = None
    wind_gusts_max_kmh: float | None = None
    wind_direction_dominant_degrees: float | None = None
    uv_index_max: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None
    daylight_duration_seconds: float | None = None
    sunshine_duration_seconds: float | None = None

    def __post_init__(self) -> None:
        for name in ("sunrise", "sunset"):
            value = getattr(self, name)
            if value is not None:
                _require_aware(value, name)
        for low, high in (
            (self.temperature_min_c, self.temperature_max_c),
            (self.feels_like_min_c, self.feels_like_max_c),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError("minimum temperature must not exceed maximum")


@dataclass(frozen=True, slots=True)
class WeatherForecast:
    """Identified forecast snapshot for a location, independent of its provider.

    forecast_id identifies this snapshot; fetching a new snapshot assigns a new
    identity. fetched_at records retrieval freshness, not model issuance time.
    issued_at is optional because a provider may not expose model run time.
    Hourly and daily timelines are strictly increasing and can contain gaps.
    An empty timeline means unavailable, not a prediction of no weather.
    """

    forecast_id: str
    location: WeatherLocation
    fetched_at: datetime
    source: str
    current: WeatherConditions | None = None
    hourly: tuple[WeatherConditions, ...] = ()
    daily: tuple[DailyWeatherForecast, ...] = ()
    issued_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.forecast_id.strip():
            raise ValueError("forecast_id is required")
        if not self.source.strip():
            raise ValueError("source is required")
        _require_aware(self.fetched_at, "fetched_at")
        if self.issued_at is not None:
            _require_aware(self.issued_at, "issued_at")
        for earlier, later in zip(self.hourly, self.hourly[1:]):
            if earlier.valid_at.astimezone(UTC) >= later.valid_at.astimezone(UTC):
                raise ValueError("hourly forecasts must have increasing timestamps")
        for earlier, later in zip(self.daily, self.daily[1:]):
            if earlier.date >= later.date:
                raise ValueError("daily forecasts must have increasing dates")
