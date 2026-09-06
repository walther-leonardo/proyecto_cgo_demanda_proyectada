from pprint import pprint

from m365.sharepoint import SharePoint


def main():

    sp = SharePoint()

    sites = sp.search_sites("INTELIGENCIACOMERCIAL")

    pprint(sites)


if __name__ == "__main__":
    main()