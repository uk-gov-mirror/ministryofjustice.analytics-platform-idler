FROM python:3.6.4-alpine AS base

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

WORKDIR /home/idler
RUN apk update && apk add --virtual build-dependencies build-base gcc libffi-dev openssl-dev

ADD requirements.txt requirements.txt
RUN pip install -U pip && pip install -r requirements.txt
RUN apk del build-dependencies

ADD idler.py idler.py
ADD metrics_api.py metrics_api.py

CMD ["python", "idler.py"]


FROM base AS test

ADD test/requirements.txt test/
RUN pip install -r test/requirements.txt

ADD test test

RUN pytest test

FROM base
