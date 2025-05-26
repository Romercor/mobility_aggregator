from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import asyncio
import concurrent.futures

from providers.base import BaseProvider
from api.models import WeeklyMenu, DayMenu, Dish
from utils.cache import get_cached_data, set_cached_data

class MensaProvider(BaseProvider):
    """Provider for TU Berlin mensa menus"""
    
    # Mensa configuration - matching your original script exactly
    MENSAS = {
        "hardenbergstrasse": {
            "name": "Mensa Hardenbergstrasse",
            "url": "https://www.stw.berlin/en/student-canteens/overview-student-canteens/technische-universität-berlin/mensa-tu-hardenbergstrasse.html"
        },
        "marchstrasse": {
            "name": "Mensa Marchstrasse", 
            "url": "https://www.stw.berlin/mensen/einrichtungen/technische-universität-berlin/mensa-tu-marchstraße.html"
        },
        "veggie": {
            "name": "Veggie2.0",
            "url": "https://www.stw.berlin/mensen/einrichtungen/technische-universität-berlin/veggie2.0.html"
        }
    }
    
    # CSS selectors - exactly from your original script
    CONSENT_BUTTON = 'button[data-testid="uc-accept-all-button"]'
    CONSENT_BUTTON_DE = 'button.uc-embedding-accept'
    
    def __init__(self):
        super().__init__()
        self.cache_ttl = 3600  # 1 hour cache
    
    def get_available_mensas(self) -> List[str]:
        """Get list of available mensa names"""
        return list(self.MENSAS.keys())
    
    async def get_weekly_menu(self, mensa_name: str, force_refresh: bool = False) -> Optional[WeeklyMenu]:
        """
        Get weekly menu for a specific mensa
        """
        if mensa_name not in self.MENSAS:
            return None
        
        # Check cache first
        cache_key = f"mensa_menu:{mensa_name}"
        if not force_refresh:
            cached_menu = await get_cached_data(cache_key)
            if cached_menu:
                return WeeklyMenu(**cached_menu)
        
        # Scrape fresh data
        mensa_config = self.MENSAS[mensa_name]
        try:
            menu_data = await self._scrape_weekly_menu(mensa_config["url"])
            weekly_menu = self._parse_menu_data(mensa_config["name"], menu_data)
            
            # Cache the result
            await set_cached_data(cache_key, weekly_menu.model_dump())
            return weekly_menu
            
        except Exception as e:
            print(f"Error scraping menu for {mensa_name}: {str(e)}")
            return None
    
    async def _scrape_weekly_menu(self, url: str) -> Dict[str, Dict]:
        """Scrape weekly menu - exact copy of your original script logic"""
        
        def fetch_weekly_menu_sync(url: str) -> dict:
            """Exact copy of your original fetch_weekly_menu function"""
            from playwright.sync_api import sync_playwright
            
            weekly = {}
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(url, timeout=60000)

                # Attempt to dismiss cookie consent
                try:
                    page.wait_for_selector(self.CONSENT_BUTTON, timeout=5000)
                    page.locator(self.CONSENT_BUTTON).click()
                except:
                    try:
                        page.wait_for_selector(self.CONSENT_BUTTON_DE, timeout=5000)
                        page.locator(self.CONSENT_BUTTON_DE).click()
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
        
        # Run your original sync function in thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, fetch_weekly_menu_sync, url)
    
    def _parse_menu_data(self, mensa_name: str, raw_data: Dict[str, Dict]) -> WeeklyMenu:
        """Convert raw scraped data to structured menu"""
        days = []
        
        for day_name, groups_data in raw_data.items():
            # Convert to our models
            groups = {}
            for group_name, dishes_data in groups_data.items():
                dishes = [
                    Dish(
                        name=dish["name"],
                        price=dish["price"],
                        vegan=dish["vegan"],
                        vegetarian=dish["vegetarian"]
                    )
                    for dish in dishes_data
                ]
                groups[group_name] = dishes
            
            # Create day menu
            day_menu = DayMenu(
                day_name=day_name,
                groups=groups,
                is_available=len(groups) > 0
            )
            days.append(day_menu)
        
        return WeeklyMenu(
            mensa_name=mensa_name,
            days=days,
            last_updated=datetime.now()
        )