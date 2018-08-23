FROM python:3.6.4-alpine AS base

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

WORKDIR /home/idler

ADD requirements.txt requirements.txt
RUN pip install -U pip && pip install -r requirements.txt

ADD idler.py idler.py
ADD metrics_api.py metrics_api.py

CMD ["python", "idler.py"]


FROM base AS test

RUN pip install pytest

ADD test test

RUN pytest test


FROM base
