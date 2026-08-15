import time
import requests
from typing import Optional


VK_API_VERSION = "5.199"
VK_API_BASE = "https://api.vk.com/method"


class VKClient:
    def __init__(self, access_token: str):
        self._token = access_token
        self._session = requests.Session()

    def _call(self, method: str, params: dict) -> dict:
        params["access_token"] = self._token
        params["v"] = VK_API_VERSION
        last_err = None
        for attempt in range(3):
            try:
                response = self._session.get(f"{VK_API_BASE}/{method}", params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    raise ValueError(f"VK API error {data['error']['error_code']}: {data['error']['error_msg']}")
                return data["response"]
            except ValueError:
                raise
            except Exception as e:
                last_err = e
                time.sleep(2 * (attempt + 1))
        raise last_err

    def get_user(self, user_id: str) -> dict:
        result = self._call("users.get", {"user_ids": user_id, "fields": "photo_50"})
        return result[0]

    def get_friends(self, user_id: int) -> list[dict]:
        try:
            result = self._call(
                "friends.get",
                {"user_id": user_id, "fields": "first_name,last_name,photo_50,is_closed"},
            )
            return result.get("items", [])
        except ValueError:
            return []

    def get_mutual_friends(self, source_uid: int, target_uids: list[int]) -> dict[int, list[int]]:
        """Батчевый запрос общих друзей через execute."""
        result: dict[int, list[int]] = {}
        batch_size = 25

        for i in range(0, len(target_uids), batch_size):
            batch = target_uids[i : i + batch_size]
            target_str = ",".join(str(uid) for uid in batch)
            try:
                data = self._call(
                    "friends.getMutual",
                    {"source_uid": source_uid, "target_uids": target_str},
                )
                for item in data:
                    result[item["id"]] = item.get("common_friends", [])
            except ValueError:
                pass
            time.sleep(0.34)  # VK rate limit: ~3 req/sec

        return result
