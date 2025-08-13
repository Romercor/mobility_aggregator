# providers/room.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from providers.moses import StudentScheduleProvider  # наследуемся, чтобы переиспользовать парсинг

class RoomScheduleProvider(StudentScheduleProvider):
    """Provider for TU Berlin room schedule (single day view)"""

    def generate_url(self, room_id: str, date: str) -> str:
        """
        Build the URL for the room schedule.
        Example:
        https://moseskonto.tu-berlin.de/moses/verzeichnis/veranstaltungen/raum.html
        ?location=raum77&search=true&calendartab=SINGLE_DAY&farbgebung=RAUM&singleday=2025-10-31
        """
        base_url = "https://moseskonto.tu-berlin.de/moses/verzeichnis/veranstaltungen/raum.html"
        params = [
            f"location={room_id}",
            "search=true",
            "calendartab=SINGLE_DAY",
            "farbgebung=RAUM",
            f"singleday={date}",
            "ausweichtermine=true",
            "einzeltermine=true",
            "bereitungsdauern=false"
        ]
        return f"{base_url}?" + "&".join(params)

    def parse_room_schedule_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Парсинг расписания комнаты (SINGLE_DAY) с извлечением названия, лектора, времени и аудитории.
        Работает и при наличии data-content, и когда данные спрятаны в DOM.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        lectures = []

        events = soup.find_all("div", class_="moses-calendar-event-wrapper")
        for event in events:
            try:
                # Название предмета
                title_el = event.find("a", attrs={"data-testid": "veranstaltung-name"})
                title = title_el.get_text(strip=True) if title_el else None

                lecturer = None
                datetime_text = None
                room = None

                # Блок с подробной информацией
                popover_anchor = event.find("span", class_="popover-anchor")
                if popover_anchor:
                    # Если есть data-content — парсим его
                    if popover_anchor.has_attr("data-content"):
                        popover_html = BeautifulSoup(popover_anchor["data-content"], "html.parser")
                    else:
                        # Если data-content нет — берём сразу вложенный HTML
                        popover_html = popover_anchor

                    for fg in popover_html.find_all("div", class_="form-group"):
                        label = fg.find("label")
                        if not label:
                            continue
                        label_text = label.get_text(strip=True)
                        value_text = fg.get_text(strip=True).replace(label_text, "").strip()
                        if "Dozierende" in label_text:
                            lecturer = value_text
                        elif "Datum/Uhrzeit" in label_text:
                            datetime_text = value_text
                        elif "Ort" in label_text:
                            room = value_text

                # Фоллбек на видимые элементы
                if not lecturer:
                    lect_small = event.find_all("small", class_="ellipsis")
                    for small in lect_small:
                        if small.find("a") and "," in small.get_text():
                            lecturer = small.get_text(strip=True)
                            break

                if not room:
                    loc_small = event.find("small", {"data-testid": "ort"})
                    if loc_small:
                        room = loc_small.get_text(strip=True)

                lectures.append({
                    "title": title,
                    "datetime": datetime_text,
                    "room": room,
                    "lecturer": lecturer
                })

            except Exception as e:
                print(f"Error parsing room event: {e}")
                continue

        return lectures

    async def get_room_schedule(
        self,
        room_id: str,
        date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch and parse the room schedule for a given date.
        """
        url = self.generate_url(room_id, date)
        html_content = await self.fetch_page_async(url)
        if not html_content:
            return []
        return self.parse_room_schedule_from_html(html_content)
