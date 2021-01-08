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

export DB_MIGRATIONS=true 
export DJANGO_DEFAULT_SAMPLE_FHIR_ID="dummy"
export DJANGO_FHIR_CERTSTORE="dummy"

docker-compose down
