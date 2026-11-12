ARG COMPONENTS_SAGEMAKER_SHIM_VERSION=0.9.0

######################
#  Builder Container #
######################
# Compiles the python virtual environments. This stage contains the full
# build toolchain (gcc and the -dev headers) required to build C extensions
# such as psycopg[c]. None of these build tools are carried into the runtime
# image: only the resulting virtual environments are copied across.
FROM python:3.14-slim-trixie AS builder

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # wget (and TLS roots) for fetching pre-built tooling below
        wget \
        ca-certificates \
        # postgres and gcc packages for building psycopg[c]
        libpq-dev \
        gcc \
        # for python-magic
        libmagic1 \
        # openslide and vips development headers for building panimg deps
        libopenslide-dev \
        libvips-dev \
    && rm -rf /var/lib/apt/lists/*

# Selects the sagemaker-shim release downloaded below. Must stay in sync with
# the COMPONENTS_SAGEMAKER_SHIM_VERSION declared in the base stage, which the
# app reads at runtime to locate and version-check the shim binary.
ARG COMPONENTS_SAGEMAKER_SHIM_VERSION

# Fetch and unpack dart-sass for compiling scss
RUN mkdir -p /opt/dart-sass \
    && wget https://github.com/sass/dart-sass/releases/download/1.107.0/dart-sass-1.107.0-linux-arm64.tar.gz -O /opt/dart-sass/src.tar.gz \
    && echo "df6b06b97c722f70facedd40efa10ddc625ece905ebd581347881ea398762f7f  /opt/dart-sass/src.tar.gz" | shasum -c - || exit 1 \
    && tar -C /opt/dart-sass/ --strip-components=1 -xzvf /opt/dart-sass/src.tar.gz \
    && rm /opt/dart-sass/src.tar.gz

# Fetch and unpack crane for pushing containers
RUN mkdir -p /opt/crane \
    && wget https://github.com/google/go-containerregistry/releases/download/v0.21.1/go-containerregistry_Linux_arm64.tar.gz -O /opt/crane/src.tar.gz \
    && echo "2ca7e6beca62cb289ee8e4089801e6d0d934508ae827cf7ca8f54fd6fcbadc54  /opt/crane/src.tar.gz" | shasum -c - || exit 1 \
    && tar -C /opt/crane/ -xzvf /opt/crane/src.tar.gz crane \
    && chmod a+x /opt/crane/crane

# Fetch and unpack sagemaker shim for shimming containers
RUN mkdir -p /opt/sagemaker-shim \
    && wget "https://github.com/DIAGNijmegen/rse-sagemaker-shim/releases/download/v${COMPONENTS_SAGEMAKER_SHIM_VERSION}/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" -P /opt/sagemaker-shim/ \
    && echo "03bd0e80fee4e7c800cb697da4f4af5e1448a2db3eec2b8ef9b1376aafdd7fb5  /opt/sagemaker-shim/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" | shasum -c - || exit 1 \
    && tar -C /opt/sagemaker-shim/ -xzvf "/opt/sagemaker-shim/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" \
    && rm "/opt/sagemaker-shim/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" \
    && chmod -R a+rX /opt/sagemaker-shim

RUN mkdir -p /opt/grand-challenge /opt/virtualenvs

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create isolated virtual environments from locked dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=virtualenvs/biom/pyproject.toml,target=/tmp/biom/pyproject.toml \
    --mount=type=bind,source=virtualenvs/biom/uv.lock,target=/tmp/biom/uv.lock \
    UV_PROJECT_ENVIRONMENT=/opt/virtualenvs/biom \
    uv sync --frozen --no-install-project --project /tmp/biom

WORKDIR /opt/grand-challenge

# Install base python packages
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

###################
#  Base Container #
###################
# The runtime base. Contains only the shared libraries required to *run* the
# compiled dependencies (not the -dev headers) and no compiler. The virtual
# environments are copied in from the builder stage.
FROM python:3.14-slim-trixie AS base

# Install runtime system dependencies.
# These are the runtime shared-library counterparts of the -dev packages used
# in the builder stage. gcc, the -dev headers, and wget are deliberately
# absent: pre-built tooling is fetched in the builder stage and copied in.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # postgres runtime library for psycopg[c]
        libpq5 \
        # for python-magic
        libmagic1 \
        # openslide and vips runtime libraries for image imports with panimg
        libopenslide0 \
        libvips42t64 \
        # git for CodeBuild integration
        git \
    && rm -rf /var/lib/apt/lists/*

# Install dart-sass (for compiling scss), fetched in the builder stage
COPY --from=builder /opt/dart-sass /opt/dart-sass
ENV PATH="/opt/dart-sass/:${PATH}"

# Install crane (for pushing containers), fetched in the builder stage
COPY --from=builder /opt/crane/crane /usr/local/bin/crane

# Must stay in sync with the COMPONENTS_SAGEMAKER_SHIM_VERSION in the
# builder stage: that value selects the downloaded shim binary, this one is
# read by the app at runtime to locate and version-check it.
ARG COMPONENTS_SAGEMAKER_SHIM_VERSION
ENV COMPONENTS_SAGEMAKER_SHIM_VERSION=${COMPONENTS_SAGEMAKER_SHIM_VERSION}\
    PYTHONUNBUFFERED=1\
    PATH="/opt/grand-challenge/.venv/bin:/home/django/.local/bin:${PATH}"

RUN mkdir -p /opt/grand-challenge /app /static /opt/sagemaker-shim /opt/virtualenvs /opt/vendored \
    && groupadd -r django && useradd -m -r -g django django \
    && chown django:django /opt/grand-challenge /app /static /opt/sagemaker-shim /opt/virtualenvs /opt/vendored

# Install sagemaker shim (for shimming containers), fetched in the builder stage
COPY --from=builder --chown=django:django /opt/sagemaker-shim /opt/sagemaker-shim

USER django:django

# Copy the pre-built virtual environments from the builder stage. The paths are
# identical to the builder so the environments resolve without relocation.
# No --chown: the venvs are only read at runtime (never written), so leaving
# them root-owned and world-readable avoids rewriting every file into a new
# layer with changed ownership.
COPY --from=builder /opt/virtualenvs /opt/virtualenvs
COPY --from=builder /opt/grand-challenge/.venv /opt/grand-challenge/.venv

WORKDIR /opt/grand-challenge

# Install the vendored frontend assets (js/css/fonts) with amass. These are
# not committed to the repository, so they are fetched here at build time.
# Running this in the base stage means both the test and dist stages inherit
# the assets. They are installed to /opt/vendored/static, outside /app, so
# that the development bind mount of ./app over /app does not shadow them: the
# same baked-in assets are used in development, test and production.
RUN --mount=type=bind,source=pyproject.toml,target=/opt/grand-challenge/pyproject.toml \
    --mount=type=bind,source=amass.lock,target=/opt/grand-challenge/amass.lock \
    amass install --output /opt/vendored/static

##################
# TEST CONTAINER #
##################
# Extends base with the build toolchain (so dev dependencies with C extensions
# can be installed) plus documentation and browser-testing tooling. This image
# is never shipped to production.
FROM base AS test

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # build toolchain for compiling dev dependencies
        libpq-dev \
        gcc \
        # Add java and graphviz for plantuml documentation
        default-jre \
        graphviz \
        # make for sphinx docs
        make \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# The main venv is copied root-owned in the base stage (it is read-only in
# dist). The test stage installs dev dependencies into it, so hand ownership
# to django here. This rewrites the venv into a new layer, but only in the
# test image, which is never shipped.
RUN chown -R django:django /opt/grand-challenge/.venv
USER django:django

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

USER root
RUN playwright install-deps chromium
USER django:django
RUN playwright install chromium

COPY --chown=django:django setup.cfg /home/django

WORKDIR /app
RUN mkdir /tmp/.pytest_cache
COPY --chown=django:django ./app/ /app/

##################
# Dist Container #
##################
# The production image. Built from base, so it contains no compiler and no
# -dev headers.
FROM base AS dist

WORKDIR /app
COPY --chown=django:django ./app/ /app/

ARG COMMIT_ID=unknown
ENV COMMIT_ID=$COMMIT_ID

RUN python manage.py collectstatic --noinput && GRAND_CHALLENGE_USE_LOC_MEM_CACHE=true python manage.py compress --force
