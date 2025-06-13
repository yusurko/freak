#!/usr/bin/bash

start-app() {
    [[ ! -d /opt/live-app ]] && exit 1
    cd /usr/src/app
    cp -rv /opt/live-app/{freak,pyproject.toml,docker-run.sh} ./
    cp -v /opt/live-app/.env.prod .env
    pip install -e .
    flask --app freak run --host=0.0.0.0 
}

[[ "$1" = "" ]] && start-app

