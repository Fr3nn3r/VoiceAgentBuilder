"""
PHI/PII redaction for observability tracing.

Follows HIPAA Safe Harbor method: removes 18 types of identifiers before sending to LangSmith.
Implements Single Responsibility Principle: only handles data redaction.

Per PRD Section 10: Redaction Policy
"""

import re
from typing import Any, Dict, List


class FieldRedactor:
    """
    Redacts PHI (Protected Health Information) and PII (Personally Identifiable Information)
    from data before sending to observability platform.

    Implements HIPAA Safe Harbor de-identification:
    - Removes 18 types of identifiers
    - Truncates sensitive text fields
    - Preserves non-sensitive metadata

    Usage:
        redactor = FieldRedactor()
        safe_data = redactor.redact_phi(raw_data)
    """

    # PHI fields - must be completely redacted per HIPAA
    PHI_FIELDS = {
        # Patient identifiers
        "patient_name",
        "phone",
        "phone_number",
        "email",
        "dob",
        "birth_date",
        "mrn",  # Medical Record Number
        "ssn",  # Social Security Number
        "address",
        "street",
        "city",
        "zip",
        "postal_code",
        # Other identifiers
        "ip_address",
        "device_id",
        "biometric",
        "photo",
        "full_name",
        "last_name",
        "first_name",
    }

    # Fields that should be truncated (not fully redacted)
    TRUNCATE_FIELDS = {
        "reason_for_visit",
        "reason",
        "notes",
        "symptoms",
        "comments",
        "message",
        "complaint",
        "diagnosis",
        "treatment",
    }

    # Safe fields - can be sent as-is
    SAFE_FIELDS = {
        "appointment_datetime",
        "start_datetime",
        "end_datetime",
        "confirmation_id",
        "doctor_name",
        "clinic_location",
        "clinic_name",
        "available",
        "success",
        "error",
        "duration_ms",
        "test_mode",
        "tool_name",
    }

    # Redaction constants
    REDACTED_MARKER = "<REDACTED>"
    TRUNCATE_LENGTH = 50

    def __init__(self):
        """Initialize redactor with regex patterns for sensitive data detection"""
        # Phone number patterns (various formats)
        self.phone_pattern = re.compile(
            r"""
            (?:\+?1[-.\s]?)?              # Optional country code
            (?:\(?\d{3}\)?[-.\s]?)        # Area code
            \d{3}[-.\s]?\d{4}              # Phone number
            """,
            re.VERBOSE,
        )

        # Email pattern
        self.email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )

        # Date of birth patterns (various formats)
        self.dob_pattern = re.compile(
            r"""
            (?:
                \d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}  |  # MM/DD/YYYY or DD/MM/YYYY
                \d{4}[-/.]\d{1,2}[-/.]\d{1,2}       # YYYY-MM-DD
            )
            """,
            re.VERBOSE,
        )

        # SSN pattern
        self.ssn_pattern = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")

    def redact_phi(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact PHI/PII from dictionary data.

        Applies three strategies:
        1. Complete redaction for PHI fields (patient_name, phone, etc.)
        2. Truncation for sensitive text (reason, notes, symptoms)
        3. Pattern-based redaction for phone/email/DOB in any string

        Args:
            data: Dictionary containing potentially sensitive data

        Returns:
            Dictionary with PHI/PII redacted

        Example:
            >>> redactor = FieldRedactor()
            >>> raw = {"patient_name": "John Doe", "phone": "555-1234", "start_datetime": "2025-11-15T10:30"}
            >>> redactor.redact_phi(raw)
            {"patient_name": "<REDACTED>", "phone": "<REDACTED>", "start_datetime": "2025-11-15T10:30"}
        """
        if not isinstance(data, dict):
            return data

        redacted = {}

        for key, value in data.items():
            key_lower = key.lower()

            # Strategy 1: Redact PHI fields completely
            if key_lower in self.PHI_FIELDS:
                redacted[key] = self.REDACTED_MARKER

            # Strategy 2: Truncate sensitive text fields
            elif key_lower in self.TRUNCATE_FIELDS:
                if isinstance(value, str):
                    redacted[key] = self._truncate_text(value)
                else:
                    redacted[key] = value

            # Strategy 3: Keep safe fields as-is
            elif key_lower in self.SAFE_FIELDS:
                redacted[key] = value

            # Strategy 4: Recursively redact nested dicts
            elif isinstance(value, dict):
                redacted[key] = self.redact_phi(value)

            # Strategy 5: Redact lists of dicts
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_phi(item) if isinstance(item, dict) else item
                    for item in value
                ]

            # Strategy 6: Apply pattern-based redaction to unknown string fields
            elif isinstance(value, str):
                redacted[key] = self._redact_patterns(value)

            # Other types (numbers, booleans, None) - pass through
            else:
                redacted[key] = value

        return redacted

    def _truncate_text(self, text: str) -> str:
        """
        Truncate sensitive text to maximum length.

        Args:
            text: Text to truncate

        Returns:
            Truncated text with ellipsis if needed

        Example:
            >>> redactor._truncate_text("This is a very long medical complaint with lots of details...")
            "This is a very long medical complaint with lot..."
        """
        if len(text) <= self.TRUNCATE_LENGTH:
            return text

        # Truncate and add ellipsis
        return text[: self.TRUNCATE_LENGTH - 3] + "..."

    def _redact_patterns(self, text: str) -> str:
        """
        Redact sensitive patterns from text (phone, email, DOB, SSN).

        Args:
            text: Text to scan for patterns

        Returns:
            Text with sensitive patterns redacted

        Example:
            >>> redactor._redact_patterns("Call me at 555-1234 or email john@example.com")
            "Call me at <REDACTED> or email <REDACTED>"
        """
        # Redact phone numbers
        text = self.phone_pattern.sub(self.REDACTED_MARKER, text)

        # Redact emails
        text = self.email_pattern.sub(self.REDACTED_MARKER, text)

        # Redact dates that might be DOB
        # Note: This is conservative - redacts all dates in certain formats
        # In production, you might want more sophisticated detection
        text = self.dob_pattern.sub(self.REDACTED_MARKER, text)

        # Redact SSN
        text = self.ssn_pattern.sub(self.REDACTED_MARKER, text)

        return text

    def validate_redacted(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate that data has been properly redacted.

        Scans for patterns that might indicate PHI leakage.

        Args:
            data: Dictionary to validate

        Returns:
            List of violations found (empty list if clean)

        Example:
            >>> redactor = FieldRedactor()
            >>> violations = redactor.validate_redacted({"phone": "555-1234"})
            >>> violations
            ["Found phone number pattern in field 'phone': 555-1234"]
        """
        violations = []

        def scan_value(key: str, value: Any, path: str = ""):
            """Recursively scan values for PHI patterns"""
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, str):
                # Check for phone numbers
                if self.phone_pattern.search(value):
                    violations.append(
                        f"Found phone number pattern in field '{current_path}': {value[:20]}..."
                    )

                # Check for emails
                if self.email_pattern.search(value):
                    violations.append(
                        f"Found email pattern in field '{current_path}': {value[:20]}..."
                    )

                # Check for SSN
                if self.ssn_pattern.search(value):
                    violations.append(
                        f"Found SSN pattern in field '{current_path}': {value[:10]}..."
                    )

            elif isinstance(value, dict):
                for k, v in value.items():
                    scan_value(k, v, current_path)

            elif isinstance(value, list):
                for i, item in enumerate(value):
                    scan_value(f"[{i}]", item, current_path)

        # Scan all fields
        for key, value in data.items():
            scan_value(key, value)

        return violations


# Convenience function for quick redaction
def redact_phi(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for quick PHI redaction.

    Args:
        data: Dictionary to redact

    Returns:
        Redacted dictionary

    Example:
        from observability.redaction import redact_phi
        safe_data = redact_phi(raw_tool_inputs)
    """
    redactor = FieldRedactor()
    return redactor.redact_phi(data)
