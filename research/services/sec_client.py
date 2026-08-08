import os

import requests


class SECClient:
    BASE_URL = "https://data.sec.gov"

    def __init__(self):
        self.user_agent = os.getenv("SEC_USER_AGENT")

        if not self.user_agent:
            raise ValueError(
                "SEC_USER_AGENT is missing from the environment."
            )

        self.headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    def get_company_submissions(self, cik):
        padded_cik = str(cik).strip().zfill(10)

        url = (
            f"{self.BASE_URL}/submissions/"
            f"CIK{padded_cik}.json"
        )

        response = requests.get(
            url,
            headers=self.headers,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()
    
    def get_company_facts(self, cik):
        padded_cik = str(cik).strip().zfill(10)

        url = (
            f"{self.BASE_URL}/api/xbrl/companyfacts/"
            f"CIK{padded_cik}.json"
        )

        response = requests.get(
            url,
            headers=self.headers,
            timeout=60,
        )

        response.raise_for_status()

        return response.json()