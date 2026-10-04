from datetime import date

import ibis


APP_ROWS = [
    {
        "app_id": "app.b",
        "display_name": "Beta",
        "package_name": "example.beta",
        "platform": "android",
        "status": "active",
    },
    {
        "app_id": "app.a",
        "display_name": "Alpha",
        "package_name": "example.alpha",
        "platform": "android",
        "status": "active",
    },
]


class InMemorySilverSource:
    def __init__(self):
        self.backend = ibis.duckdb.connect()
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True
        return self

    def table(self, name):
        if name == "dim_app":
            return self.backend.create_table(name, APP_ROWS)
        if name == "dim_date":
            return self.backend.create_table(
                name,
                [
                    {
                        "date": date(2026, 10, day),
                        "year": 2026,
                        "quarter": 4,
                        "month": 10,
                        "week": 40,
                        "day_of_month": day,
                        "day_of_week": date(2026, 10, day).isoweekday(),
                        "month_start": date(2026, 10, 1),
                        "week_start": date(2026, 9, 28),
                        "is_weekend": date(2026, 10, day).weekday() >= 5,
                    }
                    for day in (1, 2, 3)
                ],
            )
        raise KeyError(name)

    def close(self):
        self.closed = True
        self.backend.disconnect()


def make_source():
    return InMemorySilverSource()
