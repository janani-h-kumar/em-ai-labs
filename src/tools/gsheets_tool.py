# ============================================================
# sheets_tool.py — Google Sheets Read/Write Tool
# Place at: C:\Workspace\em-ai-labs\src\tools\sheets_tool.py
#
# Dependencies:
#   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
#
# This tool is MODEL-AGNOSTIC and AGENT-AGNOSTIC.
# It does NOT import or instantiate any LLM client.
# It exposes pure data operations — the orchestrator decides when to call what.
#
# Pre-requisites (one-time setup):
#   1. Go to https://console.cloud.google.com
#   2. Create a project → enable Google Sheets API + Google Drive API
#   3. Create OAuth2 credentials (Desktop App) → download as credentials.json
#   4. Place credentials.json in: C:\Workspace\em-ai-labs\config\credentials.json
#   5. On first run, a browser window opens for you to log in and approve access.
#      A token.json is saved alongside credentials.json for future runs.
#   6. Share your Google Sheet with the Gmail IDs who should have access.
#      Access control is entirely managed by Google — no one else can open it.
#
# Expected Sheet structure (create these tabs manually):
#   - Transactions  : raw transaction rows
#   - Summary       : monthly aggregates (written by this tool)
#   - Config        : budget limits, reference data (managed by you)
#
# Usage:
#   from src.tools.sheets_tool import SheetsClient
#
#   client = SheetsClient(spreadsheet_id="your_sheet_id_here")
#
#   client.append_transactions(transactions)        # list of dicts from vision_extractor
#   client.read_transactions(month="2026-05")       # filter by month, or all if omitted
#   client.update_transaction(row_index=5, data={}) # update a specific row by index
#   client.write_summary(summary_rows)              # overwrite the Summary tab
#   client.read_summary()                           # read the Summary tab
#   client.read_config()                            # read the Config tab
# ============================================================

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ============================================================
# Constants
# ============================================================

# If you change these scopes, delete token.json and re-authenticate.
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
_CREDENTIALS_PATH = _CONFIG_DIR / "credentials.json"
_TOKEN_PATH = _CONFIG_DIR / "token.json"

# Tab names — must match exactly what you named them in the Sheet
_TAB_TRANSACTIONS = "Transactions"
_TAB_SUMMARY = "Summary"
_TAB_CONFIG = "Config"

# Column order for the Transactions tab
_TRANSACTION_COLUMNS = [
    "date",
    "merchant",
    "amount",
    "currency",
    "type",
    "category",
    "category_source",
    "description",
    "confidence",
    "notes",
    "source_file",
]


# ============================================================
# SheetsClient
# ============================================================


class SheetsClient:
    """
    Thin, deterministic wrapper around the Google Sheets API.
    One instance per spreadsheet. Re-use across calls.

    Args:
        spreadsheet_id : the ID from your Sheet URL
                         https://docs.google.com/spreadsheets/d/<THIS_PART>/edit
    """

    def __init__(self, spreadsheet_id: str):
        if not spreadsheet_id:
            raise ValueError("spreadsheet_id is required.")
        self._spreadsheet_id = spreadsheet_id
        self._service = self._build_service()

    # --------------------------------------------------------
    # PUBLIC — Transactions tab
    # --------------------------------------------------------

    def append_transactions(self, transactions: list[dict]) -> int:
        """
        Append a list of transaction dicts to the Transactions tab.
        Writes the header row first if the tab is empty.

        Args:
            transactions : list of dicts — matches vision_extractor output schema

        Returns:
            Number of rows successfully appended.
        """
        if not transactions:
            return 0

        # Write header if sheet is empty
        if self._is_tab_empty(_TAB_TRANSACTIONS):
            self._write_header(_TAB_TRANSACTIONS, _TRANSACTION_COLUMNS)

        rows = [self._transaction_to_row(t) for t in transactions]
        self._append_rows(_TAB_TRANSACTIONS, rows)

        # FIXED G004: Swapped out f-string for standard log parameterization
        logger.info("Appended %d transaction(s) to '%s'", len(rows), _TAB_TRANSACTIONS)
        return len(rows)

    def read_transactions(self, month: str | None = None) -> list[dict]:
        """
        Read all transactions from the Transactions tab.

        Args:
            month : optional filter in "YYYY-MM" format e.g. "2026-05"
                    If omitted, all rows are returned.

        Returns:
            List of transaction dicts (same schema as vision_extractor output).
        """
        rows = self._read_rows(_TAB_TRANSACTIONS)
        if not rows or len(rows) < 2:
            return []

        header = rows[0]
        data = [self._row_to_dict(header, row) for row in rows[1:]]

        if month:
            data = [
                t for t in data if isinstance(t.get("date"), str) and t["date"].startswith(month)
            ]

        return data

    def update_transaction(self, row_index: int, data: dict) -> bool:
        """
        Update a specific transaction row by its 1-based data row index
        (row 1 = first data row after header).

        Args:
            row_index : 1-based index of the data row to update (not counting header)
            data      : dict of fields to update — only provided keys are changed

        Returns:
            True if successful, False otherwise.
        """
        rows = self._read_rows(_TAB_TRANSACTIONS)
        if not rows or len(rows) < 2:
            raise ValueError("Transactions tab is empty or has no data rows.")

        header = rows[0]
        sheet_row_number = row_index + 1  # +1 to account for header row

        if sheet_row_number > len(rows):
            raise IndexError(
                f"row_index {row_index} is out of range. Tab has {len(rows) - 1} data row(s)."
            )

        existing = self._row_to_dict(header, rows[sheet_row_number - 1])
        existing.update(data)
        updated_row = self._transaction_to_row(existing)

        range_notation = f"{_TAB_TRANSACTIONS}!A{sheet_row_number}"
        self._service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=range_notation,
            valueInputOption="USER_ENTERED",
            body={"values": [updated_row]},
        ).execute()

        # FIXED G004: Swapped out f-string for standard log parameterization
        logger.info("Updated row %d in '%s'", row_index, _TAB_TRANSACTIONS)
        return True

    # --------------------------------------------------------
    # PUBLIC — Summary tab
    # --------------------------------------------------------

    def write_summary(self, summary_rows: list[dict]) -> None:
        """
        Overwrite the Summary tab with fresh aggregated data.
        Clears the tab first, then writes header + rows.

        Args:
            summary_rows : list of dicts — expected keys:
                           month, category, total_debit, total_credit, transaction_count
        """
        if not summary_rows:
            return

        header = ["month", "category", "total_debit", "total_credit", "transaction_count"]
        rows = [
            [
                row.get("month", ""),
                row.get("category", ""),
                row.get("total_debit", 0),
                row.get("total_credit", 0),
                row.get("transaction_count", 0),
            ]
            for row in summary_rows
        ]

        self._clear_tab(_TAB_SUMMARY)
        self._write_header(_TAB_SUMMARY, header)
        self._append_rows(_TAB_SUMMARY, rows)

        # FIXED G004: Swapped out f-string for standard log parameterization
        logger.info("Written %d summary row(s) to '%s'", len(rows), _TAB_SUMMARY)

    def read_summary(self) -> list[dict]:
        """
        Read all rows from the Summary tab.

        Returns:
            List of dicts with keys: month, category, total_debit, total_credit, transaction_count
        """
        rows = self._read_rows(_TAB_SUMMARY)
        if not rows or len(rows) < 2:
            return []

        header = rows[0]
        return [self._row_to_dict(header, row) for row in rows[1:]]

    # --------------------------------------------------------
    # PUBLIC — Config tab
    # --------------------------------------------------------

    def read_config(self) -> list[dict]:
        """
        Read all rows from the Config tab as a list of dicts.
        The first row is treated as the header.

        Returns:
            List of dicts keyed by column headers.
        """
        rows = self._read_rows(_TAB_CONFIG)
        if not rows or len(rows) < 2:
            return []

        header = rows[0]
        return [self._row_to_dict(header, row) for row in rows[1:]]

    # --------------------------------------------------------
    # INTERNAL — Low-level Sheets API helpers
    # --------------------------------------------------------

    def _read_rows(self, tab_name: str) -> list[list]:
        """Read all rows from a tab. Returns list of lists (raw values)."""
        try:
            result = (
                self._service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self._spreadsheet_id,
                    range=tab_name,
                )
                .execute()
            )
            return result.get("values", [])
        except HttpError:
            # FIXED G201 / G004: Swapped manual error logging out for native exception capture tracking
            logger.exception("Could not read tab '%s'", tab_name)
            return []

    def _append_rows(self, tab_name: str, rows: list[list]) -> None:
        """Append rows to a tab."""
        self._service.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def _write_header(self, tab_name: str, columns: list[str]) -> None:
        """Write the header row to a tab."""
        self._service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [columns]},
        ).execute()

    def _clear_tab(self, tab_name: str) -> None:
        """Clear all content from a tab."""
        self._service.spreadsheets().values().clear(
            spreadsheetId=self._spreadsheet_id,
            range=tab_name,
        ).execute()

    def _is_tab_empty(self, tab_name: str) -> bool:
        """Return True if the tab has no data."""
        rows = self._read_rows(tab_name)
        return len(rows) == 0

    # --------------------------------------------------------
    # INTERNAL — Row serialisation helpers
    # --------------------------------------------------------

    def _transaction_to_row(self, txn: dict) -> list:
        """Convert a transaction dict to an ordered list matching _TRANSACTION_COLUMNS."""
        return [str(txn.get(col, "") or "") for col in _TRANSACTION_COLUMNS]

    def _row_to_dict(self, header: list, row: list) -> dict:
        """Zip a header row and a data row into a dict. Pads short rows with empty strings."""
        padded = row + [""] * (len(header) - len(row))
        return dict(zip(header, padded, strict=False))

    # --------------------------------------------------------
    # INTERNAL — OAuth2 authentication
    # --------------------------------------------------------

    def _build_service(self):
        """
        Build and return an authenticated Google Sheets API service.
        On first run: opens browser for OAuth2 consent, saves token.json.
        On subsequent runs: loads token.json, refreshes silently if expired.
        """
        if not _CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"credentials.json not found at: {_CREDENTIALS_PATH}\n"
                "Download it from Google Cloud Console → APIs & Services → Credentials."
            )

        creds = None

        if _TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS_PATH), _SCOPES)
                # Opens browser once for user consent
                creds = flow.run_local_server(port=0)

            # Save token for next run
            _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

        return build("sheets", "v4", credentials=creds)
