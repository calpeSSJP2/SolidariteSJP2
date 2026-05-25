# system_monitor/utils.py

import requests


def get_location(ip):

    try:
        response = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=3
        )

        data = response.json()

        return {
            "country": data.get("country_name", ""),
            "city": data.get("city", ""),
        }

    except Exception:
        return {
            "country": "",
            "city": "",
        }