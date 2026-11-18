import json
import os
import ssl
from typing import Any

import httpx

BASE_URL = "https://esms.moenv.gov.tw"
WS_BASE = f"{BASE_URL}/eco/_ws/wsToiletVote.asmx"


class MoenvClient:
    def __init__(self, timeout_s: float = 30.0) -> None:
        # A custom trusted CA bundle may be needed for the source's certificate chain.
        tls_context = ssl.create_default_context(cafile=os.getenv("MOENV_CA_BUNDLE"))
        self._client = httpx.Client(timeout=timeout_s, verify=tls_context)

    def close(self) -> None:
        self._client.close()

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> Any:
        response = self._client.post(
            f"{WS_BASE}/{endpoint}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        return json.loads(body["d"])

    def get_cities(self) -> list[dict[str, str]]:
        return self._post_json("getCity2", {})

    def get_toilets_by_area(self, area_id: str) -> dict[str, Any]:
        payload = {
            "sAreaId": area_id,
            "vKeyWord": "",
            "ChangingTable": "-1",
            "OpenTime": "-1",
            "ToiletType": "0",
        }
        return self._post_json("getCtrlToilet", payload)
