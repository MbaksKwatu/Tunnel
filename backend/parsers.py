"""
File parsers for PDF, CSV, and XLSX files
"""
import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
import pandas as pd
from typing import List, Dict, Any, Optional
import logging
import io
import time
import httpx
import re

logger = logging.getLogger(__name__)


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", str(key or "").strip().lower())


def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except Exception:
            return None

    s = str(value).strip()
    if not s:
        return None

    s_lower = s.lower()
    sign = 1.0

    if " dr" in f" {s_lower}" or s_lower.endswith("dr"):
        sign = -1.0
    elif " cr" in f" {s_lower}" or s_lower.endswith("cr"):
        sign = 1.0

    if "(" in s and ")" in s:
        sign *= -1.0
        s = s.replace("(", "").replace(")", "")

    if s.endswith("-"):
        sign *= -1.0
        s = s[:-1]

    s = s.replace("$", "").replace(",", "").replace(" ", "")
    s = re.sub(r"[^0-9.+-]", "", s)

    if not s:
        return None

    try:
        return float(s) * sign
    except Exception:
        return None


def _to_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = pd.to_datetime(s, errors='coerce', infer_datetime_format=True)
        if pd.isna(dt):
            return None
        return dt.date().isoformat()
    except Exception:
        return None


def normalize_transaction_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows

    date_aliases = [
        'transaction_date',
        'transaction date',
        'date',
        'posting date',
        'post date',
        'value date',
        'booking date',
        'timestamp',
        'time',
    ]

    amount_aliases = [
        'amount',
        'transaction amount',
        'txn amount',
        'net amount',
        'amt',
        'value',
    ]

    debit_aliases = ['debit', 'dr', 'withdrawal', 'outflow', 'money out']
    credit_aliases = ['credit', 'cr', 'deposit', 'inflow', 'money in']

    normalized: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            normalized.append(row)
            continue

        out = dict(row)
        key_map = { _normalize_key(k): k for k in row.keys() }

        date_val = None
        for alias in date_aliases:
            src_key = key_map.get(alias)
            if src_key is None:
                continue
            date_val = row.get(src_key)
            if date_val not in (None, ''):
                break

        out['transaction_date'] = _to_iso_date(date_val)

        amount_val = None
        for alias in amount_aliases:
            src_key = key_map.get(alias)
            if src_key is None:
                continue
            amount_val = row.get(src_key)
            if amount_val not in (None, ''):
                break

        amount_num = _to_number(amount_val)

        if amount_num is None:
            debit_val = None
            credit_val = None
            for alias in debit_aliases:
                src_key = key_map.get(alias)
                if src_key is not None:
                    debit_val = row.get(src_key)
                    if debit_val not in (None, ''):
                        break
            for alias in credit_aliases:
                src_key = key_map.get(alias)
                if src_key is not None:
                    credit_val = row.get(src_key)
                    if credit_val not in (None, ''):
                        break

            debit_num = _to_number(debit_val)
            credit_num = _to_number(credit_val)

            if debit_num is not None or credit_num is not None:
                amount_num = float(credit_num or 0.0) - float(debit_num or 0.0)

        out['amount'] = amount_num
        normalized.append(out)

    return normalized


class PasswordRequiredError(Exception):
    """Raised when a file requires a password to open"""
    pass


class PartialParseError(Exception):
    def __init__(
        self,
        *,
        rows: List[Dict[str, Any]],
        error_code: str,
        error_message: str,
        next_action: str,
        rows_expected: Optional[int] = None,
    ):
        super().__init__(error_message)
        self.rows = rows
        self.error_code = error_code
        self.error_message = error_message
        self.next_action = next_action
        self.rows_expected = rows_expected


class FileParser:
    """Base class for file parsers"""
    
    @staticmethod
    async def download_file(url: str) -> bytes:
        """Download file from URL"""
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
            
    @staticmethod
    async def parse(
        file_url: str,
        password: Optional[str] = None,
        file_content: Optional[bytes] = None,
        max_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Parse file and return rows"""
        raise NotImplementedError


class PDFParser(FileParser):
    """Parser for PDF files using pdfplumber"""
    
    @staticmethod
    async def parse(
        file_url: str,
        password: Optional[str] = None,
        file_content: Optional[bytes] = None,
        max_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract tables and text from PDF
        Returns a list of dictionaries representing rows
        """
        logger.info(f"Parsing PDF from {file_url if file_url else 'bytes'}")
        
        # Download if content not provided
        if not file_content and file_url:
            file_content = await FileParser.download_file(file_url)
        elif not file_content:
            raise ValueError("Either file_url or file_content must be provided")
        
        all_rows: List[Dict[str, Any]] = []
        start_time = time.time()
        
        try:
            # Open PDF with pdfplumber
            with pdfplumber.open(io.BytesIO(file_content), password=password or "") as pdf:
                logger.info(f"PDF has {len(pdf.pages)} pages")

                total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    if max_seconds is not None and (time.time() - start_time) > float(max_seconds):
                        if all_rows:
                            raise PartialParseError(
                                rows=all_rows,
                                error_code='PARSE_TIMEOUT',
                                error_message=f"We processed {len(all_rows)} rows before timing out.",
                                next_action='retry_upload',
                                rows_expected=None,
                            )
                        raise TimeoutError("Parsing timed out")

                    # Try to extract tables first
                    tables = page.extract_tables()
                    
                    if tables:
                        logger.info(f"Found {len(tables)} tables on page {page_num}")
                        for table_num, table in enumerate(tables, start=1):
                            # Convert table to list of dicts
                            if len(table) > 1:
                                headers = table[0]
                                # Clean headers
                                headers = [
                                    str(h).strip() if h is not None else f"Column_{i}"
                                    for i, h in enumerate(headers)
                                ]
                                
                                # Process data rows
                                for row_data in table[1:]:
                                    if row_data and any(cell for cell in row_data):
                                        row_dict = {
                                            'page': page_num,
                                            'table': table_num,
                                        }
                                        for i, cell in enumerate(row_data):
                                            if i < len(headers):
                                                row_dict[headers[i]] = str(cell).strip() if cell else ''
                                        all_rows.append(row_dict)
                    else:
                        # If no tables found, extract text
                        text = page.extract_text()
                        if text:
                            logger.info(f"No tables on page {page_num}, extracting text")
                            lines = text.split('\n')
                            for line_num, line in enumerate(lines, start=1):
                                if line.strip():
                                    all_rows.append({
                                        'page': page_num,
                                        'line': line_num,
                                        'text': line.strip()
                                    })
                                    
        except Exception as e:
            # Check for password error by type name or message
            if type(e).__name__ == 'PDFPasswordIncorrect' or "password" in str(e).lower():
                logger.warning(f"PDF is encrypted and requires a password: {file_url}")
                raise PasswordRequiredError("This PDF is password protected. Please provide the password.")
            
            logger.error(f"Error parsing PDF: {e}")
            raise e
        
        logger.info(f"Extracted {len(all_rows)} rows from PDF")
        return all_rows


class CSVParser(FileParser):
    """Parser for CSV files using pandas"""
    
    @staticmethod
    async def parse(
        file_url: str,
        password: Optional[str] = None,
        file_content: Optional[bytes] = None,
        max_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parse CSV file
        Returns a list of dictionaries representing rows
        """
        logger.info(f"Parsing CSV from {file_url if file_url else 'bytes'}")
        
        # Download if content not provided
        if not file_content and file_url:
            file_content = await FileParser.download_file(file_url)
        elif not file_content:
            raise ValueError("Either file_url or file_content must be provided")
        
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    io.BytesIO(file_content),
                    encoding=encoding,
                    skip_blank_lines=True,
                    on_bad_lines='skip'
                )
                logger.info(f"Successfully parsed CSV with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Error parsing CSV with encoding {encoding}: {e}")
                continue
        
        if df is None:
            raise ValueError("Failed to parse CSV with any supported encoding")
        
        # Clean column names (strip whitespace, lower case maybe? Keeping case sensitive but clean)
        df.columns = df.columns.str.strip()
        
        # Auto-detect date columns
        for col in df.columns:
            if 'date' in str(col).lower() or 'time' in str(col).lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='ignore')
                except:
                    pass

        # Convert to list of dicts
        # Replace NaN with None
        rows = df.where(pd.notnull(df), None).to_dict('records')
        
        # Convert all values to strings for consistency, handling dates
        cleaned_rows = []
        for row in rows:
            cleaned_row = {}
            for key, value in row.items():
                if value is None:
                    cleaned_row[key] = ''
                elif isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
                    cleaned_row[key] = value.strftime('%Y-%m-%d %H:%M:%S') if hasattr(value, 'strftime') else str(value)
                else:
                    cleaned_row[key] = str(value).strip()
            cleaned_rows.append(cleaned_row)
        
        logger.info(f"Extracted {len(cleaned_rows)} rows from CSV")
        return cleaned_rows


class ExcelParser(FileParser):
    """Parser for Excel files using pandas"""
    
    @staticmethod
    async def parse(
        file_url: str,
        password: Optional[str] = None,
        file_content: Optional[bytes] = None,
        max_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parse Excel file
        Returns a list of dictionaries representing rows
        If sheet_name is None, uses the first sheet
        """
        logger.info(f"Parsing Excel from {file_url if file_url else 'bytes'}")
        
        # Download if content not provided
        if not file_content and file_url:
            file_content = await FileParser.download_file(file_url)
        elif not file_content:
            raise ValueError("Either file_url or file_content must be provided")
        
        # Read Excel file
        try:
            # If sheet_name not specified, read first sheet
            excel_file = pd.ExcelFile(io.BytesIO(file_content))
            
            sheet_name = excel_file.sheet_names[0]
            logger.info(f"Using first sheet: {sheet_name}")
            
            df = pd.read_excel(
                io.BytesIO(file_content),
                sheet_name=sheet_name,
                engine='openpyxl'
            )
            
            logger.info(f"Loaded sheet '{sheet_name}' with {len(df)} rows")
            
        except Exception as e:
            logger.error(f"Error parsing Excel file: {e}")
            raise ValueError(f"Failed to parse Excel file: {str(e)}")
        
        # Clean column names
        df.columns = df.columns.astype(str).str.strip()
        
        # Add sheet name to each row
        df['_sheet'] = sheet_name
        
        # Convert to list of dicts
        rows = df.where(pd.notnull(df), None).to_dict('records')
        
        # Convert all values to strings for consistency
        cleaned_rows = []
        for row in rows:
            cleaned_row = {}
            for key, value in row.items():
                if value is None:
                    cleaned_row[key] = ''
                else:
                    cleaned_row[key] = str(value).strip()
            cleaned_rows.append(cleaned_row)
        
        logger.info(f"Extracted {len(cleaned_rows)} rows from Excel")
        return cleaned_rows


def get_parser(file_type: str):
    """Get the appropriate parser for the file type"""
    parsers = {
        'pdf': PDFParser,
        'csv': CSVParser,
        'xlsx': ExcelParser,
    }
    
    parser = parsers.get(file_type.lower())
    if not parser:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    return parser


