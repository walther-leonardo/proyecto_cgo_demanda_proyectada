from m365.auth import Auth


def main():

    auth = Auth()

    token = auth.get_access_token()

    print()
    print("Authentication successful!")
    print()

    print(token[:100] + "...")


if __name__ == "__main__":
    main()