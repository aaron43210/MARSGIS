# marsgis-engine Makefile — dev / CI convenience targets.
# The engine package lives in this directory; run `make -C engine <target>`.

VERSION := $(shell python3 -c "import re,pathlib;print(re.search(r'\"([^\"]+)\"',pathlib.Path('src/marsgis_engine/_version.py').read_text()).group(1))")
GHCR_OWNER ?= marsgis
IMAGE := ghcr.io/$(GHCR_OWNER)/marsgis-engine

.PHONY: help install test lint typecheck build docker cog-check clean version

help:
	@echo "marsgis-engine targets:"
	@echo "  install    pip install -e .[dev]"
	@echo "  test       pytest (offline, synthetic fixtures)"
	@echo "  lint       ruff check"
	@echo "  typecheck  mypy"
	@echo "  build      python -m build (sdist + wheel)"
	@echo "  docker     docker build -t $(IMAGE):$(VERSION)  (Dockerfile owned by infra)"
	@echo "  cog-check  validate a sample output COG with gdalinfo"
	@echo "  version    print the engine version ($(VERSION))"

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

typecheck:
	mypy

build:
	python -m build

# The Dockerfile is provided by the infra unit at repo root context.
docker:
	docker build -t $(IMAGE):$(VERSION) -f Dockerfile ..

# Validate that a produced angle raster is a real COG (requires GDAL on PATH).
# Usage: make cog-check COG=out/result_SAM_angle.tif
COG ?= out/result_SAM_angle.tif
cog-check:
	@python3 -c "import rasterio; ds=rasterio.open('$(COG)'); \
print('driver', ds.driver); print('tiled', ds.profile.get('tiled')); \
print('overviews', ds.overviews(1)); print('crs', ds.crs); print('nodata', ds.nodata)"

version:
	@echo $(VERSION)

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
