ARG KCC_BASE_IMAGE=ghcr.io/ciromattia/kcc:latest
FROM ${KCC_BASE_IMAGE}

WORKDIR /app

COPY pyproject.toml README.md ./
COPY hosted_kcc ./hosted_kcc

RUN python3 -m pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["hosted-kcc"]
