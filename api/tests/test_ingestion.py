from pathlib import Path

import pytest

from app.ingestion import InvalidHeader, InvalidRow, parse_csv, parse_measurement

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def test_valid_csv():
    result = parse_csv((DATA_DIR / "mesures-salles-2026-10-05.csv").read_bytes())

    assert len(result.measurements) == 63
    assert result.rejected == []
    assert result.duplicates == 0


def test_csv_with_errors():
    result = parse_csv((DATA_DIR / "mesures-avec-erreurs.csv").read_bytes())

    assert len(result.measurements) == 4
    assert [error.line for error in result.rejected] == [5, 6, 7, 8, 9, 10, 12]
    assert result.duplicates == 1


def test_invalid_header():
    content = (DATA_DIR / "en-tete-invalide.csv").read_bytes()

    with pytest.raises(InvalidHeader, match="Invalid header"):
        parse_csv(content)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        (2, "2147483648", "co2_ppm out of storage range"),
        (3, "1000", "temperature_c out of storage range"),
    ],
)
def test_values_that_cannot_fit_database_are_rejected(field, value, reason):
    row = ["A101", "2026-10-05T08:00:00+02:00", "430", "19.5", "42.0"]
    row[field] = value
    with pytest.raises(InvalidRow, match=reason):
        parse_measurement(row)
