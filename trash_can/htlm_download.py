#!/usr/bin/env python3
import requests
from pathlib import Path

# ← Hier deine URL eintragen:
URL = "https://www.stw.berlin/en/student-canteens/overview-student-canteens/technische-universität-berlin/mensa-tu-hardenbergstrasse.html"

# Name der Ausgabedatei
FILENAME = "page_content.txt"

# Browser-ähnliche Header
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.stw.berlin/"
}

def download_html():
    script_dir = Path(__file__).parent
    out_path = script_dir / FILENAME

    resp = requests.get(URL, headers=HEADERS)
    resp.raise_for_status()

    out_path.write_text(resp.text, encoding="utf-8")
    print(f"✅ HTML gespeichert in: {out_path}")

if __name__ == "__main__":
    download_html()

