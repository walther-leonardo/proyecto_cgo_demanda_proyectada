import os

import requests

from m365.auth import Auth


class SharePoint:
    """
    Handles Microsoft Graph requests related to
    SharePoint and OneDrive.
    """

    GRAPH_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self):
        self.auth = Auth()

    # ==========================================================
    # Internal Helpers
    # ==========================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ):
        """
        Executes a Microsoft Graph request.

        Parameters
        ----------
        method : HTTP method (GET, POST, PATCH, DELETE...)
        endpoint : Graph endpoint beginning with "/"
        kwargs : Additional arguments passed to requests.request()

        Returns
        -------
        requests.Response
        """

        token = self.auth.get_access_token()

        headers = kwargs.pop("headers", {})

        headers["Authorization"] = f"Bearer {token}"

        response = requests.request(
            method=method,
            url=f"{self.GRAPH_URL}{endpoint}",
            headers=headers,
            **kwargs,
        )

        if not response.ok:
            print("\nHeaders:")
            for key, value in response.headers.items():
                print(f"{key}: {value}")
            print("\n" + "=" * 70)
            print("MICROSOFT GRAPH REQUEST FAILED")
            print("=" * 70)
            print(f"Method : {method}")
            print(f"URL    : {self.GRAPH_URL}{endpoint}")
            print(f"Status : {response.status_code}")
            print("\nResponse:")
            print(response.text)
            print("=" * 70 + "\n")

        response.raise_for_status()

        return response

    # ==========================================================
    # User
    # ==========================================================

    def get_current_user(self):

        response = self._request(
            "GET",
            "/me",
        )

        return response.json()

    # ==========================================================
    # Sites
    # ==========================================================

    def search_sites(self, search_text: str):

        response = self._request(
            "GET",
            "/sites",
            params={"search": search_text},
        )

        return response.json()["value"]

    def get_site(self, site_name: str):

        sites = self.search_sites(site_name)

        if not sites:
            return None

        return sites[0]

    # ==========================================================
    # Drives
    # ==========================================================

    def list_drives(self, site_id: str):

        response = self._request(
            "GET",
            f"/sites/{site_id}/drives",
        )

        return response.json()["value"]

    def get_drive(self, site_id: str, drive_name: str):

        drives = self.list_drives(site_id)

        for drive in drives:
            if drive["name"].lower() == drive_name.lower():
                return drive

        return None

    def get_default_drive(self, site_name: str):

        site = self.get_site(site_name)

        if site is None:
            return None

        return self.get_drive(site["id"], "Documentos")

    # ==========================================================
    # Items
    # ==========================================================

    def list_items(
        self,
        drive_id: str,
        folder_id: str | None = None,
    ):

        if folder_id is None:
            endpoint = f"/drives/{drive_id}/root/children"
        else:
            endpoint = f"/drives/{drive_id}/items/{folder_id}/children"

        response = self._request(
            "GET",
            endpoint,
        )

        return response.json()["value"]

    def get_item(
        self,
        drive_id: str,
        item_name: str,
        folder_id: str | None = None,
    ):

        items = self.list_items(
            drive_id=drive_id,
            folder_id=folder_id,
        )

        for item in items:
            if item["name"].lower() == item_name.lower():
                return item

        return None

    # ==========================================================
    # File Operations
    # ==========================================================

    def download_file(
        self,
        drive_id: str,
        item_id: str,
        destination: str,
    ):

        response = self._request(
            "GET",
            f"/drives/{drive_id}/items/{item_id}/content",
            stream=True,
        )

        folder = os.path.dirname(destination)

        if folder:
            os.makedirs(folder, exist_ok=True)

        with open(destination, "wb") as file:

            for chunk in response.iter_content(chunk_size=8192):

                if chunk:
                    file.write(chunk)

        return destination

    def replace_file(
        self,
        local_file: str,
        item: dict,
    ):

        drive_id = item["parentReference"]["driveId"]
        item_id = item["id"]

        endpoint = (
            f"/drives/{drive_id}"
            f"/items/{item_id}"
            f"/content"
        )

        with open(local_file, "rb") as file:

            response = self._request(
                "PUT",
                endpoint,
                data=file,
                headers={
                    "Content-Type": "application/octet-stream"
                },
            )

        return response.json()

    def list_permissions(
        self,
        item: dict,
    ):
        """
        Lists the permissions assigned to a SharePoint item.
        """

        drive_id = item["parentReference"]["driveId"]
        item_id = item["id"]

        endpoint = (
            f"/drives/{drive_id}"
            f"/items/{item_id}"
            f"/permissions"
        )

        response = self._request(
            "GET",
            endpoint,
        )

        return response.json()["value"]