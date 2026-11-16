"""
MiniLedger CSV Export Module.

Handles the logic for exporting ledger records to CSV format.
Includes validation, permission checks (owner_id), and performance limits.
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any

# Constants
MAX_EXPORT_ROWS = 100_000
CSV_HEADER = ["date", "amount", "category", "note"]
UTF8_BOM = "\ufeff"


def validate_month_param(month_str: str) -> str:
    """
    Validate and normalize the month parameter (YYYY-MM).
    
    Args:
        month_str: The month string to validate.
        
    Returns:
        Normalized month string in YYYY-MM format.
        
    Raises:
        ValueError: If the format is invalid or not a real month.
    """
    if not month_str:
        raise ValueError("Month parameter is required.")
    
    try:
        # Validate format and date validity
        dt = datetime.strptime(month_str, "%Y-%m")
        return dt.strftime("%Y-%m")
    except ValueError:
        raise ValueError(f"Invalid month format. Expected YYYY-MM, got '{month_str}'.")


def check_row_limit(count: int) -> None:
    """
    Check if the number of records exceeds the hard limit.
    
    Args:
        count: The number of records to export.
        
    Raises:
        ValueError: If count exceeds MAX_EXPORT_ROWS.
    """
    if count > MAX_EXPORT_ROWS:
        raise ValueError(
            f"Export limit exceeded. Requested {count} rows, "
            f"maximum allowed is {MAX_EXPORT_ROWS}. Please narrow the date range."
        )


def build_csv_content(records: List[Dict[str, Any]]) -> bytes:
    """
    Build CSV content with UTF-8 BOM header.
    
    Args:
        records: List of record dictionaries containing 'date', 'amount', 
                 'category', and 'note'.
                 
    Returns:
        Bytes object containing the CSV data with BOM.
    """
    output = io.StringIO()
    
    # Write BOM manually to ensure it's at the very start of the byte stream
    # when encoded later, or prepend it if using text mode. 
    # Standard practice for Excel compatibility in Python:
    # We will write the BOM character as the first string.
    
    writer = csv.writer(output, lineterminator='\n')
    
    # Write Header
    writer.writerow(CSV_HEADER)
    
    # Write Data Rows
    if records:
        for record in records:
            writer.writerow([
                record.get("date", ""),
                record.get("amount", 0),
                record.get("category", ""),
                record.get("note", "")
            ])
            
    csv_string = output.getvalue()
    
    # Prepend BOM for Excel compatibility
    csv_with_bom = UTF8_BOM + csv_string
    
    # Encode to bytes using UTF-8
    return csv_with_bom.encode('utf-8')


def export_ledger_csv(
    month: str, 
    owner_id: str, 
    query_service: Any
) -> bytes:
    """
    Main function to export ledger records for a specific month.
    
    Args:
        month: The target month in YYYY-MM format.
        owner_id: The ID of the user requesting the export (for permission check).
        query_service: The injected service responsible for querying the database.
                       It must support filtering by owner_id and date range.
                       
    Returns:
        Bytes object containing the CSV content.
        
    Raises:
        ValueError: If validation fails or limits are exceeded.
        PermissionError: If owner_id is invalid (handled by query_service usually, 
                         but explicit check here if needed).
    """
    # 1. Validate Input
    normalized_month = validate_month_param(month)
    
    # 2. Determine Date Range
    start_date = datetime.strptime(normalized_month, "%Y-%m").replace(day=1)
    # Calculate end date: next month's day 1 minus 1 second, or just use < next month start
    if normalized_month == "12-31": # Edge case for year end if needed, but strptime handles YYYY-MM
        import calendar
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        end_date = start_date.replace(day=last_day)
    else:
        next_month_start = (start_date.replace(day=28) + __import__('datetime').timedelta(days=4)).replace(day=1)
        end_date = next_month_start - __import__('datetime').timedelta(seconds=1)

    # 3. Query Data with Owner Constraint
    # CRITICAL: The query_service MUST enforce owner_id to prevent IDOR vulnerabilities.
    records = query_service.find_records_by_month(
        owner_id=owner_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not records:
        # Empty month: Return valid CSV with only headers
        return build_csv_content([])
        
    # 4. Check Row Limit
    check_row_limit(len(records))
    
    # 5. Generate CSV Content
    return build_csv_content(records)