#!/bin/bash

export DJANGO_USER_ID_SALT="dummy"
export DJANGO_USER_ID_ITERATIONS="dummy"
export DJANGO_PASSWORD_HASH_ITERATIONS="dummy"

docker-compose down
