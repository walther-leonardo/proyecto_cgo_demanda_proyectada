from pathlib import Path

from m365.sharepoint import SharePoint


SITE_NAME = "INTELIGENCIACOMERCIAL"
FOLDER_NAME = "32.- Call Center"
FILE_NAME = "Brenda Call.xlsx"


def main():

    sp = SharePoint()

    drive = sp.get_default_drive(SITE_NAME)

    if drive is None:
        raise RuntimeError("Drive not found.")

    folder = sp.get_item(
        drive_id=drive["id"],
        item_name=FOLDER_NAME,
    )

    if folder is None:
        raise RuntimeError("Folder not found.")

    file = sp.get_item(
        drive_id=drive["id"],
        folder_id=folder["id"],
        item_name=FILE_NAME,
    )

    if file is None:
        raise RuntimeError("File not found.")

    destination = Path("downloads") / FILE_NAME

    downloaded_file = sp.download_file(
        drive_id=drive["id"],
        item_id=file["id"],
        destination=str(destination),
    )

    print()
    print("Download completed.")
    print(downloaded_file)


if __name__ == "__main__":
    main()