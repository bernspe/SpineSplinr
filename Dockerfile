#FROM python:3.7.6
FROM python:3.8
ENV PYTHONUNBUFFERED 1
RUN apt-get update && apt-get install -y libpq-dev gcc python-dev musl-dev daphne

RUN mkdir /code
WORKDIR /code
ADD requirements.txt /code/
RUN pip install -r requirements.txt

