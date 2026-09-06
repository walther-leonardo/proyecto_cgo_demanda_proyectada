from pprint import pprint

from m365.sharepoint import SharePoint


def main():

    sp = SharePoint()

    drive = sp.get_default_drive("INTELIGENCIACOMERCIAL")

    if drive is None:
        print("Drive not found.")
        return

    root_items = sp.list_items(drive["id"])

    call_center = None

    for item in root_items:
        if item["name"] == "32.- Call Center":
            call_center = item
            break

    if call_center is None:
        print("Folder not found.")
        return

    print("\nFolder found:\n")
    pprint(call_center)

    print("\nContents:\n")

    items = sp.list_items(
        drive["id"],
        folder_id=call_center["id"]
    )

    pprint(items)


if __name__ == "__main__":
    main()