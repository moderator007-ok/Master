FROM python:3.10.8-slim-buster

# Update sources to use HTTPS and install apt-transport-https
RUN apt-get update -y --fix-missing \
    && apt-get install -y --no-install-recommends apt-transport-https \
    && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list \
    && apt-get update -y --fix-missing \
    && apt-get install -y --no-install-recommends debian-archive-keyring \
    && apt-get update -y --fix-missing \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc libffi-dev musl-dev ffmpeg aria2 python3-pip git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/
RUN pip3 install --no-cache-dir --upgrade --requirement requirements.txt
CMD gunicorn app:app & python3 main.py
