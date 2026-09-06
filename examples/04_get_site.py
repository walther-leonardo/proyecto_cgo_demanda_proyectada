from pprint import pprint

from m365.sharepoint import SharePoint


def main():

    sp = SharePoint()

    site = sp.get_site("INTELIGENCIACOMERCIAL")

    if site is None:
        print("Site not found.")
        return

    pprint(site)


if __name__ == "__main__":
    main()