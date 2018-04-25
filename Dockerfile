FROM python:3.6.4-alpine

MAINTAINER Andy Driver <andy.driver@digital.justice.gov.uk>

WORKDIR /home/idler

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt

ADD idler.py idler.py
ADD metrics_api.py metrics_api.py

CMD ["python", "idler.py"]
