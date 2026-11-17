"""Read constants only; never execute workbook formulas. Requires openpyxl.

Usage: python scripts/extract_cultivation_workbook.py workbook.xlsx output.json
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path
from openpyxl import load_workbook


def extract(path):
    workbook = load_workbook(path, read_only=True, data_only=False)
    result = {}
    for name, width in [('Batch Register', 20), ('Daily Growth Log', 7), ('Nutrient & EC Log', 11)]:
        rows = []
        for row in workbook[name].iter_rows(min_row=4, max_col=width):
            values = [None if cell.data_type == 'f' else cell.value for cell in row]
            values = [v.isoformat() if isinstance(v, (date, datetime)) else v for v in values]
            if any(v is not None for v in values):
                rows.append({'row': row[0].row, 'values': values})
        result[name] = rows
    workbook.close()
    return result


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(json.dumps(extract(sys.argv[1]), ensure_ascii=False, indent=2), encoding='utf-8')
