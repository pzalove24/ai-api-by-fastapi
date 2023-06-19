FROM python:3.8-alpine

COPY .env /app/.env
COPY ./app /app/app
COPY ./requirements.txt /app/requirements.txt
COPY ./entrypoint.sh /app/entrypoint.sh
COPY ./pipelines /app/pipelines/

WORKDIR /app

RUN chmod +x entrypoint.sh

# for cassandra-driver
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    python3-dev \
    python3-setuptools \
    git \
    git-crypt \
    unzip \
    chromium-driver \
    gcc \
    make

RUN python -m pip install cassandra-driver

RUN apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

###

RUN python3 -m venv /opt/venv && /opt/venv/bin/python -m pip install -r requirements.txt

RUN /opt/venv/bin/python -m pypyr /app/pipelines/ai-model-download
RUN /opt/venv/bin/python -m pypyr /app/pipelines/decrypt

CMD ["./entrypoint.sh"]