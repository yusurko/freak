#!/usr/bin/bash

start-app() {
    [[ ! -d /opt/live-app ]] && exit 1
    cd /usr/src/app
    cp -rv /opt/live-app/{freak,pyproject.toml,.env,docker-run.sh} ./
    pip install -e .
    flask --app freak run --host=0.0.0.0 
}

[[ "$1" = "" ]] && start-app

