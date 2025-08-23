import requests
import crud
from database import SessionLocal
import jdatetime
from datetime import timedelta

KEY_MAP = {
    "co_code": "کد کمپانی",
    "company_name": "نام کمپانی",
    "Phase": "فاز",
    "customer_type": "نوع مشتری",
    "customer_name": "نام مشتری",
    "customer_family": "نام خانوادگی مشتری",
    "serial_number": "شماره سریال",
    "total_bill_debt": "کل بدهی قبض",
    "mobile_number": "شماره موبایل",
    "site_address": "آدرس سایت",
    "subscriber_base": "پایه مشترک",
    "company_address": "آدرس کمپانی",
    "company_phone": "تلفن کمپانی",
    "answering_phone": "تلفن پاسخگو",
    "city": "شهر",
}

def translate_json_to_persian(data: dict) -> str:
    """
    Convert JSON keys to Persian and return a formatted string.
    """
    lines = []
    for key, value in data.items():
        if key not in KEY_MAP: continue
        persian_key = KEY_MAP.get(key)
        lines.append(f"{persian_key}: {value}")
    return "\n".join(lines)

def get_jalali_date_range():
    today_jalali = jdatetime.date.today()
    three_days_later = today_jalali + timedelta(days=3)
    from_date = today_jalali.strftime("%Y/%m/%d")
    to_date = three_days_later.strftime("%Y/%m/%d")
    return from_date, to_date

class GetAPI:
    headers = {}
    proxies = {
        "http": "socks5h://127.0.0.1:50000",
        "https": "socks5h://127.0.0.1:50000"
    }

    def __init__(self):
        self.servers_bearer_token = {}
        self.session = requests.Session()
        self.refresh_connection()

    @classmethod
    def get_new_header(cls):
        with SessionLocal() as session:
            token = crud.get_token(session, "blackout_report_token")
            cls.headers["Authorization"] = token.token

    @classmethod
    def get_header(cls):
        if not cls.headers:
            cls.get_new_header()
        return cls.headers

    def refresh_connection(self):
        """Refresh access tokens for all servers."""
        pass

    def make_request(self, method, url, timeout=20, **kwargs):
        """Make an HTTP request and return JSON response."""
        response = self.session.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_power_bill_data(self, bill_identifier):
        """Retrieve access token for a given server."""
        url = 'https://uiapi2.saapa.ir/api/ebills/GetPowerBillData'
        data = {'bill_identifier': str(bill_identifier)}
        return self.make_request('post', url=url, json=data, headers=self.get_header(), proxies=self.proxies)

    def get_planned_blackout_report(self, bill_id, from_date, to_date):
        """Retrieve access token for a given server."""
        url = 'https://uiapi2.saapa.ir/api/ebills/GetPowerBillData'
        data = {'bill_id': bill_id, 'from_date': from_date, 'to_date': to_date}
        return self.make_request('post', url=url, json=data, headers=self.get_header(), proxies=self.proxies)
