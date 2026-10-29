###################
#  Base Container #
###################
FROM python:3.14-slim-bookworm AS base

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpng-dev \
        libjpeg-dev \
        libjpeg62-turbo-dev \
        libfreetype6-dev \
        libxft-dev \
        libffi-dev \
        wget \
        gettext \
        # postgres packages for psycopg2
        libpq-dev \
        # curl and ssl for pycurl
        libcurl4-openssl-dev \
        libssl-dev \
        # for python-magic
        libmagic1 \
        # openslide and vips for image imports with panimg
        # gcc is required to compile the extensions
        libopenslide-dev \
        libvips-dev \
        gcc \
        # ruby3.1, rugged and nokogiri for licensee
        ruby3.1 \
        ruby-rugged \
        ruby-nokogiri \
        # git for CodeBuild integration
        git \
        # for dbshell
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Fetch and install licensee for checking licenses
# Separate install required as the bundled version does not include the --json flag
RUN gem install licensee -v 9.16.1

# Fetch and install dart-sass for compiling scss
RUN mkdir -p /opt/dart-sass \
    && wget https://github.com/sass/dart-sass/releases/download/1.107.0/dart-sass-1.107.0-linux-arm64.tar.gz -O /opt/dart-sass/src.tar.gz \
    && echo "df6b06b97c722f70facedd40efa10ddc625ece905ebd581347881ea398762f7f  /opt/dart-sass/src.tar.gz" | shasum -c - || exit 1 \
    && tar -C /opt/dart-sass/ --strip-components=1 -xzvf /opt/dart-sass/src.tar.gz \
    && rm /opt/dart-sass/src.tar.gz
ENV PATH="/opt/dart-sass/:${PATH}"

# Fetch and install crane for pushing containers
RUN mkdir -p /opt/crane \
    && wget https://github.com/google/go-containerregistry/releases/download/v0.21.1/go-containerregistry_Linux_arm64.tar.gz -O /opt/crane/src.tar.gz \
    && echo "2ca7e6beca62cb289ee8e4089801e6d0d934508ae827cf7ca8f54fd6fcbadc54  /opt/crane/src.tar.gz" | shasum -c - || exit 1 \
    && tar -C /opt/crane/ -xzvf /opt/crane/src.tar.gz crane \
    && chmod a+x /opt/crane/crane \
    && mv /opt/crane/crane /usr/local/bin/ \
    && rm -r /opt/crane

# Fetch and install git lfs for github integration
RUN mkdir -p /opt/git-lfs \
    && wget https://github.com/git-lfs/git-lfs/releases/download/v3.4.1/git-lfs-linux-arm64-v3.4.1.tar.gz -O /opt/git-lfs/src.tar.gz \
    && echo "f93c5070223d95eb44fea0ee2f2db26656793d5f3417366f77dd20b9518c46ce  /opt/git-lfs/src.tar.gz" | shasum --algorithm 256 -c - || exit 1 \
    && tar -C /opt/git-lfs/ -xzvf /opt/git-lfs/src.tar.gz \
    && bash /opt/git-lfs/git-lfs-3.4.1/install.sh \
    && rm -r /opt/git-lfs

ENV PYTHONUNBUFFERED=1\
    AWS_XRAY_SDK_ENABLED=false\
    COMPONENTS_SAGEMAKER_SHIM_VERSION=0.8.3\
    PATH="/opt/grand-challenge/.venv/bin:/home/django/.local/bin:${PATH}"

RUN mkdir -p /opt/grand-challenge /app /static /opt/sagemaker-shim /opt/virtualenvs \
    && groupadd -r django && useradd -m -r -g django django \
    && chown django:django /opt/grand-challenge /app /static /opt/sagemaker-shim /opt/virtualenvs

USER django:django

# Fetch and install sagemaker shim for shimming containers
RUN mkdir -p /opt/sagemaker-shim \
    && wget "https://github.com/DIAGNijmegen/rse-sagemaker-shim/releases/download/v${COMPONENTS_SAGEMAKER_SHIM_VERSION}/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" -P /opt/sagemaker-shim/ \
    && echo "779f50797ef74c8b1d524ee32cd303680130621a324fbbf1059558b7d0ca93bc  /opt/sagemaker-shim/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" | shasum -c - || exit 1 \
    && tar -C /opt/sagemaker-shim/ -xzvf "/opt/sagemaker-shim/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" \
    && rm "/opt/sagemaker-shim/sagemaker-shim-${COMPONENTS_SAGEMAKER_SHIM_VERSION}-Linux-x86_64.tar.gz" \
    && chmod -R a+rX /opt/sagemaker-shim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create isolated virtual environments from locked dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=virtualenvs/biom/pyproject.toml,target=/tmp/biom/pyproject.toml \
    --mount=type=bind,source=virtualenvs/biom/uv.lock,target=/tmp/biom/uv.lock \
    UV_PROJECT_ENVIRONMENT=/opt/virtualenvs/biom \
    uv sync --frozen --no-install-project --project /tmp/biom

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=virtualenvs/panimg/pyproject.toml,target=/tmp/panimg/pyproject.toml \
    --mount=type=bind,source=virtualenvs/panimg/uv.lock,target=/tmp/panimg/uv.lock \
    UV_PROJECT_ENVIRONMENT=/opt/virtualenvs/panimg \
    uv sync --frozen --no-install-project --project /tmp/panimg

WORKDIR /opt/grand-challenge

# Install base python packages
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

##################
# TEST CONTAINER #
##################
FROM base AS test

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # Add java and graphviz for plantuml documentation
        default-jre \
        graphviz \
        # make for sphinx docs
        make \
        # playwright dependencies
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxrandr2 \
        libgbm1 \
        libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*
USER django:django

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project
RUN playwright install

COPY --chown=django:django setup.cfg /home/django

WORKDIR /app
RUN mkdir /tmp/.pytest_cache
COPY --chown=django:django ./app/ /app/

##################
# Dist Container #
##################
FROM base AS dist

WORKDIR /app
COPY --chown=django:django ./app/ /app/

ARG COMMIT_ID=unknown
ENV COMMIT_ID=$COMMIT_ID

RUN python manage.py collectstatic --noinput && GRAND_CHALLENGE_USE_LOC_MEM_CACHE=true python manage.py compress --force
