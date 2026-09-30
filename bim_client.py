import requests


BASE_URL = "http://localhost:48884/bim-brain"


def get_schema():
    r = requests.get(
        BASE_URL + "/schema"
    )
    r.raise_for_status()
    return r.json()


def query_elements(category, filters, fields):
    r = requests.post(
        BASE_URL + "/query",
        json={
            "category": category,
            "filters": filters,
            "fields": fields
        }
    )
    r.raise_for_status()
    return r.json()["results"]


def aggregate_elements(
    category,
    filters,
    group_by,
    metric,
    field
):
    r = requests.post(
        BASE_URL + "/aggregate",
        json={
            "category": category,
            "filters": filters,
            "group_by": group_by,
            "metric": metric,
            "field": field
        }
    )
    r.raise_for_status()
    return r.json()