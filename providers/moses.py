from typing import List, Dict, Any, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import re

from providers.base import BaseProvider
from api.models import StudentLecture
from utils.cache import moses_cache

class StudentScheduleProvider(BaseProvider):
    """Provider for TU Berlin student schedule data - FULLY ASYNC"""
    
    def __init__(self):
        super().__init__()
        self.client.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_current_semester(self) -> int:
        """Calculate current university semester number (base: 74 = Summer 2025)"""
        current_date = datetime.now()
        base_semester, base_year, base_month = 74, 2025, 4
        
        months_passed = (current_date.year - base_year) * 12 + (current_date.month - base_month)
        semesters_passed = months_passed // 6
        
        return base_semester + semesters_passed
    
    def get_start_type(self, student_semester: int) -> int:
        """Get registration type (1=winter start, 2=summer start)"""
        current_date = datetime.now()
        current_is_summer = 4 <= current_date.month <= 9
        semesters_back = student_semester - 1
        
        started_in_summer = current_is_summer if semesters_back % 2 == 0 else not current_is_summer
        return 2 if started_in_summer else 1
    
    def generate_url(self, stupo: str, semester: int) -> str:
        """Generate complete schedule URL with all filter parameters"""
        current_sem = self.get_current_semester()
        start_type = self.get_start_type(semester)
        
        basegroups = f"semester{current_sem}stupo{stupo}einschreibungszeitraum{start_type}fs{semester}"
        base_url = "https://moseskonto.tu-berlin.de/moses/verzeichnis/veranstaltungen/vkpl_stg.html"

        params = [
            f"basegroups={basegroups}",
            "show-pt-pflicht=true",
            "show-pt-wahlpflicht=false", 
            "show-pt-wahl=false",
            "show-lv=true",
            "show-pruefungen=false",
            "show-kleingruppe=false",
            "search=true"
        ]
        
        return f"{base_url}?" + "&".join(params)
    
    def parse_date_from_german(self, date_str: str) -> Optional[datetime]:
        """Parse German date format 'DD.MM.YY' to datetime"""
        try:
            if len(date_str.split('.')[-1]) == 2:
                return datetime.strptime(date_str, "%d.%m.%y")
            else:
                return datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            return None
    
    def parse_schedule_dates(self, schedule_str: str) -> Dict[str, Any]:
        """Parse schedule string and extract date information"""
        result = {
            'is_recurring': False,
            'start_date': None,
            'end_date': None,
            'is_future': False,
            'schedule_type': 'unknown'
        }
        
        if not schedule_str:
            return result
        
        current_year = datetime.now().year
        
        # Check for recurring patterns
        recurring_pattern = r'(\w+)\.\s*(\d{2}\.\d{2})\s*-\s*(\d{2}\.\d{2}\.?\d{2,4}),\s*wöchentlich'
        recurring_match = re.search(recurring_pattern, schedule_str)
        
        if recurring_match:
            result['is_recurring'] = True
            result['schedule_type'] = 'recurring'
            
            start_date_str = recurring_match.group(2) + f".{current_year}"
            end_date_str = recurring_match.group(3)
            
            result['start_date'] = self.parse_date_from_german(start_date_str)
            result['end_date'] = self.parse_date_from_german(end_date_str)
            
            today = datetime.now()
            if result['end_date'] and result['end_date'] >= today:
                result['is_future'] = True
        else:
            # Check for single date pattern
            single_pattern = r'(\w+)\.\s*(\d{2}\.\d{2}\.?\d{2,4})'
            single_match = re.search(single_pattern, schedule_str)
            
            if single_match:
                result['schedule_type'] = 'single'
                date_str = single_match.group(2)
                result['start_date'] = self.parse_date_from_german(date_str)
                result['end_date'] = result['start_date']
                
                today = datetime.now()
                if result['start_date'] and result['start_date'] >= today:
                    result['is_future'] = True
        
        return result
    
    async def fetch_page_async(self, url: str) -> str:
        try:
            response = await self.client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching page: {e}")
            return ""
    
    def extract_popover_data(self, event_element) -> Dict[str, str]:
        """Extract data from hidden popover content"""
        popover_data = {}
        
        content_div = event_element.find("div", class_="content", style="display: none")
        if not content_div:
            return popover_data
        
        labels = content_div.find_all("label")
        for label in labels:
            label_text = label.get_text(strip=True)
            
            next_element = label.next_sibling
            while next_element:
                if next_element.name == "br":
                    value_element = next_element.next_sibling
                    if value_element and hasattr(value_element, 'get_text'):
                        popover_data[label_text] = value_element.get_text(strip=True)
                    elif isinstance(value_element, str):
                        popover_data[label_text] = value_element.strip()
                    break
                next_element = next_element.next_sibling
        
        return popover_data
    
    def extract_visible_data(self, event_element) -> Dict[str, str]:
        """Extract data from visible part of event"""
        visible_data = {}
        
        # Course name
        name_link = event_element.find("a", {"data-testid": "veranstaltung-name"})
        if name_link:
            visible_data["course_name"] = name_link.get_text(strip=True)
        
        # Location
        location_element = event_element.find("small", {"data-testid": "ort"})
        if location_element:
            visible_data["location"] = location_element.get_text(strip=True)
        
        # Group and instructor from small elements
        small_elements = event_element.find_all("small", class_="ellipsis")
        for i, small in enumerate(small_elements):
            text = small.get_text(strip=True)
            if i == 0 and "Termingruppe" in text:
                visible_data["group"] = text
            elif small.find("a") and not small.get("data-testid"):
                visible_data["instructor"] = text
        
        return visible_data
    
    def parse_lectures_from_html(self, html_content: str, filter_dates: bool = True) -> List[Dict[str, Any]]:
        """Parse lectures from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        lectures = []
        
        events = soup.find_all("div", class_="moses-calendar-event-wrapper")
        
        for event in events:
            try:
                popover_data = self.extract_popover_data(event)
                visible_data = self.extract_visible_data(event)
                
                # Only include lectures
                event_format = popover_data.get("Format", "")
                if "Vorlesung" not in event_format:
                    continue
                
                # Skip lectures without location
                location = visible_data.get("location", popover_data.get("Ort", ""))
                if "Ohne Ort" in location or not location.strip():
                    continue
                
                time_schedule = popover_data.get("Datum/Uhrzeit", "")
                
                # Apply date filtering if enabled
                if filter_dates:
                    date_info = self.parse_schedule_dates(time_schedule)
                    if not date_info['is_future']:
                        continue
                
                # Create lecture data with only required fields
                lecture = {
                    "course_name": visible_data.get("course_name", "Unknown"),
                    "instructor": popover_data.get("Dozierende", visible_data.get("instructor", "")),
                    "location": location,
                    "time_schedule": time_schedule,
                    "lv_number": popover_data.get("LV-Nummer", "")  # Keep for uniqueness
                }
                
                lectures.append(lecture)
                
            except Exception as e:
                print(f"Error parsing event: {e}")
                continue
        
        return lectures
    
    async def get_student_lectures(
        self, 
        stupo: str, 
        semester: int, 
        filter_dates: bool = True
    ) -> List[StudentLecture]:
        """
        Get lectures for a student (identical pattern to ALL other providers)
        
        Args:
            stupo: Studienordnung number
            semester: Student's current semester
            filter_dates: Filter out past lectures (default: True)
            
        Returns:
            List of current/future lectures
        """
        try:
            cache_key = f"student_lectures:{stupo}:{semester}:{filter_dates}"
            cached_result = await moses_cache.get(cache_key)
            if cached_result:
                try:
                    return [StudentLecture(**lecture) for lecture in cached_result]
                except Exception as e:
                    print(f"Error deserializing cached lectures: {str(e)}")
            
            url = self.generate_url(stupo, semester)
            html_content = await self.fetch_page_async(url)
            
            if not html_content:
                return []
            
            lectures_data = self.parse_lectures_from_html(html_content, filter_dates)
            
            lectures = [StudentLecture(**lecture_data) for lecture_data in lectures_data]
            
            try:
                serializable_lectures = [lecture.model_dump() for lecture in lectures]
                await moses_cache.set(cache_key, serializable_lectures)
            except Exception as e:
                print(f"Error caching lectures: {str(e)}")
            
            return lectures
            
        except Exception as e:
            print(f"Error getting student lectures: {str(e)}")
            return []