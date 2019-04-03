# Stage: base
FROM python:3.6.8-alpine AS base

LABEL maintainers="andy.driver@digital.justice.gov.uk,aldo.giambelluca@digital.justice.gov.uk"

WORKDIR /home/idler

RUN adduser -D -u 4242 idler

ADD requirements.txt requirements.txt
RUN apk update && \
    apk add --virtual build-dependencies build-base gcc libffi-dev openssl-dev && \
    pip install -U pip && \
    pip install -r requirements.txt && \
    apk del build-dependencies

COPY idler.py metrics_api.py ./
RUN chown -R idler:idler .

CMD ["python", "idler.py"]


# Stage: test
FROM base AS test

COPY test/requirements.txt test/
RUN pip install -r test/requirements.txt

COPY test test/
RUN pytest test


# Stage: final
FROM base
USER idler
