from pathlib import Path

import msal
from msal import PublicClientApplication

from m365.config import (
    CLIENT_ID,
    TENANT_ID,
    TOKEN_CACHE_FILE,
)


class Auth:

    SCOPES = [
        "User.Read",
        "Files.ReadWrite",
        "Sites.Read.All",
    ]

    def __init__(self):

        self.authority = (
            f"https://login.microsoftonline.com/{TENANT_ID}"
        )

        self.cache = msal.SerializableTokenCache()

        self._load_cache()

        self.app = PublicClientApplication(
            client_id=CLIENT_ID,
            authority=self.authority,
            token_cache=self.cache,
        )

    def _load_cache(self):

        if TOKEN_CACHE_FILE.exists():

            self.cache.deserialize(
                TOKEN_CACHE_FILE.read_text()
            )

    def _save_cache(self):

        if self.cache.has_state_changed:

            TOKEN_CACHE_FILE.write_text(
                self.cache.serialize()
            )

    def get_access_token(self) -> str:

        accounts = self.app.get_accounts()

        if accounts:

            result = self.app.acquire_token_silent(
                self.SCOPES,
                account=accounts[0],
            )

            if result and "access_token" in result:

                return result["access_token"]

        flow = self.app.initiate_device_flow(
            scopes=self.SCOPES
        )

        if "user_code" not in flow:

            raise RuntimeError(flow)

        print()
        print("=" * 70)
        print(flow["message"])
        print("=" * 70)
        print()

        result = self.app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:

            raise RuntimeError(result)

        self._save_cache()

        return result["access_token"]
    