FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim

COPY ./app /app
COPY ./requirements.txt /

# Upgrade
RUN apt-get update && apt-get -y upgrade && apt clean && pip3 install -r /requirements.txt

COPY ./start-reload.sh /start-reload.sh
RUN chmod +x /start-reload.sh

EXPOSE 80
