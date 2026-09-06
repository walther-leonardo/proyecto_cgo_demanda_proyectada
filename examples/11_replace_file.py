from pathlib import Path

from m365.sharepoint import SharePoint


SITE_NAME = "INTELIGENCIACOMERCIAL"
FOLDER_NAME = "32.- Call Center"
FILE_NAME = "Brenda Call.xlsx"


def main():

    sp = SharePoint()

    drive = sp.get_default_drive(SITE_NAME)

    folder = sp.get_item(
        drive["id"],
        FOLDER_NAME,
    )

    file = sp.get_item(
        drive["id"],
        FILE_NAME,
        folder["id"],
    )

    local_file = Path("downloads") / FILE_NAME

    updated = sp.replace_file(
        local_file=str(local_file),
        item=file,
    )

    print()
    print("File replaced successfully.")
    print(updated["lastModifiedDateTime"])


if __name__ == "__main__":
    main()