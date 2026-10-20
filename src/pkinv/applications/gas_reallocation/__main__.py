"""python3 -m pkinv.applications.gas_reallocation: write the products, then draw the two figures."""
import sys

from . import build, figures

if __name__ == "__main__":
    code = build.main(sys.argv[1:])
    figures.main()
    sys.exit(code)
