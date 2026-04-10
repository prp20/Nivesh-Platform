import pytest
from pipeline.normalizer import parse_indian_number, normalize_financial_table


class TestParseIndianNumber:
    def test_plain_number(self):
        assert parse_indian_number("87939") == 87939.0

    def test_comma_separated(self):
        assert parse_indian_number("87,939") == 87939.0

    def test_lakh_format(self):
        assert parse_indian_number("1,23,456") == 123456.0

    def test_negative_parens(self):
        assert parse_indian_number("(12,345)") == -12345.0

    def test_percentage(self):
        assert parse_indian_number("12.34%") == 12.34

    def test_empty_string(self):
        assert parse_indian_number("") is None

    def test_dash(self):
        assert parse_indian_number("-") is None

    def test_double_dash(self):
        assert parse_indian_number("--") is None

    def test_na(self):
        assert parse_indian_number("N/A") is None

    def test_zero(self):
        assert parse_indian_number("0") == 0.0

    def test_decimal(self):
        assert parse_indian_number("1,234.56") == 1234.56

    def test_negative_decimal_paren(self):
        assert parse_indian_number("(1,234.56)") == -1234.56


class TestNormalizeTable:
    def test_basic_pl_table(self):
        raw = {
            "headers": ["", "Mar 2023", "Mar 2024"],
            "rows": [
                {"": "Revenue", "Mar 2023": "87,939", "Mar 2024": "1,00,616"},
                {"": "Net Profit", "Mar 2023": "(1,234)", "Mar 2024": "5,678"},
            ]
        }
        result = normalize_financial_table(raw)
        assert result["periods"] == ["Mar 2023", "Mar 2024"]
        assert result["data"]["revenue"] == [87939.0, 100616.0]
        assert result["data"]["net_profit"] == [-1234.0, 5678.0]

    def test_empty_raw(self):
        assert normalize_financial_table({}) == {"periods": [], "data": {}}

    def test_bhartiartl_fixture(self):
        """Validate against real scraper output."""
        import json
        import os
        fixture = os.path.join(os.path.dirname(__file__), "../../BHARTIARTL.json")
        if not os.path.exists(fixture):
            pytest.skip("BHARTIARTL.json not found")
        with open(fixture) as f:
            data = json.load(f)
        result = normalize_financial_table(data["profit_and_loss"])
        assert len(result["periods"]) >= 4
        # BHARTIARTL has "Sales +" not "Revenue"
        assert "sales" in result["data"]
        # Sales should be large positive numbers (Airtel sales are 87,939 Cr+)
        assert all(v is None or v > 0 for v in result["data"]["sales"])
