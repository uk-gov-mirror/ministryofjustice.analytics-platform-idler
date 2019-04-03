FROM python:3.6.8-alpine AS base

LABEL maintainers="andy.driver@digital.justice.gov.uk,aldo.giambelluca@digital.justice.gov.uk"

WORKDIR /home/idler
RUN apk update && apk add --virtual build-dependencies build-base gcc libffi-dev openssl-dev

ADD requirements.txt requirements.txt
RUN pip install -U pip && pip install -r requirements.txt
RUN apk del build-dependencies

COPY idler.py metrics_api.py ./

CMD ["python", "idler.py"]


FROM base AS test

COPY test/requirements.txt test/
RUN pip install -r test/requirements.txt

COPY test test/

RUN pytest test

FROM base
