# providers/mensa.py - Cache First Logic

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import asyncio
import concurrent.futures

from providers.base import BaseProvider
from api.models import WeeklyMenu, DayMenu, Dish
from utils.cache import mensa_cache

# Import database service
try:
    from database.service import DatabaseService
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: Database not available, using cache only")

class MensaProvider(BaseProvider):
    """Provider for TU Berlin mensa menus with Cache First strategy"""
    
    # Mensa configuration - matching your original script exactly
    MENSAS = {
        "hardenbergstrasse": {
            "name": "hardenbergstrasse",
            "url": "https://www.stw.berlin/en/student-canteens/overview-student-canteens/technische-universität-berlin/mensa-tu-hardenbergstrasse.html"
        },
        "marchstrasse": {
            "name": "marchstrasse", 
            "url": "https://www.stw.berlin/en/student-canteens/overview-student-canteens/technische-universität-berlin/mensa-tu-marchstrasse.html"
        },
        "veggie": {
            "name": "veggie",
            "url": "https://www.stw.berlin/en/student-canteens/overview-student-canteens/technische-universität-berlin/veggie2.0.html"
        }
    }
    
    # CSS selectors - exactly from your original script
    CONSENT_BUTTON = 'button[data-testid="uc-accept-all-button"]'
    CONSENT_BUTTON_DE = 'button.uc-embedding-accept'
    
    def __init__(self):
        super().__init__()
        self.cache_ttl = 3600  # Keep for reference
    
    def get_available_mensas(self) -> List[str]:
        """Get list of available mensa names"""
        return list(self.MENSAS.keys())
    
    async def get_weekly_menu(self, mensa_name: str, force_refresh: bool = False) -> Optional[WeeklyMenu]:
        """
        Get weekly menu with Cache First strategy
        """
        if mensa_name not in self.MENSAS:
            return None
        
        cache_key = f"mensa_menu:{mensa_name}"
        
        # 1. Check unified cache first
        if not force_refresh:
            cached_menu = await mensa_cache.get(cache_key)
            if cached_menu:
                try:
                    # Same scheduling logic for cache
                    if not self._should_refresh_menu(cached_menu):
                        print(f"Returning cached data for {mensa_name}")
                        return WeeklyMenu(**cached_menu)
                    else:
                        print(f"Cache data stale for {mensa_name}")
                except Exception as e:
                    print(f"Error with cached menu for {mensa_name}: {str(e)}")
            else:
                print(f"No cached data for {mensa_name}")
        
        # 2. Try database second (if available)
        if DB_AVAILABLE and not force_refresh:
            try:
                print(f"DEBUG: Checking database for {mensa_name}")
                db_data = await DatabaseService.get_mensa_menu(mensa_name)
                print(f"DEBUG: DB data exists: {db_data is not None}")
                
                if db_data:
                    print(f"DEBUG: DB last_updated: {db_data.get('last_updated')}")
                    should_refresh = self._should_refresh_menu(db_data)
                    print(f"DEBUG: Should refresh DB data: {should_refresh}")
                    
                    if not should_refresh:
                        print(f"Returning fresh data from database for {mensa_name}")
                        menu = self._parse_db_menu_data(db_data)
                        
                        # Restore cache from database
                        try:
                            await mensa_cache.set(cache_key, menu.model_dump())
                            print(f"Cache restored from DB for {mensa_name}")
                        except Exception as e:
                            print(f"Error restoring cache for {mensa_name}: {str(e)}")
                        
                        return menu
                    else:
                        print(f"Database data stale for {mensa_name}")
                else:
                    print(f"No database data found for {mensa_name}")
            except Exception as e:
                print(f"Database query failed for {mensa_name}: {str(e)}")
        
        # 3. Scrape fresh data (last resort)
        mensa_config = self.MENSAS[mensa_name]
        try:
            print(f"Scraping fresh data for {mensa_name}")
            menu_data = await self._scrape_weekly_menu(mensa_config["url"])
            weekly_menu = self._parse_menu_data(mensa_config["name"], menu_data)
            
            # Save to database first (if available)
            if DB_AVAILABLE:
                try:
                    db_saved = await DatabaseService.save_mensa_menu(weekly_menu, force_refresh)
                    if db_saved:
                        print(f"Saved menu to database for {mensa_name}")
                except Exception as e:
                    print(f"Failed to save to database for {mensa_name}: {str(e)}")
            
            # Cache the result (always do this as fallback)
            try:
                await mensa_cache.set(cache_key, weekly_menu.model_dump())
                print(f"Cached menu for {mensa_name}")
            except Exception as e:
                print(f"Error caching menu for {mensa_name}: {str(e)}")
            
            return weekly_menu
            
        except Exception as e:
            print(f"Error scraping menu for {mensa_name}: {str(e)}")
            return None
    

    
    def _parse_db_menu_data(self, db_data: dict) -> WeeklyMenu:
        """Convert database JSON data back to WeeklyMenu object"""
        days = []
        for day_data in db_data["days"]:
            groups = {}
            for group_name, dishes_data in day_data["groups"].items():
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
            
            day_menu = DayMenu(
                day_name=day_data["day_name"],
                groups=groups,
                is_available=day_data["is_available"]
            )
            days.append(day_menu)
        
        return WeeklyMenu(
            mensa_name=db_data["mensa_name"],
            days=days,
            last_updated=datetime.fromisoformat(db_data["last_updated"])
        )
    
    def _should_refresh_menu(self, menu_data: dict) -> bool:
        """
        Unified scheduling logic for both cache and database data
        """
        try:
            # Handle both datetime object and string
            last_updated_raw = menu_data["last_updated"]
            if isinstance(last_updated_raw, str):
                last_updated = datetime.fromisoformat(last_updated_raw)
            else:
                last_updated = last_updated_raw  # Already a datetime object
            
            now = datetime.now()
            
            # Rule 1: If older than 7 days, always refresh
            if (now - last_updated).days >= 7:
                print(f"Data is {(now - last_updated).days} days old, refreshing...")
                return True
            
            # Rule 2: If data is from previous week (any day of current week)
            if last_updated.isocalendar()[1] < now.isocalendar()[1]:
                print("Data from previous week, refreshing...")
                return True
                
            return False
            
        except Exception as e:
            print(f"Error checking refresh condition: {e}")
            return True
    
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
                is_available=any(len(dishes) > 0 for dishes in groups.values())
            )
            days.append(day_menu)
        
        return WeeklyMenu(
            mensa_name=mensa_name,
            days=days,
            last_updated=datetime.now()
        )