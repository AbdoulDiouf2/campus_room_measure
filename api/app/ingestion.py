import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO

EXPECTED_HEADER = (
    "room",
    "measured_at",
    "co2_ppm",
    "temperature_c",
    "humidity_pct",
)


class CsvFormatError(ValueError):
    """Le fichier CSV ne peut pas être lu correctement."""


class InvalidHeader(CsvFormatError):
    """Les colonnes du fichier ne correspondent pas au contrat."""


def read_rows(content: bytes) -> list[tuple[int, list[str]]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvFormatError("Invalid UTF-8") from exc

    reader = csv.reader(StringIO(text, newline=""), strict=True)

    try:
        header = next(reader)
    except StopIteration:
        raise InvalidHeader("Invalid header") from None

    if tuple(header) != EXPECTED_HEADER:
        raise InvalidHeader("Invalid header")

    try:
        return [(reader.line_num, row) for row in reader]
    except csv.Error as exc:
        raise CsvFormatError("Invalid CSV") from exc


class InvalidRow(ValueError):
    """Une ligne de données est invalide."""


@dataclass(frozen=True)
class ParsedMeasurement:
    room: str
    measured_at: datetime
    co2_ppm: int
    temperature_c: Decimal
    humidity_pct: Decimal


def parse_measurement(
    row: list[str], *, now: datetime | None = None
) -> ParsedMeasurement:
    if len(row) != 5:
        raise InvalidRow("Expected 5 columns")

    room = row[0].strip()
    if not room:
        raise InvalidRow("Missing room")

    raw_date = row[1].strip()
    if "T" not in raw_date:
        raise InvalidRow("Invalid measured_at")

    try:
        measured_at = datetime.fromisoformat(raw_date)
    except ValueError as exc:
        raise InvalidRow("Invalid measured_at") from exc

    if measured_at.tzinfo is None or measured_at.utcoffset() is None:
        raise InvalidRow("Missing timezone")
    if measured_at > (now or datetime.now(timezone.utc)):
        raise InvalidRow("Future measured_at")

    try:
        co2_ppm = int(row[2])
    except ValueError as exc:
        raise InvalidRow("Invalid co2_ppm") from exc
    if co2_ppm < 0:
        raise InvalidRow("Negative co2_ppm")
    if co2_ppm > 2_147_483_647:
        raise InvalidRow("co2_ppm out of storage range")

    try:
        temperature_c = Decimal(row[3])
        humidity_pct = Decimal(row[4])
    except InvalidOperation as exc:
        raise InvalidRow("Invalid temperature or humidity") from exc

    if not temperature_c.is_finite():
        raise InvalidRow("Invalid temperature_c")
    if not Decimal("-999.99") <= temperature_c <= Decimal("999.99"):
        raise InvalidRow("temperature_c out of storage range")
    if not humidity_pct.is_finite() or not 0 <= humidity_pct <= 100:
        raise InvalidRow("Invalid humidity_pct")

    return ParsedMeasurement(
        room=room,
        measured_at=measured_at,
        co2_ppm=co2_ppm,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
    )


def check_line(row: list[str], now: datetime) -> ParsedMeasurement:
    """Apply the CSV measurement rules to one Kafka message too."""
    return parse_measurement(row, now=now)


@dataclass(frozen=True)
class RejectedRow:
    line: int
    reason: str


@dataclass
class ParseResult:
    measurements: list[ParsedMeasurement]
    rejected: list[RejectedRow]
    duplicates: int


def parse_csv(content: bytes, *, now: datetime | None = None) -> ParseResult:
    checked_at = now or datetime.now(timezone.utc)
    measurements: list[ParsedMeasurement] = []
    rejected: list[RejectedRow] = []
    duplicates = 0
    seen: set[tuple[str, datetime]] = set()

    for line_number, row in read_rows(content):
        try:
            measurement = parse_measurement(row, now=checked_at)
        except InvalidRow as exc:
            rejected.append(RejectedRow(line=line_number, reason=str(exc)))
            continue

        key = (measurement.room, measurement.measured_at)
        if key in seen:
            duplicates += 1
            continue

        seen.add(key)
        measurements.append(measurement)

    return ParseResult(
        measurements=measurements,
        rejected=rejected,
        duplicates=duplicates,
    )
