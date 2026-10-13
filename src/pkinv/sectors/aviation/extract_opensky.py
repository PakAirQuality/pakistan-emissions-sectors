"""CLI for permissioned FY2023-24 OpenSky extraction."""
from pkinv.sectors.aviation.opensky import extract


def main():
    for name, result in extract().items():
        print("%s: %d rows -> %s" % (name, result["rows"], result["path"]))


if __name__ == "__main__":
    main()
