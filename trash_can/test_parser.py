#!/usr/bin/env python3
import time
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# URLs of Mensa locations to parse
MENSAS = {
    "Hardenbergstrasse": (
        "https://www.stw.berlin/en/student-canteens/overview-student-canteens/"
        "technische-universität-berlin/mensa-tu-hardenbergstrasse.html"
    ),
    "Marchstrasse": (
        "https://www.stw.berlin/mensen/einrichtungen/"
        "technische-universität-berlin/mensa-tu-marchstraße.html"
    ),
    "Veggie2.0": (
        "https://www.stw.berlin/mensen/einrichtungen/"
        "technische-universität-berlin/veggie2.0.html"
    ),
}

# CSS selectors for the consent accept button (if present)
CONSENT_BUTTON = 'button[data-testid="uc-accept-all-button"]'
CONSENT_BUTTON_DE = 'button.uc-embedding-accept'


def fetch_weekly_menu(url: str) -> dict:
    """Returns a dict mapping weekday → { group → [ {name, price, vegan, vegetarian}, … ] }."""
    weekly = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, timeout=60000)

        # Attempt to dismiss cookie consent
        try:
            page.wait_for_selector(CONSENT_BUTTON, timeout=5000)
            page.locator(CONSENT_BUTTON).click()
        except:
            try:
                page.wait_for_selector(CONSENT_BUTTON_DE, timeout=5000)
                page.locator(CONSENT_BUTTON_DE).click()
            except:
                pass
        page.wait_for_timeout(500)

        # Loop over Monday (1) … Saturday (6)
        for day_idx in range(1, 7):
            tab = page.locator(f"#spltag{day_idx}")
            tab.wait_for(state="visible", timeout=5000)
            day_name = tab.inner_text().strip()

            # Capture old content and click new day
            old_content = page.inner_html("#speiseplan")
            tab.click()
            # Wait until the #speiseplan content changes
            page.wait_for_function(
                "([old, selector]) => document.querySelector(selector).innerHTML !== old",
                arg=(old_content, "#speiseplan"),
                timeout=10000
            )

            # Parse the newly loaded HTML
            html = page.inner_html("#speiseplan")
            soup = BeautifulSoup(html, "html.parser")

            day_menu = {}
            for wrapper in soup.select(".splGroupWrapper"):
                group_tag = wrapper.select_one(".splGroup")
                group = group_tag.get_text(strip=True) if group_tag else "General"
                meals = []

                for meal in wrapper.select(".splMeal"):
                    name = meal.select_one("span.bold").get_text(strip=True)
                    price = meal.select_one(".text-right").get_text(strip=True)
                    vegan = bool(meal.select_one('img[aria-describedby="tooltip_vegan"]'))
                    vegetarian = bool(meal.select_one('img[aria-describedby="tooltip_vegetarisch"]'))
                    meals.append({
                        "name": name,
                        "price": price,
                        "vegan": vegan,
                        "vegetarian": vegetarian
                    })

                day_menu[group] = meals

            weekly[day_name] = day_menu

        browser.close()
    return weekly


if __name__ == "__main__":
    # Prepare single output file
    script_dir = Path(__file__).parent
    out_path = script_dir / "all_menus.txt"

    with open(out_path, "w", encoding="utf-8") as f:
        for mensa_name, mensa_url in MENSAS.items():
            f.write(f"Mensa {mensa_name}\n")
            try:
                menu = fetch_weekly_menu(mensa_url)
            except Exception as e:
                f.write(f"Failed to fetch {mensa_name}: {e}\n\n")
                continue

            for day, groups in menu.items():
                f.write(f"\n--- {day} ---\n")
                if not groups:
                    f.write("No dishes available for this day.\n")
                    continue
                for grp, items in groups.items():
                    f.write(f"\n{grp}:\n")
                    if not items:
                        f.write("No dishes available for this section.\n")
                        continue
                    for d in items:
                        tags = []
                        if d["vegan"]:
                            tags.append("vegan")
                        if d["vegetarian"]:
                            tags.append("vegetarian")
                        tag_str = f" ({', '.join(tags)})" if tags else ""
                        f.write(f" • {d['name']} — {d['price']}{tag_str}\n")
            f.write("\n\n")
    print(f"✅ All menus saved to {out_path}")
