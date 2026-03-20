import json
import re
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class ScreenerSection:
    name: str
    headers: List[str]
    rows: List[Dict[str, Any]]


class ScreenerScraper:
    """
    Scrapes financial statement tables from Screener company pages.

    Supported sections:
    - Profit & Loss
    - Balance Sheet
    - Cash Flow
    - Shareholding Pattern

    Notes:
    - Uses the public company page HTML.
    - Works best for URLs like:
      https://www.screener.in/company/<TICKER>/consolidated/
      or
      https://www.screener.in/company/<TICKER>/
    """

    BASE_URL = "https://www.screener.in/company/{ticker}/{mode}/"

    def __init__(self, session: Optional[requests.Session] = None, delay_seconds: float = 1.5):
        self.session = session or requests.Session()
        self.delay_seconds = delay_seconds
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.screener.in/",
            }
        )

    def build_url(self, ticker: str, consolidated: bool = True) -> str:
        mode = "consolidated" if consolidated else ""
        return self.BASE_URL.format(ticker=ticker.upper(), mode=mode).replace("//", "/").replace("https:/", "https://")

    def fetch_page(self, ticker: str, consolidated: bool = True) -> BeautifulSoup:
        url = self.build_url(ticker, consolidated=consolidated)
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        time.sleep(self.delay_seconds)
        return BeautifulSoup(response.text, "html.parser")

    def scrape_ticker(self, ticker: str, consolidated: bool = True) -> Dict[str, Any]:
        soup = self.fetch_page(ticker, consolidated=consolidated)

        result = {
            "ticker": ticker.upper(),
            "url": self.build_url(ticker, consolidated=consolidated),
            "statement_type": "consolidated" if consolidated else "standalone",
            "company_name": self._extract_company_name(soup),
            "profit_and_loss": self._extract_section_table(
                soup,
                possible_ids=["profit-loss", "profit-and-loss"],
                fallback_keywords=["Profit & Loss", "Profit and Loss"],
            ),
            "balance_sheet": self._extract_section_table(
                soup,
                possible_ids=["balance-sheet"],
                fallback_keywords=["Balance Sheet"],
            ),
            "cash_flow": self._extract_section_table(
                soup,
                possible_ids=["cash-flow", "cash-flows"],
                fallback_keywords=["Cash Flow", "Cash Flows"],
            ),
            "shareholding_pattern": self._extract_shareholding_table(
                soup,
                possible_ids=["shareholding"],
                fallback_keywords=["Shareholding Pattern", "Shareholding"],
            ),
        }

        return result

    def save_json(self, data: Dict[str, Any], filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _extract_company_name(self, soup: BeautifulSoup) -> Optional[str]:
        # Company title commonly appears as h1 on Screener company page
        h1 = soup.find("h1")
        if h1:
            return self._clean_text(h1.get_text(" ", strip=True))
        return None

    def _extract_section_table(
        self,
        soup: BeautifulSoup,
        possible_ids: List[str],
        fallback_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a section by id or nearby heading text and extracts the first table under it.
        Returns a dict with headers + row records.
        """
        section = self._find_section_container(soup, possible_ids, fallback_keywords)
        if not section:
            return None

        table = section.find("table")
        if not table:
            # fallback: maybe next sibling table
            table = self._find_next_table(section)

        if not table:
            return None

        return self._parse_html_table(table)

    def _extract_shareholding_table(
        self,
        soup: BeautifulSoup,
        possible_ids: List[str],
        fallback_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        section = self._find_section_container(soup, possible_ids, fallback_keywords)
        if not section:
            return None

        # Shareholding may have one or more tables. Collect all.
        tables = section.find_all("table")
        if not tables:
            next_table = self._find_next_table(section)
            tables = [next_table] if next_table else []

        parsed_tables = []
        for table in tables:
            if table:
                parsed = self._parse_html_table(table)
                if parsed and parsed["rows"]:
                    parsed_tables.append(parsed)

        if not parsed_tables:
            return None

        return {
            "tables": parsed_tables
        }

    def _find_section_container(
        self,
        soup: BeautifulSoup,
        possible_ids: List[str],
        fallback_keywords: List[str],
    ) -> Optional[BeautifulSoup]:
        # 1) Direct id match
        for section_id in possible_ids:
            node = soup.find(id=section_id)
            if node:
                return node

        # 2) Anchor href match like #balance-sheet, #cash-flow
        for section_id in possible_ids:
            anchor = soup.find("a", href=re.compile(rf"#{re.escape(section_id)}$"))
            if anchor:
                candidate = anchor.find_parent(["section", "div"])
                if candidate:
                    return candidate

        # 3) Text heading fallback
        headings = soup.find_all(re.compile("^h[1-6]$"))
        for heading in headings:
            text = self._clean_text(heading.get_text(" ", strip=True))
            if any(keyword.lower() in text.lower() for keyword in fallback_keywords):
                parent = heading.find_parent(["section", "div"])
                if parent:
                    return parent

        # 4) Generic text scan fallback
        text_nodes = soup.find_all(string=True)
        for node in text_nodes:
            text = self._clean_text(str(node))
            if any(keyword.lower() == text.lower() for keyword in fallback_keywords):
                parent = node.parent
                if parent:
                    container = parent.find_parent(["section", "div"])
                    if container:
                        return container

        return None

    def _find_next_table(self, node):
        current = node
        for _ in range(8):
            current = current.find_next()
            if current is None:
                break
            if getattr(current, "name", None) == "table":
                return current
        return None

    def _parse_html_table(self, table) -> Dict[str, Any]:
        headers = self._extract_headers(table)
        rows = []

        body_rows = table.find_all("tr")
        for tr in body_rows:
            cells = tr.find_all(["td", "th"])
            values = [self._clean_text(cell.get_text(" ", strip=True)) for cell in cells]

            if not values:
                continue

            # skip duplicate header row
            if headers and values == headers:
                continue

            if headers and len(values) <= len(headers):
                row_dict = {}
                for idx, header in enumerate(headers[: len(values)]):
                    row_dict[header] = values[idx]
                rows.append(row_dict)
            else:
                rows.append({"values": values})

        return {
            "headers": headers,
            "rows": rows,
        }

    def _extract_headers(self, table) -> List[str]:
        # Prefer thead headers
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = [
                    self._clean_text(th.get_text(" ", strip=True))
                    for th in header_row.find_all(["th", "td"])
                ]
                if headers:
                    return headers

        # Fallback to first row
        first_row = table.find("tr")
        if first_row:
            headers = [
                self._clean_text(cell.get_text(" ", strip=True))
                for cell in first_row.find_all(["th", "td"])
            ]
            return headers

        return []

    @staticmethod
    def _clean_text(value: str) -> str:
        value = re.sub(r"\s+", " ", value or "").strip()
        value = value.replace("\xa0", " ")
        return value


def scrape_and_save_ticker(ticker: str, consolidated: bool = True) -> Dict[str, Any]:
    scraper = ScreenerScraper(delay_seconds=1.5)
    data = scraper.scrape_ticker(ticker=ticker, consolidated=consolidated)
    output_file = f"{ticker.upper()}.json"
    scraper.save_json(data, output_file)
    print(f"Saved: {output_file}")
    return data


if __name__ == "__main__":
    # Example:
    # For Bharti Airtel consolidated data
    data = scrape_and_save_ticker("BHARTIARTL", consolidated=True)

    # Optional preview
    print(json.dumps(data, indent=2)[:2000])