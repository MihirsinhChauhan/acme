"""CSV validation service for pre-import checks."""
from __future__ import annotations

import csv
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.product import CSVProductRow


@dataclass
class ValidationResult:
    """Result of CSV validation with error details."""

    is_valid: bool
    errors: list[str]
    total_rows: int = 0
    sample_size: int = 0


class CSVValidator:
    """Validates CSV files before import processing."""

    REQUIRED_HEADERS = {"sku", "name"}
    OPTIONAL_HEADERS = {"description", "active"}
    ALLOWED_HEADERS = REQUIRED_HEADERS | OPTIONAL_HEADERS
    SAMPLE_SIZE = 100
    MAX_FILE_SIZE_MB = 100

    @classmethod
    def validate_file(cls, file_path: str | Path) -> ValidationResult:
        """
        Validate CSV file before enqueueing import task.

        Performs the following checks:
        1. File extension is .csv
        2. File size is within limits
        3. CSV has required headers (sku, name)
        4. Sample first 100 rows for schema validation

        Args:
            file_path: Path to the CSV file to validate

        Returns:
            ValidationResult with validation status and error details
        """
        errors: list[str] = []
        file_path = Path(file_path)

        # Check 1: File extension
        if not file_path.suffix.lower() == ".csv":
            errors.append(f"Invalid file extension: {file_path.suffix}. Expected .csv")
            return ValidationResult(is_valid=False, errors=errors)

        # Check 2: File exists
        if not file_path.exists():
            errors.append(f"File not found: {file_path}")
            return ValidationResult(is_valid=False, errors=errors)

        # Check 3: File size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > cls.MAX_FILE_SIZE_MB:
            errors.append(
                f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({cls.MAX_FILE_SIZE_MB} MB)"
            )
            return ValidationResult(is_valid=False, errors=errors)

        # Check 4: CSV structure and content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                # Validate headers
                if not reader.fieldnames:
                    errors.append("CSV file is empty or has no headers")
                    return ValidationResult(is_valid=False, errors=errors)

                headers = set(reader.fieldnames)
                missing_headers = cls.REQUIRED_HEADERS - headers
                if missing_headers:
                    errors.append(
                        f"Missing required headers: {', '.join(sorted(missing_headers))}. "
                        f"Found: {', '.join(sorted(headers))}"
                    )
                    return ValidationResult(is_valid=False, errors=errors)

                # Check for unknown headers (warn but don't fail)
                unknown_headers = headers - cls.ALLOWED_HEADERS
                if unknown_headers:
                    errors.append(
                        f"Warning: Unknown headers will be ignored: {', '.join(sorted(unknown_headers))}"
                    )

                # Sample first N rows for validation and count rows
                sample_errors, rows_validated = cls._validate_sample_rows(
                    reader, cls.SAMPLE_SIZE
                )
                errors.extend(sample_errors)

                # Count remaining rows (reader position is after sample)
                remaining_rows = sum(1 for _ in reader)
                total_rows = rows_validated + remaining_rows

                # Validation succeeds if only warnings (unknown headers)
                has_critical_errors = any(
                    not err.startswith("Warning:") for err in errors
                )

                return ValidationResult(
                    is_valid=not has_critical_errors,
                    errors=errors,
                    total_rows=total_rows,
                    sample_size=rows_validated,
                )

        except csv.Error as e:
            errors.append(f"CSV parsing error: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors)
        except UnicodeDecodeError as e:
            errors.append(
                f"File encoding error: {str(e)}. File must be UTF-8 encoded"
            )
            return ValidationResult(is_valid=False, errors=errors)
        except Exception as e:
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors)

    @classmethod
    def _validate_sample_rows(
        cls, reader: csv.DictReader, sample_size: int
    ) -> tuple[list[str], int]:
        """
        Validate a sample of CSV rows using Pydantic schema.

        Args:
            reader: CSV DictReader positioned at the start
            sample_size: Number of rows to validate

        Returns:
            Tuple of (validation error messages, number of rows validated)
        """
        errors: list[str] = []
        rows_validated = 0

        # Use islice to take exactly sample_size rows (or fewer if file is smaller)
        for row_num, row in enumerate(itertools.islice(reader, sample_size), start=1):
            rows_validated = row_num

            try:
                # Prepare row data with only allowed fields
                row_data = {k: v for k, v in row.items() if k in cls.ALLOWED_HEADERS}

                # Convert 'active' to boolean if present
                if "active" in row_data:
                    row_data["active"] = cls._parse_bool(row_data["active"])

                # Validate using Pydantic schema
                CSVProductRow(**row_data)

            except ValidationError as e:
                # Extract field-specific errors
                for error in e.errors():
                    field = error["loc"][0] if error["loc"] else "unknown"
                    msg = error["msg"]
                    errors.append(f"Row {row_num}, field '{field}': {msg}")

                # Stop after collecting first 10 errors to avoid overwhelming output
                if len(errors) >= 10:
                    errors.append(
                        f"Validation stopped after 10 errors. Please fix these issues and retry."
                    )
                    break

            except Exception as e:
                errors.append(f"Row {row_num}: Unexpected error - {str(e)}")

        return errors, rows_validated

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        """
        Parse boolean values from CSV strings.

        Accepts: true, yes, 1, t, y (case-insensitive) as True
        Accepts: false, no, 0, f, n (case-insensitive) as False

        Args:
            value: Value to parse

        Returns:
            Boolean value

        Raises:
            ValueError: If value cannot be parsed as boolean
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value_lower = value.strip().lower()
            if value_lower in ("true", "yes", "1", "t", "y"):
                return True
            if value_lower in ("false", "no", "0", "f", "n"):
                return False

        raise ValueError(f"Cannot parse '{value}' as boolean")

