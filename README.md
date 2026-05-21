# Starlink Data Usage Scraper

A simple Python tool that extracts daily data usage from Starlink account HTML files and saves the results to a CSV file.

## What It Does

- Reads a saved Starlink account HTML page
- Extracts daily data usage (in GB) from the usage chart
- Creates a CSV file with the data organized by month and day
- Automatically handles billing cycles that span two months

## How to Use

### Quick Start

1. **Save your Starlink HTML file** — Go to your Starlink account online, save the page as HTML (right-click → Save as), and move it to this folder

2. **Run the scraper:**
   ```bash
   python web_scraper.py your_file.html
   ```

3. **Check the output** — Look for `starlink_data_usage.csv` in the same folder

### Custom Output Name

Save to a specific CSV filename:
```bash
python web_scraper.py your_file.html custom_name.csv
```

## How It Works

The script follows these steps:

1. **Reads** the HTML file from your Starlink account
2. **Parses** the usage chart data from the SVG elements
3. **Converts** chart pixels to GB values using the axis scale
4. **Detects** the billing month and handles month transitions
5. **Exports** everything to a clean CSV file with a total row

## Requirements

- Python 3.x
- Libraries: `beautifulsoup4`, `pandas`, `lxml`

Install dependencies:
```bash
pip install -r requirements.txt
```

Python Script for venv:
python -m venv .venv
.venv/Scripts/Activate/ps1

## Files in This Project

- `web_scraper.py` — Main script (run this)
- `starlink_data_usage.csv` — Output file with your data
- `requirements.txt` — Python dependencies
- HTML files (e.g., `Nov-Dec.html`) — Saved Starlink account pages

## Billing Cycle

By default, the script assumes your Starlink billing cycle starts on the **17th of each month**. If yours is different, edit this line in `web_scraper.py`:

```python
BILLING_START_DAY = 17  # Change this to your billing start day
```

## Output Format

The CSV file looks like this:

| month | day | data_usage_gb |
|-------|-----|---------------|
| Nov   | 17  | 0.45          |
| Nov   | 18  | 0.32          |
| ...   | ... | ...           |
| Dec   | 16  | 0.28          |
| Dec   | Total | 15.42       |

## Troubleshooting

- **"File not found"** — Make sure the HTML file is in the same folder as the script
- **"No data bars found"** — The HTML file might be corrupted or from a different Starlink page
- **Wrong date range** — Check that your billing start day (BILLING_START_DAY) is correct

## Questions?

The code is well-documented with comments explaining each step. Feel free to modify it to fit your needs!
