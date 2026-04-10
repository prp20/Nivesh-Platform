"""
Safe query building utilities for filtering and sorting.

Provides a reusable FilterBuilder class to safely construct parameterized WHERE clauses
and prevent SQL injection while maintaining code DRY principles.
"""

from typing import Optional, Dict, Any, List, Tuple


class FilterBuilder:
    """
    Safe query filter builder using parameterized placeholders.

    Prevents SQL injection by enforcing:
    1. All values are parameterized (passed separately from SQL)
    2. Column names and operators come from predefined maps
    3. No f-string interpolation of user input

    Example:
        builder = FilterBuilder()
        builder.add("s.sector", "=", sector_value, "sector")
        builder.add("r.pe_ratio", ">=", min_pe_value, "min_pe")
        where_clause = builder.build_where()  # Returns: "s.sector = :sector AND r.pe_ratio >= :min_pe"
        params = builder.get_params()         # Returns: {"sector": sector_value, "min_pe": min_pe_value}
    """

    def __init__(self, base_filters: Optional[List[str]] = None):
        """
        Initialize filter builder.

        Args:
            base_filters: Optional list of base filter strings (e.g., ["s.is_active = TRUE"])
        """
        self.filters: List[str] = base_filters or []
        self.params: Dict[str, Any] = {}

    def add(
        self,
        column: str,
        operator: str,
        value: Optional[Any],
        param_key: str,
    ) -> "FilterBuilder":
        """
        Add a filter clause if value is not None.

        Args:
            column: Fully qualified column name (e.g., "stocks.sector")
            operator: SQL operator (=, >=, <=, >, <, IN, LIKE, etc.)
            value: Filter value (None is skipped)
            param_key: Parameter placeholder key (e.g., "sector")

        Returns:
            self (for method chaining)
        """
        if value is not None:
            self.filters.append(f"{column} {operator} :{param_key}")
            self.params[param_key] = value
        return self

    def add_range(
        self,
        column: str,
        min_value: Optional[float],
        max_value: Optional[float],
        min_key: str,
        max_key: str,
    ) -> "FilterBuilder":
        """
        Add min/max range filters (validates min <= max).

        Args:
            column: Fully qualified column name
            min_value: Minimum value (None skips min check)
            max_value: Maximum value (None skips max check)
            min_key: Parameter key for minimum
            max_key: Parameter key for maximum

        Returns:
            self (for method chaining)

        Raises:
            ValueError: If min_value > max_value (both not None)
        """
        # Validate range
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(
                f"Invalid range: {min_key}={min_value} > {max_key}={max_value}"
            )

        if min_value is not None:
            self.filters.append(f"{column} >= :{min_key}")
            self.params[min_key] = min_value

        if max_value is not None:
            self.filters.append(f"{column} <= :{max_key}")
            self.params[max_key] = max_value

        return self

    def add_in(
        self,
        column: str,
        values: Optional[List[Any]],
        param_key: str,
    ) -> "FilterBuilder":
        """
        Add an IN filter for multiple values.

        Args:
            column: Fully qualified column name
            values: List of values (None or empty list skips)
            param_key: Parameter placeholder key

        Returns:
            self (for method chaining)
        """
        if values and len(values) > 0:
            placeholders = ", ".join([f":{param_key}_{i}" for i in range(len(values))])
            self.filters.append(f"{column} IN ({placeholders})")
            for i, val in enumerate(values):
                self.params[f"{param_key}_{i}"] = val

        return self

    def add_custom(self, filter_clause: str) -> "FilterBuilder":
        """
        Add a custom WHERE clause (carefully — avoid user input!).

        Only use this for hardcoded, application-defined filters.
        Never pass user input directly.

        Args:
            filter_clause: Raw SQL filter (e.g., "s.is_active = TRUE")

        Returns:
            self (for method chaining)
        """
        self.filters.append(filter_clause)
        return self

    def build_where(self) -> str:
        """
        Build the final WHERE clause by joining all filters with AND.

        Returns:
            WHERE clause string, or "TRUE" if no filters (safe default)
        """
        if not self.filters:
            return "TRUE"
        return " AND ".join(self.filters)

    def get_params(self) -> Dict[str, Any]:
        """Return all parameterized values."""
        return self.params.copy()

    def __str__(self) -> str:
        """Return WHERE clause for debugging."""
        return self.build_where()


class SortColumnMap:
    """
    Safe sorting column mapper.

    Prevents SQL injection in ORDER BY clause by restricting sort columns
    to a predefined allow-list.
    """

    def __init__(self, columns: Dict[str, str]):
        """
        Initialize with allowed column mappings.

        Args:
            columns: Dict mapping {user_input -> sql_column}
                     Example: {"total_score": "sr.total_score", "symbol": "s.symbol"}
        """
        self._columns = columns
        self._default = next(iter(columns.values())) if columns else "1"

    def get_column(self, user_input: str, default: Optional[str] = None) -> str:
        """
        Get SQL column name for user input.

        Args:
            user_input: Requested sort column (user input)
            default: Default column if user_input not found (uses map default if not provided)

        Returns:
            Safe SQL column name from allow-list
        """
        return self._columns.get(user_input, default or self._default)

    def is_valid(self, user_input: str) -> bool:
        """Check if user input is in allow-list."""
        return user_input in self._columns

    def get_default(self) -> str:
        """Get default sort column."""
        return self._default


# Validators for numeric ranges (used in Pydantic models)

def validate_min_max_range(
    min_val: Optional[float], max_val: Optional[float], field_name: str = "range"
) -> None:
    """
    Validate that min <= max (both can be None).

    Args:
        min_val: Minimum value
        max_val: Maximum value
        field_name: Field name for error message

    Raises:
        ValueError: If min_val > max_val
    """
    if min_val is not None and max_val is not None and min_val > max_val:
        raise ValueError(f"{field_name}: min ({min_val}) > max ({max_val})")


def validate_positive(value: Optional[float], field_name: str = "value") -> None:
    """Validate that value is positive or None."""
    if value is not None and value <= 0:
        raise ValueError(f"{field_name}: must be positive, got {value}")


def validate_in_range(
    value: Optional[float],
    min_val: float,
    max_val: float,
    field_name: str = "value",
) -> None:
    """Validate that value is in range [min_val, max_val]."""
    if value is not None and not (min_val <= value <= max_val):
        raise ValueError(
            f"{field_name}: must be between {min_val} and {max_val}, got {value}"
        )
