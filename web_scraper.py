"""
Starlink Data Usage Scraper
----------------------------
Extracts daily data usage (GB) from a saved Starlink account HTML page
and exports the results to a CSV file.

Follows the DataCamp "Web Scraping using Python" tutorial pattern:
  Step 1 -- Open / read the HTML with urllib.request (or a local file)
  Step 2 -- Parse the HTML into a BeautifulSoup object using lxml
  Step 3 -- Navigate and extract data via tags, attributes, and CSS selectors
  Step 4 -- Clean / transform the extracted values
  Step 5 -- Export to CSV with pandas

Usage:
    python scraper.py <input.html> [output.csv]

    <input.html>  -- path to a saved Starlink service-line HTML file
                     OR a live URL (e.g. https://starlink.com/account/...)
    [output.csv]  -- optional output filename (default: starlink_data_usage.csv)

Examples:
    python scraper.py Starlink.html
    python scraper.py Starlink.html april_usage.csv
"""

# ── Step 1: Import libraries ──────────────────────────────────────────────────
# DataCamp tutorial pattern:
#   from urllib.request import urlopen
#   from bs4 import BeautifulSoup
import sys
import re
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from bs4 import BeautifulSoup


# ── Fallback chart scale constants ────────────────────────────────────────────
# Used only when the axis ticks cannot be read from the page.
# Confirmed from a real Starlink HTML capture (Starlink.html):
#   translate(0, 130)              -> "0 GB"  (zero baseline)
#   translate(0, 43.134687002672)  -> "20 GB" (top of scale)
_FALLBACK_Y_ZERO_PX = 130.0
_FALLBACK_Y_TOP_PX  = 43.134687002672486
_FALLBACK_MAX_GB    = 20.0

# ── Billing cycle configuration ───────────────────────────────────────────────
# Starlink billing cycles start on a fixed day each month.
# Change this to match your account's billing start day.
BILLING_START_DAY = 17

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ── Step 2: Open the HTML source and create a BeautifulSoup object ────────────
def get_soup(source: str) -> BeautifulSoup:
    """
    DataCamp tutorial pattern:
        html = urlopen(url)
        soup = BeautifulSoup(html, 'lxml')

    Accepts either a local file path or a live URL.
    """
    if source.startswith("http://") or source.startswith("https://"):
        html = urlopen(source)
        soup = BeautifulSoup(html, "lxml")
    else:
        html_path = Path(source)
        if not html_path.exists():
            raise FileNotFoundError(f"File not found: {html_path}")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "lxml")

    return soup


# ── Step 3: Navigate the parse tree and extract raw data ─────────────────────
def extract_bar_positions(soup: BeautifulSoup) -> list:
    """
    The daily usage is stored as SVG <rect> elements inside
    g[data-series="y_0"].

    We read the 'y' attribute — the TOP pixel position of each bar.
    The bar height alone is not used because both 'y' and 'height' happen
    to be numerically equal for baseline-anchored bars (height = Y_ZERO - y),
    but 'y' is the semantically correct value: it directly encodes distance
    from the zero line without any assumption about bar anchoring.

    DataCamp pattern: soup.select to locate elements by CSS selector.
    """
    rects = soup.select('g[data-series="y_0"] rect')
    if not rects:
        raise ValueError(
            "No data bars found. Make sure the HTML contains a Starlink "
            "usage bar chart (g[data-series='y_0'] rect elements)."
        )
    return [float(r["y"]) for r in rects]


def read_axis_scale(soup: BeautifulSoup) -> tuple:
    """
    Read the true Y-axis scale directly from the SVG tick group transforms
    and their label text, so the script stays accurate even if Starlink
    changes the chart dimensions.

    The MUI chart renders each Y-axis tick as:
        <g transform="translate(0, <pixel_y>)">
            <text ...><tspan>N GB</tspan></text>
        </g>

    We find every tick whose label ends with " GB", collect
    (pixel_y, gb_value) pairs, then derive:
        y_zero  = pixel_y where gb_value == 0
        y_top   = pixel_y where gb_value == max label
        max_gb  = the highest GB label found

    Falls back to the hardcoded constants if fewer than two ticks are found.

    DataCamp pattern: soup.find_all with attrs={} + regex on transform string.
    """
    ticks = []  # list of (pixel_y: float, gb_value: float)

    for g in soup.find_all("g", transform=True):
        # Match translate(0, <y>) — Y-axis ticks have x=0
        m_transform = re.match(r"translate\(\s*0\s*,\s*([0-9.]+)\s*\)", g.get("transform", ""))
        if not m_transform:
            continue

        label = g.get_text(strip=True)
        # Match labels like "0 GB" or "20 GB"
        m_label = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*GB$", label)
        if not m_label:
            continue

        pixel_y  = float(m_transform.group(1))
        gb_value = float(m_label.group(1))
        ticks.append((pixel_y, gb_value))

    if len(ticks) < 2:
        print(
            f"  [warn] Only {len(ticks)} axis tick(s) found — "
            "using fallback scale constants."
        )
        return _FALLBACK_Y_ZERO_PX, _FALLBACK_Y_TOP_PX, _FALLBACK_MAX_GB

    # Sort by GB value: index 0 = 0 GB (bottom), last = max GB (top)
    ticks.sort(key=lambda t: t[1])
    y_zero = ticks[0][0]   # pixel row for 0 GB
    y_top  = ticks[-1][0]  # pixel row for max GB
    max_gb = ticks[-1][1]

    print(f"  [axis] 0 GB  -> y={y_zero}")
    print(f"  [axis] {max_gb} GB -> y={y_top}")
    return y_zero, y_top, max_gb


def detect_start_month(soup: BeautifulSoup) -> str:
    """
    Read the first active month tab — the billing cycle start month.

    The active month tabs use CSS class 'mui-1bcwr2w' inside
    'button.mui-hkx3jt'.  The first tab is always the cycle start month.

    DataCamp pattern: soup.select to find elements by CSS class.
    """
    for btn in soup.select("button.mui-hkx3jt h6.mui-1bcwr2w"):
        text = btn.get_text(strip=True)
        if text and text != "-":
            return text
    return "Unknown"


# ── Step 4: Clean and transform the extracted values ─────────────────────────
def positions_to_gb(bar_y_positions: list, y_zero: float, y_top: float, max_gb: float) -> list:
    """
    Convert each bar's top pixel position to a GB value using the linear
    scale derived from the two SVG axis reference ticks:

        scale = max_gb / (y_zero - y_top)
        gb    = (y_zero - bar_y) * scale

    The scale is now read dynamically from the page (read_axis_scale) rather
    than hardcoded, so the script self-corrects if Starlink resizes the chart.
    """
    scale = max_gb / (y_zero - y_top)
    return [round((y_zero - y) * scale, 2) for y in bar_y_positions]


def build_days(start_month: str, num_bars: int, billing_day: int) -> tuple:
    """
    Return (months, days) parallel lists for the billing cycle.

    The billing cycle runs from billing_day of the start month through
    (billing_day - 1) of the next month, accounting for actual month lengths.

    For example, with start_month='Feb', billing_day=17, num_bars=28:
        months -> ['Feb']*11 + ['Mar']*17
        days   -> [17, 18, ..., 28, 1, 2, ..., 16]

    DataCamp pattern: plain Python loop for transformation.
    """
    # Days in each month (non-leap year; adjust Feb for leap years if needed)
    days_in_month = {
        'jan': 31, 'feb': 28, 'mar': 31, 'apr': 30, 'may': 31, 'jun': 30,
        'jul': 31, 'aug': 31, 'sep': 30, 'oct': 31, 'nov': 30, 'dec': 31,
    }

    month_keys        = list(MONTH_MAP.keys())  # ['jan', 'feb', ..., 'dec']
    current_month_idx = month_keys.index(start_month.lower())
    current_month_key = month_keys[current_month_idx]
    current_day       = billing_day

    months, days = [], []
    for i in range(num_bars):
        months.append(month_keys[current_month_idx].capitalize())
        days.append(current_day)

        # Move to the next day
        current_day += 1
        max_day = days_in_month[current_month_key]

        # If we exceed the month's max day, roll to next month
        if current_day > max_day:
            current_day = 1
            current_month_idx = (current_month_idx + 1) % 12
            current_month_key = month_keys[current_month_idx]

    return months, days


# ── Step 5: Export to CSV with pandas ────────────────────────────────────────
def save_csv(months: list, days: list, gb_values: list, output_path: str) -> None:
    """
    DataCamp tutorial pattern: build a pandas DataFrame, then call .to_csv().

    A summary row with day="Total" is appended as the last row so the CSV
    is self-contained — no need to sum the column manually.
    The total row uses the start month label (first entry in months).
    """
    total = round(sum(gb_values[:len(days)]), 2)

    df = pd.DataFrame({
        "month":         months,
        "day":           days,
        "data_usage_gb": gb_values[:len(days)],
    })

    total_row = pd.DataFrame({
        "month":         [months[0]],
        "day":           ["Total"],
        "data_usage_gb": [total],
    })

    df = pd.concat([df, total_row], ignore_index=True)
    df.to_csv(output_path, index=False)
    print(f"\nSaved {len(df) - 1} rows + total -> {output_path}")
    print(df.to_string(index=False))


# ── Default file paths ───────────────────────────────────────────────────────
DEFAULT_HTML = "Mar-Apr.html"           # downloaded Starlink HTML file
DEFAULT_CSV  = "starlink_data_usage.csv" # output CSV file


# ── Main pipeline ─────────────────────────────────────────────────────────────
def main():
    source      = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HTML
    output_file = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CSV

    print(f"Source  : {source}")

    # Step 2 -- parse HTML
    soup = get_soup(source)

    # Step 3 -- extract bar top positions (y attribute) + axis scale
    bar_y_positions        = extract_bar_positions(soup)
    y_zero, y_top, max_gb = read_axis_scale(soup)
    month_name             = detect_start_month(soup)

    # Step 4 -- transform positions to GB values using live axis scale
    gb_values = positions_to_gb(bar_y_positions, y_zero, y_top, max_gb)
    months, days = build_days(month_name, len(gb_values), BILLING_START_DAY)

    total = sum(gb_values)
    print(f"Month   : {month_name}")
    print(f"Days    : {len(days)}")
    print(f"Total   : {total:.1f} GB")

    # Step 5 -- export
    save_csv(months, days, gb_values, output_file)


if __name__ == "__main__":
    main()