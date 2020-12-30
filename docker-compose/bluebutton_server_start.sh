#!/bin/sh

echo "DB_MIGRATIONS = " ${DB_MIGRATIONS}
echo "SUPERUSER_NAME = " ${SUPERUSER_NAME}
echo "SUPERUSER_EMAIL = " ${SUPERUSER_EMAIL}
echo "SUPERUSER_PASSWORD = " ${SUPERUSER_PASSWORD}
echo "REMOTE_DEBUG = " ${REMOTE_DEBUG}
echo "REMOTE_DEBUG_WAIT = " ${REMOTE_DEBUG_WAIT}
echo "DJANGO_USER_ID_SALT = " ${DJANGO_USER_ID_SALT}
echo "DJANGO_USER_ID_ITERATIONS = " ${DJANGO_USER_ID_ITERATIONS}
echo "DJANGO_PASSWORD_HASH_ITERATIONS = " ${DJANGO_PASSWORD_HASH_ITERATIONS}
echo "HOSTNAME_URL = " ${HOSTNAME_URL}
echo "FHIR_URL = " ${FHIR_URL}

if [ -f ./migration.completed ]
then
    echo "DB image migrations seems performed in container, skip..."
else
    if [ "${DB_MIGRATIONS}" = true ]
    then
        echo "DB_MIGRATIONS is true, run db image migration and models initialization."
        python manage.py migrate

        echo "from django.contrib.auth.models import User; User.objects.create_superuser('${SUPERUSER_NAME}', '${SUPERUSER_EMAIL}', '${SUPERUSER_PASSWORD}')" | python manage.py shell
        python manage.py create_admin_groups
        python manage.py loaddata scopes.json
        python manage.py create_blue_button_scopes
        python manage.py create_test_user_and_application
        python manage.py create_user_identification_label_selection
        python manage.py create_test_feature_switches
        # this is to prevent restart doing migration again
        touch migration.completed
    else
        echo "DB_MIGRATIONS is false, no db image migration and models initialization will run here, you might need to manually run DB image migrations ..."
    fi
fi


if [ ! -d 'bluebutton-css' ]
then
    git clone https://github.com/CMSgov/bluebutton-css.git
else
    echo 'CSS already installed.'
fi

if [ "${REMOTE_DEBUG}" = true ]
then
    if [ "${REMOTE_DEBUG_WAIT}" = true ]
    then
        echo "Start bluebutton server with remote debugging and wait attach..."
        python3 -m ptvsd --host 0.0.0.0 --port 5678 --wait manage.py runserver 0.0.0.0:8000 --noreload
    else
        echo "Start bluebutton server with remote debugging..."
        python3 -m ptvsd --host 0.0.0.0 --port 5678 manage.py runserver 0.0.0.0:8000 --noreload
    fi
else
    echo "Start bluebutton server ..."
    python3 manage.py runserver 0.0.0.0:8000
fi
