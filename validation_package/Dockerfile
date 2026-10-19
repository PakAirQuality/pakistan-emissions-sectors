# PakEmis national validation package - a clean Linux environment for validate.sh.
#
# Build (needs the network once, for apt and pip):
#     docker build -t pakemis-validation -f environment/container/Dockerfile .
# Run OFFLINE against the package mounted read-only, with logs written to a host folder:
#     docker run --rm --network=none \
#         -v "$PWD":/package:ro -v "$PWD/logs":/package/logs \
#         pakemis-validation ./validate.sh --quick
#     docker run --rm --network=none ... pakemis-validation ./validate.sh --full
#
# The image carries the pinned Python closure from environment/requirements.lock (the
# gridded, parquet and common-draw tests need it), poppler-utils (pdftotext, used by three
# source-extraction tests that otherwise skip) and git-lfs (one raw-data test).
FROM python:3.11-slim

# libgdal-dev and a compiler: fiona 1.10.1 (pinned in requirements.lock) ships no wheel for
# linux/arm64 and builds from source against gdal-config; on x86_64 the wheel is used and
# the headers are simply present. Found by building this image on an Apple-silicon host.
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils git git-lfs make ca-certificates \
        build-essential libgdal-dev gdal-bin \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /package
COPY environment/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

ENV PKINV_ROOT=/package
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHON=python3

CMD ["./validate.sh", "--quick"]
