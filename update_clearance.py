#!/usr/bin/env python3
"""
Portor Clearance Stock Update Script
Pulls clearance data from Google Sheets and converts to JSON for the HTML frontend.
Designed to run via GitHub Actions at 7:30 AM Eastern daily.
"""

import csv
import json
import urllib.request
import re
from datetime import datetime, timezone
from io import StringIO

# Google Sheet configuration - Clearance Stock sheet
SHEET_ID = "1XwA4sOwRhb6z9jZ7XyEYUFFM04R0AzWBxKo0d4hJjMM"
GID = "0"  # Default first tab

# Category mapping to standardize categories
CATEGORY_MAP = {
    "Area Light": "Area Light",
    "AL2": "Area Light",
    "AL2N": "Area Light",
    "Twin Lens High Bay": "Linear High Bay",
    "Limited Stock - Linear High Bay": "Linear High Bay",
    "Limited Stock - High Bay - Linear Fixtures": "Linear High Bay",
    "High Bay - Round Limited Stock": "Round High Bay",
    "HBU3 Accessories": "Round High Bay",
    "PT-WAA Series -": "Wraparound",
    "Limited Stock Strip Light": "Strip Light",
    "LSFA": "Strip Light",
    "Accessories": "Accessories",
    "Limited Stock - Vapor Tight": "Vaportight",
}

def map_category(raw_category):
    """Map raw category from sheet to standardized category."""
    for key, value in CATEGORY_MAP.items():
        if key.lower() in raw_category.lower():
            return value
    return raw_category

def fetch_sheet_csv(sheet_id, gid):
    """Fetch a Google Sheet tab as CSV."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching sheet (gid={gid}): {e}")
        return None

def parse_int(value):
    """Parse a string to int, handling commas and empty values."""
    if not value:
        return 0
    cleaned = re.sub(r'[,\s]', '', str(value))
    try:
        return int(cleaned)
    except ValueError:
        return 0

def parse_clearance_csv(csv_content):
    """Parse the clearance CSV into structured data."""
    reader = csv.reader(StringIO(csv_content))
    rows = list(reader)

    # Find the header row - it's the one with "Item# / SKU" in column B (index 1)
    header_row_idx = None
    for i, row in enumerate(rows):
        if len(row) > 1 and ("Item# / SKU" in str(row[1]) or "Item#" in str(row[1])):
            header_row_idx = i
            break

    if header_row_idx is None:
        print("Could not find header row")
        return []

    # Column mapping based on the sheet structure:
    # Col 0: Category/Subcategory label
    # Col 1: SKU
    # Col 2: Description
    # Col 3: Wattage
    # Col 4: Ontario
    # Col 5: Louisville
    # Col 6: Phoenix
    # Col 7: Dallas
    # Col 8: Chicago
    # Col 9: Total
    # Col 10: Notes
    # Col 11: Spec URL

    products = []
    current_category = ""
    current_subcategory = ""

    for row in rows[header_row_idx + 1:]:
        if len(row) < 2:
            continue

        first_col = row[0].strip() if row[0] else ""
        sku_col = row[1].strip() if len(row) > 1 and row[1] else ""

        # Skip completely empty rows
        if not first_col and not sku_col:
            continue

        # Main category row: has text in first column, nothing meaningful in SKU
        if first_col and not sku_col:
            current_category = first_col.replace('\n', ' ').strip()
            current_subcategory = ""
            continue

        # Subcategory + product row: has text in first column AND SKU in second column
        if first_col and sku_col:
            current_subcategory = first_col.replace('\n', ' ').strip()

        # Product row: has SKU
        if sku_col:
            # Get spec URL from column 11, filter out #N/A and empty values
            spec_url = ""
            if len(row) > 11:
                raw_spec = row[11].strip()
                if raw_spec and raw_spec != "#N/A" and raw_spec.startswith("http"):
                    spec_url = raw_spec

            product = {
                'sku': sku_col,
                'description': row[2].strip() if len(row) > 2 else "",
                'wattage': row[3].strip() if len(row) > 3 else "",
                'category': map_category(current_category) if current_category else map_category(current_subcategory),
                'subcategory': current_subcategory,
                'ontario': parse_int(row[4] if len(row) > 4 else "0"),
                'louisville': parse_int(row[5] if len(row) > 5 else "0"),
                'phoenix': parse_int(row[6] if len(row) > 6 else "0"),
                'dallas': parse_int(row[7] if len(row) > 7 else "0"),
                'chicago': parse_int(row[8] if len(row) > 8 else "0"),
                'total': parse_int(row[9] if len(row) > 9 else "0"),
                'notes': row[10].strip() if len(row) > 10 else "",
                'spec_url': spec_url,
            }
            products.append(product)

    return products

def main():
    """Main function to fetch and process clearance data."""
    print(f"Starting clearance update at {datetime.now(timezone.utc).isoformat()}")

    print(f"Fetching clearance data (gid={GID})...")
    csv_content = fetch_sheet_csv(SHEET_ID, GID)

    if not csv_content:
        print("Failed to fetch clearance data")
        return 1

    products = parse_clearance_csv(csv_content)
    print(f"Parsed {len(products)} clearance products")

    all_data = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'updated_at_pacific': datetime.now(timezone.utc).strftime('%B %d, %Y'),
        'tabs': {
            'clearance': {
                'name': 'Clearance Stock',
                'products': products,
                'count': len(products)
            }
        }
    }

    # Write JSON output
    output_path = 'clearance_data.json'
    with open(output_path, 'w') as f:
        json.dump(all_data, f, indent=2)

    print(f"Wrote {output_path}")
    print("Update complete!")
    return 0

if __name__ == "__main__":
    exit(main())

