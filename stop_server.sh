#!/bin/bash

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
    FHIR_CERTSTORE_ON_HOST
    do
        t=${!v}
        # trim off \r
        export ${v}="${t/$'\r'/}"
    done
}

# just satisfying compose so no env var warnings emitted
export_vars

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

export DB_MIGRATIONS=true 
export DJANGO_DEFAULT_SAMPLE_FHIR_ID="dummy"
export DJANGO_FHIR_CERTSTORE="dummy"

docker-compose down

if [ -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}" ]
then
    echo "cleanup client cert file."
    rm -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_CERT_FILE}"
fi

if [ -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}" ]
then
    echo "cleanup client key file."
    rm -f "${FHIR_CERTSTORE_ON_HOST}/${FHIR_KEY_FILE}"
fi

