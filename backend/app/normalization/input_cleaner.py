"""
ForgeIQ Input Cleaning Service
Centralized cleaning for all raw product input before pipeline processing.
"""
import re
from typing import Optional
from pydantic import BaseModel


class CleanedInput(BaseModel):
    """Result of cleaning a single raw input value."""
    raw_value: Optional[str] = None
    cleaned_value: Optional[str] = None
    was_placeholder: bool = False
    was_empty: bool = False


class CleanedProductInput(BaseModel):
    """Result of cleaning all product input fields."""
    part_number: CleanedInput
    brand: CleanedInput
    manufacturer: CleanedInput
    description: CleanedInput
    category: CleanedInput


# Known placeholder strings that should become None
PLACEHOLDER_VALUES = {
    "-- unbranded --",
    "-- no unilog brand --",
    "-- no dib brand --",
    "-- no brand --",
    "-- no manufacturer --",
    "n/a",
    "na",
    "none",
    "unknown",
    "tbd",
    "not specified",
    "unspecified",
    "not available",
    "null",
    "-",
    "--",
    ".",
    "...",
    "???",
}


class InputCleaningService:
    """
    Centralized input-cleaning service.
    Handles whitespace, casing, punctuation, nulls, and placeholder values.
    """

    def clean_product_input(
        self,
        part_number: Optional[str] = None,
        brand: Optional[str] = None,
        manufacturer: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
    ) -> CleanedProductInput:
        """Clean all product input fields in one pass."""
        return CleanedProductInput(
            part_number=self.clean_part_number(part_number),
            brand=self.clean_brand_or_manufacturer(brand),
            manufacturer=self.clean_brand_or_manufacturer(manufacturer),
            description=self.clean_description(description),
            category=self.clean_category(category),
        )

    def clean_part_number(self, raw: Optional[str]) -> CleanedInput:
        """Clean MPN: strip whitespace, normalize dashes/slashes, uppercase."""
        if raw is None:
            return CleanedInput(raw_value=None, cleaned_value=None, was_empty=True)

        stripped = raw.strip()
        if not stripped or self._is_placeholder(stripped):
            return CleanedInput(
                raw_value=raw,
                cleaned_value=None,
                was_placeholder=self._is_placeholder(stripped),
                was_empty=not stripped,
            )

        # Collapse internal whitespace
        cleaned = re.sub(r'\s+', ' ', stripped)
        # Remove control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)

        return CleanedInput(raw_value=raw, cleaned_value=cleaned)

    def clean_brand_or_manufacturer(self, raw: Optional[str]) -> CleanedInput:
        """Clean brand/manufacturer: strip, detect placeholders, normalize casing."""
        if raw is None:
            return CleanedInput(raw_value=None, cleaned_value=None, was_empty=True)

        stripped = raw.strip()
        if not stripped:
            return CleanedInput(raw_value=raw, cleaned_value=None, was_empty=True)

        if self._is_placeholder(stripped):
            return CleanedInput(
                raw_value=raw,
                cleaned_value=None,
                was_placeholder=True,
            )

        # Collapse internal whitespace
        cleaned = re.sub(r'\s+', ' ', stripped)
        # Remove control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)

        return CleanedInput(raw_value=raw, cleaned_value=cleaned)

    def clean_description(self, raw: Optional[str]) -> CleanedInput:
        """Clean description: collapse spaces, remove control chars."""
        if raw is None:
            return CleanedInput(raw_value=None, cleaned_value=None, was_empty=True)

        stripped = raw.strip()
        if not stripped:
            return CleanedInput(raw_value=raw, cleaned_value=None, was_empty=True)

        if self._is_placeholder(stripped):
            return CleanedInput(
                raw_value=raw,
                cleaned_value=None,
                was_placeholder=True,
            )

        # Collapse multiple whitespace
        cleaned = re.sub(r'\s+', ' ', stripped)
        # Remove control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', cleaned)

        return CleanedInput(raw_value=raw, cleaned_value=cleaned)

    def clean_category(self, raw: Optional[str]) -> CleanedInput:
        """Clean category: strip, detect placeholders."""
        if raw is None:
            return CleanedInput(raw_value=None, cleaned_value=None, was_empty=True)

        stripped = raw.strip()
        if not stripped or self._is_placeholder(stripped):
            return CleanedInput(
                raw_value=raw,
                cleaned_value=None,
                was_placeholder=self._is_placeholder(stripped) if stripped else False,
                was_empty=not stripped,
            )

        cleaned = re.sub(r'\s+', ' ', stripped)
        return CleanedInput(raw_value=raw, cleaned_value=cleaned)

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        """Check if a value is a known placeholder."""
        return value.lower().strip() in PLACEHOLDER_VALUES


_default_input_cleaner: Optional[InputCleaningService] = None


def get_input_cleaning_service() -> InputCleaningService:
    global _default_input_cleaner
    if _default_input_cleaner is None:
        _default_input_cleaner = InputCleaningService()
    return _default_input_cleaner
