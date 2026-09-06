from pprint import pprint

from m365.sharepoint import SharePoint


def main():

    sp = SharePoint()

    drive = sp.get_default_drive("INTELIGENCIACOMERCIAL")

    if drive is None:
        print("Drive not found.")
        return

    call_center = sp.get_item(
        drive_id=drive["id"],
        item_name="32.- Call Center",
    )

    if call_center is None:
        print("Folder not found.")
        return

    brenda = sp.get_item(
        drive_id=drive["id"],
        folder_id=call_center["id"],
        item_name="Brenda Call.xlsx",
    )

    if brenda is None:
        print("File not found.")
        return

    pprint(brenda)


if __name__ == "__main__":
    main()