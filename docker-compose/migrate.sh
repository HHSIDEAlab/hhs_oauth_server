#!/bin/sh

python manage.py migrate

python manage.py createsuperuser
python manage.py create_admin_groups
python manage.py loaddata scopes.json
python manage.py create_blue_button_scopes
python manage.py create_test_user_and_application
python manage.py create_user_identification_label_selection
python manage.py create_test_feature_switches
