FROM python:3.12-alpine

WORKDIR /opt/app

ENV APP_ENV="container"

COPY . .

COPY scripts/launch.sh /opt/app/launch.sh
COPY sso/additional-info.json /opt/app/sso/additional-info.json
COPY sso/faculty-base-additional-info.json /opt/app/sso/faculty-base-additional-info.json
COPY sso/faculty_exchange_route.json /opt/app/sso/faculty_exchange_route.json

RUN apk add -u --no-cache tzdata gcc musl-dev libxml2 libxslt-dev
RUN pip install wheel
RUN pip install -r requirements.txt

ENV PORT=8006

ENTRYPOINT ["/bin/sh","launch.sh"]