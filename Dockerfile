ARG KCC_BASE_IMAGE=ghcr.io/ciromattia/kcc@sha256:2d7e34b99e71f696e830c301c4e5c75173e95e2aa51f4dadc0cd0384b2eac2f0
FROM ${KCC_BASE_IMAGE}

WORKDIR /app

COPY pyproject.toml README.md ./
COPY hosted_kcc ./hosted_kcc

RUN python3 -m pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["hosted-kcc"]
