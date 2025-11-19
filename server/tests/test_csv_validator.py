"""Tests for CSV validation service."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app.services.csv_validator import CSVValidator, ValidationResult

if TYPE_CHECKING:
    from _pytest.tmpdir import TempPathFactory


@pytest.fixture
def csv_dir(tmp_path_factory: TempPathFactory) -> Path:
    """Create a temporary directory for test CSV files."""
    return tmp_path_factory.mktemp("csv_files")


def create_csv_file(file_path: Path, headers: list[str], rows: list[dict]) -> None:
    """Helper to create CSV files for testing."""
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


class TestCSVValidator:
    """Test suite for CSVValidator."""

    def test_validate_valid_csv(self, csv_dir: Path) -> None:
        """Test validation of a valid CSV file."""
        csv_file = csv_dir / "valid.csv"
        create_csv_file(
            csv_file,
            ["sku", "name", "description"],
            [
                {"sku": "SKU-001", "name": "Product 1", "description": "Description 1"},
                {"sku": "SKU-002", "name": "Product 2", "description": "Description 2"},
                {"sku": "SKU-003", "name": "Product 3", "description": ""},
            ],
        )

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is True
        assert result.total_rows == 3
        assert result.sample_size == 3
        assert len(result.errors) == 0

    def test_validate_with_active_field(self, csv_dir: Path) -> None:
        """Test validation with active field as boolean strings."""
        csv_file = csv_dir / "with_active.csv"
        create_csv_file(
            csv_file,
            ["sku", "name", "active"],
            [
                {"sku": "SKU-001", "name": "Product 1", "active": "true"},
                {"sku": "SKU-002", "name": "Product 2", "active": "false"},
                {"sku": "SKU-003", "name": "Product 3", "active": "yes"},
                {"sku": "SKU-004", "name": "Product 4", "active": "1"},
            ],
        )

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is True
        assert result.total_rows == 4

    def test_validate_invalid_extension(self, csv_dir: Path) -> None:
        """Test validation fails for non-CSV file extension."""
        txt_file = csv_dir / "data.txt"
        txt_file.write_text("some content")

        result = CSVValidator.validate_file(txt_file)

        assert result.is_valid is False
        assert any("Invalid file extension" in err for err in result.errors)

    def test_validate_missing_file(self, csv_dir: Path) -> None:
        """Test validation fails for non-existent file."""
        missing_file = csv_dir / "missing.csv"

        result = CSVValidator.validate_file(missing_file)

        assert result.is_valid is False
        assert any("File not found" in err for err in result.errors)

    def test_validate_missing_required_headers(self, csv_dir: Path) -> None:
        """Test validation fails when required headers are missing."""
        csv_file = csv_dir / "missing_headers.csv"
        create_csv_file(
            csv_file,
            ["sku", "description"],  # Missing 'name'
            [{"sku": "SKU-001", "description": "Test"}],
        )

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        assert any("Missing required headers" in err for err in result.errors)
        assert any("name" in err for err in result.errors)

    def test_validate_empty_csv(self, csv_dir: Path) -> None:
        """Test validation fails for empty CSV file."""
        csv_file = csv_dir / "empty.csv"
        csv_file.write_text("")

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        assert any("empty or has no headers" in err for err in result.errors)

    def test_validate_empty_required_field(self, csv_dir: Path) -> None:
        """Test validation fails when required fields are empty."""
        csv_file = csv_dir / "empty_fields.csv"
        create_csv_file(
            csv_file,
            ["sku", "name"],
            [
                {"sku": "", "name": "Product 1"},  # Empty SKU
                {"sku": "SKU-002", "name": ""},  # Empty name
            ],
        )

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        assert any("sku" in err.lower() for err in result.errors)
        assert any("name" in err.lower() for err in result.errors)

    def test_validate_unknown_headers_warning(self, csv_dir: Path) -> None:
        """Test validation warns about unknown headers but doesn't fail."""
        csv_file = csv_dir / "unknown_headers.csv"
        create_csv_file(
            csv_file,
            ["sku", "name", "unknown_field", "another_unknown"],
            [
                {
                    "sku": "SKU-001",
                    "name": "Product 1",
                    "unknown_field": "value",
                    "another_unknown": "value",
                }
            ],
        )

        result = CSVValidator.validate_file(csv_file)

        # Should still be valid (warnings don't fail validation)
        assert result.is_valid is True
        assert any("Warning" in err for err in result.errors)
        assert any("unknown" in err.lower() for err in result.errors)

    def test_validate_large_sample(self, csv_dir: Path) -> None:
        """Test validation samples first 100 rows."""
        csv_file = csv_dir / "large.csv"
        rows = [
            {"sku": f"SKU-{i:05d}", "name": f"Product {i}"}
            for i in range(1, 201)  # 200 rows
        ]
        create_csv_file(csv_file, ["sku", "name"], rows)

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is True
        assert result.total_rows == 200
        assert result.sample_size == 100  # Only first 100 validated

    def test_validate_whitespace_trimming(self, csv_dir: Path) -> None:
        """Test that whitespace in SKU and name is handled correctly."""
        csv_file = csv_dir / "whitespace.csv"
        create_csv_file(
            csv_file,
            ["sku", "name"],
            [
                {"sku": "  SKU-001  ", "name": "  Product 1  "},  # Whitespace
                {"sku": "SKU-002", "name": "Product 2"},  # No whitespace
            ],
        )

        result = CSVValidator.validate_file(csv_file)

        # Should be valid as CSVProductRow strips whitespace
        assert result.is_valid is True

    def test_validate_malformed_csv(self, csv_dir: Path) -> None:
        """Test validation handles malformed CSV gracefully."""
        csv_file = csv_dir / "malformed.csv"
        # Create CSV with missing required field values (which will fail validation)
        # Note: csv module is lenient, so we test validation errors instead
        csv_file.write_text('sku,name\n,Product1\n')  # Missing SKU

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        # Should have validation error for empty SKU
        assert len(result.errors) > 0

    def test_validate_invalid_encoding(self, csv_dir: Path) -> None:
        """Test validation handles non-UTF8 files."""
        csv_file = csv_dir / "invalid_encoding.csv"
        # Write non-UTF8 bytes
        csv_file.write_bytes(b"\xff\xfe\xfd")

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        # Should fail with encoding or parsing error
        assert len(result.errors) > 0

    def test_validate_stops_after_max_errors(self, csv_dir: Path) -> None:
        """Test that validation stops after collecting 10 errors."""
        csv_file = csv_dir / "many_errors.csv"
        # Create CSV with many empty SKUs
        rows = [{"sku": "", "name": f"Product {i}"} for i in range(1, 21)]
        create_csv_file(csv_file, ["sku", "name"], rows)

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        # Should stop at 10 errors + 1 message about stopping
        assert len(result.errors) <= 11
        assert any("stopped after 10 errors" in err for err in result.errors)

    def test_validate_sku_length(self, csv_dir: Path) -> None:
        """Test validation enforces SKU length constraints."""
        csv_file = csv_dir / "long_sku.csv"
        long_sku = "S" * 300  # 300 characters (max is 255)
        create_csv_file(
            csv_file,
            ["sku", "name"],
            [{"sku": long_sku, "name": "Product 1"}],
        )

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        assert any("sku" in err.lower() for err in result.errors)

    def test_validate_only_whitespace_fields(self, csv_dir: Path) -> None:
        """Test validation fails when fields contain only whitespace."""
        csv_file = csv_dir / "whitespace_only.csv"
        create_csv_file(
            csv_file,
            ["sku", "name"],
            [
                {"sku": "   ", "name": "Product 1"},  # Whitespace-only SKU
                {"sku": "SKU-001", "name": "   "},  # Whitespace-only name
            ],
        )

        result = CSVValidator.validate_file(csv_file)

        assert result.is_valid is False
        # After stripping, these become empty strings
        assert any("sku" in err.lower() for err in result.errors)


class TestParseBool:
    """Test suite for boolean parsing helper."""

    def test_parse_bool_true_values(self) -> None:
        """Test parsing of various true values."""
        true_values = ["true", "True", "TRUE", "yes", "YES", "1", "t", "T", "y", "Y"]
        for value in true_values:
            assert CSVValidator._parse_bool(value) is True

    def test_parse_bool_false_values(self) -> None:
        """Test parsing of various false values."""
        false_values = [
            "false",
            "False",
            "FALSE",
            "no",
            "NO",
            "0",
            "f",
            "F",
            "n",
            "N",
        ]
        for value in false_values:
            assert CSVValidator._parse_bool(value) is False

    def test_parse_bool_already_bool(self) -> None:
        """Test parsing when value is already a boolean."""
        assert CSVValidator._parse_bool(True) is True
        assert CSVValidator._parse_bool(False) is False

    def test_parse_bool_invalid_value(self) -> None:
        """Test parsing raises error for invalid values."""
        with pytest.raises(ValueError, match="Cannot parse"):
            CSVValidator._parse_bool("invalid")

        with pytest.raises(ValueError):
            CSVValidator._parse_bool("maybe")

        with pytest.raises(ValueError):
            CSVValidator._parse_bool(123)


class TestValidationResult:
    """Test suite for ValidationResult dataclass."""

    def test_validation_result_creation(self) -> None:
        """Test creating ValidationResult instances."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            total_rows=100,
            sample_size=100,
        )

        assert result.is_valid is True
        assert result.errors == []
        assert result.total_rows == 100
        assert result.sample_size == 100

    def test_validation_result_defaults(self) -> None:
        """Test ValidationResult uses defaults correctly."""
        result = ValidationResult(is_valid=False, errors=["Error 1"])

        assert result.is_valid is False
        assert result.errors == ["Error 1"]
        assert result.total_rows == 0
        assert result.sample_size == 0

