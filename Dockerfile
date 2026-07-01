FROM python:3.12-alpine AS builder

WORKDIR /opt/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        libxml2-dev \
        libxslt-dev

COPY requirements.txt .

RUN python -m pip install --upgrade pip wheel \
    && python -m pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-alpine AS runtime

WORKDIR /opt/app

ENV APP_ENV=container \
    PORT=8006 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache tzdata libxml2 libxslt

COPY --from=builder /install /usr/local

COPY scripts/launch.sh /opt/app/launch.sh
COPY app /opt/app/app
COPY models /opt/app/models
COPY scraper /opt/app/scraper
COPY uploader /opt/app/uploader
COPY widgets /opt/app/widgets
COPY sso /opt/app/sso
COPY cron.sh /opt/app/cron.sh

RUN chmod +x /opt/app/launch.sh

ENTRYPOINT ["/opt/app/launch.sh"]
