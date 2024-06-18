FROM python:3.6-alpine

WORKDIR /opt/app

ENV APP_ENV="container"

COPY . .

COPY launch.sh /opt/app/launch.sh
COPY sso/additional-info.json /opt/app/sso/additional-info.json
COPY sso/faculty-base-additional-info.json /opt/app/sso/faculty-base-additional-info.json
COPY sso/faculty_exchange_route.json /opt/app/sso/faculty_exchange_route.json

RUN apk add -u --no-cache tzdata gcc musl-dev libxml2 libxslt-dev && \
    pip install wheel && \
    pip install -r requirements.txt

ENV PORT=8006

ENTRYPOINT ["/opt/app","launch.sh"]