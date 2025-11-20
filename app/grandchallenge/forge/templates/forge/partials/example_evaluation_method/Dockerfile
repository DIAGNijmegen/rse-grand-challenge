FROM --platform=linux/amd64 docker.io/library/python:3.11-slim AS example-evaluation-amd64

# Ensures that Python output to stdout/stderr is not buffered: prevents missing information when terminating
ENV PYTHONUNBUFFERED=1

RUN groupadd -r user && useradd -m --no-log-init -r -g user user
USER user

WORKDIR /opt/app

COPY --chown=user:user requirements.txt /opt/app/

# You can add any Python dependencies to requirements.txt
RUN python -m pip install \
    --user \
    --no-cache-dir \
    --no-color \
    --requirement /opt/app/requirements.txt

COPY --chown=user:user helpers.py /opt/app/
COPY --chown=user:user evaluate.py /opt/app/

# Setting this will limit the number of workers used by the evaluate.py
ENV GRAND_CHALLENGE_MAX_WORKERS=

ENTRYPOINT ["python", "evaluate.py"]
