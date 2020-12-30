#!/bin/bash

# 
# This script starts the docker-compose web service
# and sets the SECRET/PRIVATE SALT and ITERATION and PASSWORD_HASH_ITERATIONS variable
# values from ansible vault files.
# You must be logged in to Keybase and have the BB2 team file system present.
# NOTE: Doing this so that these secrets are not left on the local file system.
# e.g. your vault password file in keybase:
# VAULT_PASSFILE="/keybase/team/bb20/infrastructure/creds/vault_pw.txt"
# TODO: copy cert/private key pem files from keybase to ./docker-compose/certstore
# the backend netloc: 
# local backend: localhost:1337
# sandbox backend: prod-sbx.bfd.cms.gov
#

if [ ! -e ".env" ]
then
    echo ".env not found, start_server requires settings from .env"
    exit 127
fi

source .env

for v in REMOTE_DEBUG \
REMOTE_DEBUG_WAIT \
SUPERUSER_NAME \
SUPERUSER_PASSWORD \
SUPERUSER_EMAIL \
DB_MIGRATIONS \
REQUIRE_VAULT_ACCESS \
VAULT_PASSFILE \
VAULT_FILE \
FHIR_URL \
HOSTNAME_URL \
BFD_CLIENT_TRUSTED_PFX \
CLIENT_CERT_FILE \
CLIENT_PRIVATE_KEY_FILE
do
    echo ${v} "=" ${!v}
    t=${!v}
    export ${v}="${t/$'\r'/}"
done

if [ "${REQUIRE_VAULT_ACCESS}" = true ]
then
    echo "Check ansible-vault command available."
    if ! command -v ansible-vault &> /dev/null
    then
        echo "ansible-vault could not be found, it is required to access ansible vault file."
        exit 127
    fi
    if [ ! -z ${VAULT_PASSFILE} ] && [ ! -z ${VAULT_FILE} ] && \
    [ -f ${VAULT_PASSFILE} ] && [ -f ${VAULT_FILE} ]
    then
        DJANGO_USER_ID_SALT=$(ansible-vault view --vault-password-file=${VAULT_PASSFILE} ${VAULT_FILE} | grep "^vault_env_django_user_id_salt" | awk '{print $2}')
        DJANGO_USER_ID_ITERATIONS=$(ansible-vault view --vault-password-file=${VAULT_PASSFILE} ${VAULT_FILE} | grep "^vault_env_django_user_id_iterations" | awk '{print $2}')
        DJANGO_PASSWORD_HASH_ITERATIONS=$(ansible-vault view --vault-password-file=${VAULT_PASSFILE} ${VAULT_FILE} | grep "^vault_env_django_password_hash_iterations" | awk '{print $2}')
        if [ ! -z ${DJANGO_USER_ID_SALT} ]
        then
            export DJANGO_USER_ID_SALT=${DJANGO_USER_ID_SALT}
        fi
        if [ ! -z ${DJANGO_USER_ID_ITERATIONS} ]
        then
            export DJANGO_USER_ID_ITERATIONS=${DJANGO_USER_ID_ITERATIONS}
        fi
        if [ ! -z ${DJANGO_PASSWORD_HASH_ITERATIONS} ]
        then
            export DJANGO_PASSWORD_HASH_ITERATIONS=${DJANGO_PASSWORD_HASH_ITERATIONS}
        fi
        docker-compose stop web
        echo "SALT:" ${DJANGO_USER_ID_SALT} ", ITERATIONS:" ${DJANGO_USER_ID_ITERATIONS} ", PASSWORD_HASH_ITERATIONS:" ${DJANGO_PASSWORD_HASH_ITERATIONS} 
        echo "Starting blue button server..., FHIR_URL: " ${FHIR_URL}
        docker-compose run --publish 8000:8000 -p 5678:5678 -e DJANGO_USER_ID_SALT=${DJANGO_USER_ID_SALT} -e DJANGO_USER_ID_ITERATIONS=${DJANGO_USER_ID_ITERATIONS} -e DJANGO_PASSWORD_HASH_ITERATIONS=${DJANGO_PASSWORD_HASH_ITERATIONS} web bash -c "./docker-compose/bluebutton_server_start.sh"
    else
        echo "REQUIRE_VAULT_ACCESS is true, but either VAULT_PASSFILE or VAULT_FILE not properly set."
        exit 1
    fi
else
    echo "REQUIRE_VAULT_ACCESS is false, start bluebutton server with local BFD."
    echo "Check local BFD trusted client cert and private key files."
    if [ ! -z ${CLIENT_CERT_FILE} ] && [ ! -z ${CLIENT_PRIVATE_KEY_FILE} ]
    then
        if [ -f ${CLIENT_CERT_FILE} ] && [ -f ${CLIENT_PRIVATE_KEY_FILE} ]
        then
            echo "local BFD trusted client cert and private key files set and exist."
        else
            echo "Get local BFD trusted client cert and private key files in .pem format."
            if [ ! -z ${BFD_CLIENT_TRUSTED_PFX} ] && [ -f ${BFD_CLIENT_TRUSTED_PFX} ]
            then
                echo "Check openssl command available."
                if ! command -v openssl &> /dev/null
                then
                    echo "openssl command not found, it is needed to extract local BFD trusted client cert and key files in .pem format"
                    echo " from client-trusted-keystore.pfx in local bfd repo, please install openssl or manually obtain them and put under"
                    echo " bluebutton server certstore (default location: ./docker-compose/certstore/), for details check: ./docker-compose/certstore/README.md"
                    exit 127
                fi
            else
                echo "BFD_CLIENT_TRUSTED_PFX not set or the file not found, it is required to extract client trusted pfx."
                exit 127
            fi
            openssl pkcs12 -in ${BFD_CLIENT_TRUSTED_PFX} -password pass:changeit -nocerts -out ./docker-compose/certstore/ca.key.nocrypt.pem -nodes
            openssl pkcs12 -in ${BFD_CLIENT_TRUSTED_PFX} -password pass:changeit -nokeys -out ./docker-compose/certstore/ca.cert.pem  
        fi
        if [ ! -f ${CLIENT_CERT_FILE} ] && [ ! -f ${CLIENT_PRIVATE_KEY_FILE} ]
        then
            echo "local BFD trusted client cert ${CLIENT_CERT_FILE} and/or private key $CLIENT_PRIVATE_KEY_FILE} not found."
            exit 127
        fi
        echo "Starting blue button server..., FHIR_URL: " ${FHIR_URL}
        docker-compose run --publish 8000:8000 -p 5678:5678 web bash -c "./docker-compose/bluebutton_server_start.sh"
    else
        echo "local BFD trusted client cert and private key files in .pem format is required but not found."
    fi
fi

