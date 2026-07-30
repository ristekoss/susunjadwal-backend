FROM python:3.12-slim

WORKDIR /opt/app

ENV APP_ENV="container"

COPY . .

COPY scripts/launch.sh /opt/app/launch.sh
COPY sso/additional-info.json /opt/app/sso/additional-info.json
COPY sso/faculty-base-additional-info.json /opt/app/sso/faculty-base-additional-info.json
COPY sso/faculty_exchange_route.json /opt/app/sso/faculty_exchange_route.json

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	   ca-certificates \
	   tzdata \
	   gcc \
	   libxml2-dev \
	   libxslt-dev \
	   wget \
	   gnupg \
	   libnss3 \
	   libxss1 \
	   libasound2 \
	   libatk1.0-0 \
	   libcups2 \
	   libdrm2 \
	   libgbm1 \
	   libgtk-3-0 \
	   libxcomposite1 \
	   libxrandr2 \
	   libxdamage1 \
	   libx11-xcb1 \
	   libxkbcommon0 \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt
RUN pip install --no-cache-dir playwright
RUN python -m playwright install chromium --with-deps || true

ENV PORT=8006

ENTRYPOINT ["/bin/sh","launch.sh"]