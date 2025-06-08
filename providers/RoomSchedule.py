import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta


def get_room_schedule(room_number, date):
    #date_obj = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)  # уменьшение даты
    #date = date_obj.strftime("%Y-%m-%d")
    session = requests.Session()
    base_url = "https://moseskonto.tu-berlin.de/moses/verzeichnis/veranstaltungen/raum.html"
    date_input = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")

    params = {"location": f"raum{room_number}",
              "search": "true",
              "calendartab": "SINGLE_DAY",
              "dateforweek": date,
              "singleday": date}
    resp = session.get(base_url, params=params)
    with open(f"debug_get_{room_number}_{date}.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    soup = BeautifulSoup(resp.text, "html.parser")
    vs_tag = soup.find("input", {"name": "javax.faces.ViewState"})
    if not vs_tag:
        return []
    view_state = vs_tag["value"]

    single_day_input = soup.find("input", {"name": re.compile(r".*single-day-date_date$")})
    if not single_day_input:
        return []
    match = re.match(r"(.*):single-day-date_date", single_day_input["name"])
    if not match:
        return []
    form_id = match.group(1)

    headers = {
        "Faces-Request": "partial/ajax",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    data = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": f"{form_id}:j_idt4953",
        "javax.faces.partial.execute": f"{form_id}:j_idt4953 {form_id}:calendar",
        "javax.faces.partial.render": f"{form_id}:calendar-including-filter",
        f"{form_id}:j_idt4953": f"{form_id}:j_idt4953",
        "javax.faces.ViewState": view_state,
        f"{form_id}:single-day-date_input": date_input,
        f"{form_id}:single-day-date": date_input,
        f"{form_id}:single-day-date_date": date_input
    }
    resp = session.post(base_url, params=params, headers=headers, data=data)
    with open(f"debug_post1_{room_number}_{date}.xml", "w", encoding="utf-8") as f:
        f.write(resp.text)
    soup = BeautifulSoup(resp.text, "xml")
    vs_update = soup.find("update", {"id": re.compile(r".*ViewState$")})
    if vs_update:
        view_state = vs_update.text

    data = {
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": f"{form_id}:j_idt4957",
        "javax.faces.partial.execute": f"{form_id}:j_idt4957 {form_id}:calendar",
        "javax.faces.partial.render": f"{form_id}:calendar-including-filter",
        f"{form_id}:j_idt4957": f"{form_id}:j_idt4957",
        "javax.faces.ViewState": view_state,
        f"{form_id}:single-day-date_input": date_input,
        f"{form_id}:single-day-date": date_input,
        f"{form_id}:single-day-date_date": date_input,
    }
    resp = session.post(base_url, params=params, headers=headers, data=data)
    with open(f"debug_post2_{room_number}_{date}.xml", "w", encoding="utf-8") as f:
        f.write(resp.text)
    soup = BeautifulSoup(resp.text, "xml")
    upd_tag = soup.find("update", {"id": f"{form_id}:calendar-including-filter"})
    if not upd_tag:
        return []

    schedule_soup = BeautifulSoup(upd_tag.text, "html.parser")
    events = []
    for div in schedule_soup.find_all("div", class_="moses-calendar-event-wrapper"):
        item = {}
        title_tag = div.find("a", {"data-testid": "veranstaltung-name"})
        if title_tag:
            item["title"] = title_tag.get_text(strip=True)
        datetime_label = div.find("label", string="Datum/Uhrzeit")
        if datetime_label and datetime_label.parent:
            item["datetime"] = datetime_label.parent.find_next("br").next_sibling.strip()
        room_label = div.find("label", string="Ort")
        if room_label and room_label.parent:
            item["room"] = room_label.parent.find_next("br").next_sibling.strip()
        lecturer_label = div.find("label", string="Dozierende")
        if lecturer_label and lecturer_label.parent:
            item["lecturer"] = lecturer_label.parent.find_next("br").next_sibling.strip()
        if item:
            events.append(item)

    return events