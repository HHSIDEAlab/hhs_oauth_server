#!/bin/bash

# This script starts the docker-compose web service
# and sets the SECRET/PRIVATE SALT and ITERATION and PASSWORD_HASH_ITERATIONS variable
# values from ansible vault files, the password for vault file is stored in a secured
# store e.g. keybase.
# You must be logged in to the secured store e.g. Keybase and have access to the password file.
#
# NOTE: this is so that the secrets are not left on the local file system or leave the secured store
# like keybase.
#
# e.g. your vault password file in keybase:
# VAULT_PASSFILE="/keybase/my_secured_folder/creds/vault_pw.txt"
# for fhir client cert and key files:
# for BFD local: the script will extract the cert and key from location indicated by BFD_CLIENT_TRUSTED_PFX
# usually in a BFD local repo;
# for BFD on remote env: the cert and key are usually stored in secured store e.g. keybase, you must logged in to
# the secured store and have access to the cert and key files indicated by SRC_CERT_FILE and SRC_KEY_FILE


function export_vars() {
    source .env
    for v in REMOTE_DEBUG \
    REMOTE_DEBUG_WAIT \
    SUPERUSER_NAME \
    SUPERUSER_PASSWORD \
    SUPERUSER_EMAIL \
    SAMPLE_FHIR_ID_LIST \
    SAMPLE_MBI_LIST \
    SAMPLE_HICN_LIST \
    USE_LOCAL_BFD \
    VAULT_PASSFILE \
    VAULT_FILE \
    FHIR_URL \
    HOSTNAME_URL \
    BFD_CLIENT_TRUSTED_PFX \
    SRC_CERT_FILE \
    SRC_KEY_FILE \
    SLSX_ENABLED \
    FHIR_CERTSTORE_ON_HOST
    do
        echo ${v} "=" ${!v}
        t=${!v}
        # trim off \r
        export ${v}="${t/$'\r'/}"
    done
}

function start_server_with_local_bfd() {
    echo "Start blue button server with local BFD as fhir server."
    if [ ! -z ${FHIR_CERT_FILE} ] && [ ! -z ${FHIR_KEY_FILE} ]
    then
        if [ ! -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}" ] || [ ! -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}" ]
        then
            echo "Extracting local BFD trusted client cert and private key files in .pem format."
            if [ ! -z ${BFD_CLIENT_TRUSTED_PFX} ] && [ -f ${BFD_CLIENT_TRUSTED_PFX} ]
            then
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
            openssl pkcs12 -in ${BFD_CLIENT_TRUSTED_PFX} -password pass:changeit -nocerts -out "${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}" -nodes
            openssl pkcs12 -in ${BFD_CLIENT_TRUSTED_PFX} -password pass:changeit -nokeys -out "${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}"
        fi

        if [ ! -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}" ] && [ ! -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}" ]
        then
            echo "local BFD trusted client cert ${FHIR_CERT_FILE} and/or private key $FHIR_KEY_FILE} not found."
            exit 127
        fi

        if [ "${DB_MIGRATIONS}" = true ]
        then
            docker-compose down
        else
            docker-compose stop web
        fi

        echo "Starting blue button server..., FHIR_URL: " ${FHIR_URL}
        docker-compose run --publish 8000:8000 -p 5678:5678 web bash -c "./docker-compose/bluebutton_server_start.sh"
    else
        echo "local BFD trusted client cert and private key files in .pem format is required but not found."
    fi
}

function start_server_with_remote_bfd() {
    echo "Start bluebutton server with remote BFD as fhir server."
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
        DJANGO_SLSX_CLIENT_ID=$(ansible-vault view --vault-password-file=${VAULT_PASSFILE} ${VAULT_FILE} | grep "^vault_env_slsx_client_id" | awk '{print $2}')
        DJANGO_SLSX_CLIENT_SECRET=$(ansible-vault view --vault-password-file=${VAULT_PASSFILE} ${VAULT_FILE} | grep "^vault_env_slsx_client_secret" | awk '{print $2}')

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

        if [ ! -z ${DJANGO_SLSX_CLIENT_ID} ]
        then
            export DJANGO_SLSX_CLIENT_ID=${DJANGO_SLSX_CLIENT_ID}
        fi

        if [ ! -z ${DJANGO_SLSX_CLIENT_SECRET} ]
        then
            export DJANGO_SLSX_CLIENT_SECRET=${DJANGO_SLSX_CLIENT_SECRET}
        fi

        if [ -f "${SRC_CERT_FILE}" ] && [ -f "${SRC_KEY_FILE}" ]
        then
            yes | cp -rf ${SRC_CERT_FILE} ${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}
            yes | cp -rf ${SRC_KEY_FILE} ${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}
        fi

        if [ ! -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}" ] && [ ! -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}" ]
        then
            echo "remote BFD trusted client cert ${FHIR_CERT_FILE} and/or private key $FHIR_KEY_FILE} not found."
            exit 127
        fi

        if [ "${DB_MIGRATIONS}" = true ]
        then
            docker-compose down
        else
            docker-compose stop web
        fi

        echo "SALT:" ${DJANGO_USER_ID_SALT} ", ITERATIONS:" ${DJANGO_USER_ID_ITERATIONS} ", PASSWORD_HASH_ITERATIONS:" ${DJANGO_PASSWORD_HASH_ITERATIONS} 
        echo "Starting blue button server, FHIR_URL: " ${FHIR_URL}
        docker-compose run --publish 8000:8000 -p 5678:5678 -e DJANGO_USER_ID_SALT=${DJANGO_USER_ID_SALT} -e DJANGO_USER_ID_ITERATIONS=${DJANGO_USER_ID_ITERATIONS} -e DJANGO_PASSWORD_HASH_ITERATIONS=${DJANGO_PASSWORD_HASH_ITERATIONS} web bash -c "./docker-compose/bluebutton_server_start.sh"
    else
        echo "Using remote BFD, but either VAULT_PASSFILE or VAULT_FILE are not properly set."
        exit 1
    fi
}

function usage() {
    echo "Start a bluebutton server by docker compose."
    echo "Usage: start_server.sh [-h|--help] [-r|--restart]"
    echo "                 Start server (perform django models migration)"
    echo "-h, --help       Display this usage"
    echo "-r, --restart    Restart server (do not perform django models migration, keep django models)"
}

# main logic

## uncomment to tracing and trouble shooting this script 
## set -x

if [ "$#" -gt 1 ]
then
    echo "Invalid command, too many arguments."
    usage
    exit 1
fi

export DB_MIGRATIONS=true

if [ "$#" -eq 1 ]
then
    if  [ $1 = "-h" ] || [ $1 = "--help" ]
    then
        usage
        exit 0
    fi
    if [ $1 = "-r" ] || [ $1 = "--restart" ]
    then
        echo "DB_MIGRATION=false"
        export DB_MIGRATIONS=false
    else
        echo "Invalid argument: $1"
        usage
        exit 1
    fi
fi

if [ ! -e ".env" ]
then
    echo ".env not found, start_server requires settings from .env, make a copy of .env.example: cp .env.example .env and change the values accordingly."
    exit 127
fi

export_vars

if [ ! -z ${SAMPLE_FHIR_ID_LIST} ] && [ ! -z ${SAMPLE_MBI_LIST} ] && [ ! -z ${SAMPLE_HICN_LIST} ]
then
    id_list=(${SAMPLE_FHIR_ID_LIST//,/ })
    mbi_list=(${SAMPLE_MBI_LIST//,/ })
    hicn_list=(${SAMPLE_HICN_LIST//,/ })
    id_list_len=${#id_list[@]}
    mbi_list_len=${#mbi_list[@]}
    hicn_list_len=${#hicn_list[@]}
    if [ "$id_list_len" -gt 0 ] && [ "$id_list_len" -eq "$mbi_list_len" ] && [ "$mbi_list_len" -eq "$hicn_list_len" ]
    then
        export DJANGO_DEFAULT_SAMPLE_FHIR_ID="${id_list[0]}"
        export DJANGO_DEFAULT_SAMPLE_MBI="${mbi_list[0]}"
        export DJANGO_DEFAULT_SAMPLE_HICN="${hicn_list[0]}"
    fi 
else
    if [ ! -z ${SAMPLE_FHIR_ID_LIST} ] || [ ! -z ${SAMPLE_MBI_LIST} ] || [ ! -z ${SAMPLE_HICN_LIST} ]
    then
        echo "Warning: Inconsistent detected among SAMPLE_FHIR_ID_LIST, SAMPLE_MBI_LIST, SAMPLE_HICN_LIST, samples ignored."
    fi
fi

if [ -z ${FHIR_CERT_FILE} ]
then
    export FHIR_CERT_FILE="ca.cert.pem"
fi

if [ -z ${FHIR_KEY_FILE} ]
then
    export FHIR_KEY_FILE="ca.key.nocrypt.pem"
fi

if [ -z ${FHIR_CERTSTORE_ON_HOST} ]
then
    export FHIR_CERTSTORE_ON_HOST="./docker-compose/certstore"
fi

if [ -z ${DJANGO_FHIR_CERTSTORE} ]
then
    export DJANGO_FHIR_CERTSTORE="/code/docker-compose/certstore"
fi

if [ "${USE_LOCAL_BFD}" = true ]
then
    start_server_with_local_bfd
else
    start_server_with_remote_bfd
fi
