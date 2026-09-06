from pprint import pprint

from m365.sharepoint import SharePoint


def main():

    sp = SharePoint()

    site = sp.get_site("INTELIGENCIACOMERCIAL")

    if site is None:
        print("Site not found.")
        return

    drive = sp.get_drive(site["id"], "Documentos")

    if drive is None:
        print("Drive not found.")
        return

    items = sp.list_items(drive["id"])

    pprint(items)


if __name__ == "__main__":
    main()