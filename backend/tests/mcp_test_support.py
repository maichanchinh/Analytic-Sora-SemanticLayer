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
    *[
        {
            "app_id": f"app.{suffix}",
            "display_name": name,
            "package_name": f"example.{suffix}",
            "platform": "android",
            "status": "active",
        }
        for suffix, name in (("c", "Gamma"), ("d", "Delta"), ("e", "Echo"), ("f", "Foxtrot"))
    ],
]

REPORT_DATE = date(2026, 10, 6)

AD_MOB_ROWS = [
    {
        "business_date": REPORT_DATE,
        "app_id": "app.a",
        "country_code": "US",
        "currency_code": "VND",
        "estimated_earnings": 100_000_000,
    },
    {
        "business_date": REPORT_DATE,
        "app_id": "app.a",
        "country_code": "CA",
        "currency_code": "VND",
        "estimated_earnings": 50_000_000,
    },
    {
        "business_date": REPORT_DATE,
        "app_id": "app.b",
        "country_code": "US",
        "currency_code": "VND",
        "estimated_earnings": 200_000_000,
    },
    *[
        {
            "business_date": REPORT_DATE,
            "app_id": f"app.{suffix}",
            "country_code": "US",
            "currency_code": "VND",
            "estimated_earnings": earnings,
        }
        for suffix, earnings in (("c", 300_000_000), ("d", 20_000_000), ("e", 10_000_000), ("f", 5_000_000))
    ],
]

GOOGLE_ADS_ROWS = [
    {
        "business_date": REPORT_DATE,
        "app_id": "app.a",
        "campaign_id": "campaign.a.us",
        "country_code": "US",
        "currency_code": "VND",
        "cost_micros": 20_000_000,
    },
    {
        "business_date": REPORT_DATE,
        "app_id": "app.a",
        "campaign_id": "campaign.a.ca",
        "country_code": "CA",
        "currency_code": "VND",
        "cost_micros": 10_000_000,
    },
    {
        "business_date": REPORT_DATE,
        "app_id": "app.b",
        "campaign_id": "campaign.b.us",
        "country_code": "US",
        "currency_code": "VND",
        "cost_micros": 100_000_000,
    },
    *[
        {
            "business_date": REPORT_DATE,
            "app_id": f"app.{suffix}",
            "campaign_id": f"campaign.{suffix}",
            "country_code": "US",
            "currency_code": "VND",
            "cost_micros": cost,
        }
        for suffix, cost in (("c", 0), ("d", 10_000_000), ("e", 5_000_000), ("f", 5_000_000))
    ],
]

GA4_ROWS = [
    {
        "business_date": REPORT_DATE,
        "app_id": "app.a",
        "country_code": "US",
        "account_id": "account.a",
        "property_id": "property.a",
        "property_name": "Alpha",
        "mapping_status": "mapped",
        "active_users": 10,
        "new_users": 3,
        "sessions": 12,
        "engaged_sessions": 9,
        "screen_page_views": 30,
        "total_revenue": 0,
    },
    {
        "business_date": REPORT_DATE,
        "app_id": "app.a",
        "country_code": "CA",
        "account_id": "account.a",
        "property_id": "property.a",
        "property_name": "Alpha",
        "mapping_status": "mapped",
        "active_users": 5,
        "new_users": 2,
        "sessions": 6,
        "engaged_sessions": 4,
        "screen_page_views": 15,
        "total_revenue": 0,
    },
    {
        "business_date": REPORT_DATE,
        "app_id": "app.b",
        "country_code": "US",
        "account_id": "account.b",
        "property_id": "property.b",
        "property_name": "Beta",
        "mapping_status": "mapped",
        "active_users": 8,
        "new_users": 4,
        "sessions": 10,
        "engaged_sessions": 7,
        "screen_page_views": 25,
        "total_revenue": 0,
    },
    *[
        {
            "business_date": REPORT_DATE,
            "app_id": f"app.{suffix}",
            "country_code": "US",
            "account_id": f"account.{suffix}",
            "property_id": f"property.{suffix}",
            "property_name": name,
            "mapping_status": "mapped",
            "active_users": active_users,
            "new_users": new_users,
            "sessions": active_users + new_users,
            "engaged_sessions": active_users,
            "screen_page_views": active_users * 2,
            "total_revenue": 0,
        }
        for suffix, name, active_users, new_users in (
            ("c", "Gamma", 1, 1),
            ("d", "Delta", 2, 1),
            ("e", "Echo", 3, 1),
            ("f", "Foxtrot", 4, 2),
        )
    ],
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
        if name == "admob_mediation_daily":
            return self.backend.create_table(name, AD_MOB_ROWS)
        if name == "google_ads_campaign_geo_daily":
            return self.backend.create_table(name, GOOGLE_ADS_ROWS)
        if name == "fx_daily":
            return self.backend.create_table(
                name,
                [
                    {
                        "business_date": REPORT_DATE,
                        "base_currency": "VND",
                        "quote_currency": "USD",
                        "rate_date": REPORT_DATE,
                        "rate_provider": "fixture",
                        "rate": 0.00004,
                    }
                ],
            )
        if name == "ga4_daily_overview":
            return self.backend.create_table(name, GA4_ROWS)
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
