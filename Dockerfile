FROM python:3.13-slim

WORKDIR /usr/src/app

RUN pip install -U pip setuptools

COPY pyproject.toml docker-run.sh .
COPY .env.prod .env
COPY freak freak

RUN pip install -e .

VOLUME ["/opt/live-app"]

EXPOSE 5000

CMD ["/usr/bin/bash", "docker-run.sh"]
