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

    permissions = sp.list_permissions(file)

    print()

    for permission in permissions:
        print(permission)
        print()


if __name__ == "__main__":
    main()