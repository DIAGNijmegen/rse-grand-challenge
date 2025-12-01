FROM --platform=linux/amd64 public.ecr.aws/deep-learning-containers/pytorch-inference:2.6.0-cpu-py312-ubuntu22.04-sagemaker AS example_evaluation_amd64
# When in need of a GPU, use the CUDA enabled: public.ecr.aws/deep-learning-containers/pytorch-inference:2.6.0-gpu-py312-cu124-ubuntu22.04-sagemaker
# These are sourced from: https://gallery.ecr.aws/deep-learning-containers/pytorch-inference

# By using this brand of SageMaker-ready container images you get the benefit from reduced
# pulling time in the runtime environment: making it more cost efficient.

# Note: a SageMaker-branded container image is not required for an algorithm to work:
# using other containers as a base will work.

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
