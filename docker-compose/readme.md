# Local Docker Development

To begin developing locally, internal software engineers will need to obtain and copy the `bb2-local-client` certificate files in to the `docker-compose/certstore` location to support the connection to the BFD FHIR server (this can be automated by start server script, read on).

Before launch the server, set up environment by create a .env from template .env.example:

```
cp .env.example .env

```
then customize .env properly per your local development environment.

To startup the Docker containerized BB2 server, run the following command: 

```
start_server.sh           Start the server and perform DB migration
```
or

```
start_server.sh -r        Restart the server without performing DB migration (keep DB images)

```

Note that start_server.sh executes docker-compose run after setting up required environment variables per 
settings in .env; the server is run in foreground and loggings are displayed in current stdout, press Ctrl C
to stop the server, or alternatively, run command below:

```
stop_server.sh

```

Note that stop_server.sh executes docker-compose down to stop and remove the containerized services

## Secured blue button server secrets handling:

Blue Button server configuration values: DJANGO_USER_ID_SALT, DJANGO_USER_ID_ITERATIONS, PASSWORD_HASH_ITERATIONS
are server secrets and stored in password encrypted vault file, the password is kept in a password file
stored in a secured store (e.g. keybase), the following variables in .env need to be set properly to make
the secrets available to server start process and leave no trace of the secret values outside the secured store and vault file.
 
When the fhir server is a local bfd, the salt, iterations etc. use default values in blue button server settings,
the client cert and key files, if not already available at blue button server certstore, are extracted from bfd 
local git repo to blue button server certstore automatically.

```
USE_LOCAL_BFD=true
FHIR_URL="url to local bfd, e.g. https://192.168.0.109:1337/v1/fhir/"
BFD_CLIENT_TRUSTED_PFX="path to client-trusted-keystore.pfx in bfd local git repo"

```

When the fhir server is a remote bfd, the salt, iterations etc. are extracted from the vault file, and the password
is stored in a secured store (e.g. keybase), the client cert and key files are stored in secured store, and indicated by
SRC_CERT_FILE, SRC_KEY_FILE, and are copied to blue button server certstore automatically if they are not there already.

```
USE_LOCAL_BFD=false
FHIR_URL="url to remote bfd e.g. https://prod-sbx.bfd.cms.gov/v1/fhir/"
VAULT_PASSFILE="path-to-vault-password-file" (usually in secured store)
VAULT_FILE="path-to-vault-file" (in bluebutton-web-deployment local git repo)
SRC_CERT_FILE="/cygdrive/k/my_secured_store/fhir_client/client_data_server_bluebutton_local_certificate.pem" (usually in secured store)
SRC_KEY_FILE="/cygdrive/k/my_secured_store/fhir_client/client_data_server_bluebutton_local_private_key.pem" (usually in secured store)

```

Blue Button server url is indicated as HOSTNAME_URL needs to be set with local host IP,
as shown in sample below, this is required to make service in container work properly:

```
HOSTNAME_URL="http://192.168.0.109:8000"

```

## Blue Button DB image migrations

DB image migrations is done in docker container before blue button server is started.
this is done during execution of start_server.sh.

the migration creates a super user with below attributes, can be customized in .env:

```
SUPERUSER_NAME=root
SUPERUSER_PASSWORD=blue123
SUPERUSER_EMAIL=bluebutton@example.com
```

if chose to start server without db image migrations, use command below:

```
start_server.sh -r (or --restart)
```

If you're working with a fresh db image
the migrations have to be run.

so either run start_server.sh as below:

```
start_server.sh

```

or perform the migration separately:

```
docker-compose exec web docker-compose/migrate.sh

```

If any permissions errors are thrown try the following command,
then run the migrate script again:
```
docker-compose exec web chmod +x docker-compose/migrate.sh
```
## Populate BB2 Django models with large number of records

Run migrate.sh will in turn execute a django command among other things:

python manage.py create_test_user_and_application

this will populate BB2 Django models User, UserProfile, Application, Crosswalk, AccessToken with:

one user 'fred', one app 'TestApp', one access token, and one corresponding crosswalk entry, which can be used for minimum test, for local tests that require large number of users, applications, etc. there
is a command to help with that:

python manage.py create_test_users_and_applications_batch

which generates 50 dev users, each has 1-5 apps, and 30k bene users which have following relations:

1. dev users and apps created date are spread over past 700 days randomly
2. each bene sign up (grant access) with 1-3 apps by aproximately: 70% 1 app, 25% 2 apps, 5% 3 apps and
3. among these sign up (access token grants): 80% with demographic scopes, 20% deny demo access
4. benes sign up dates are randomized and set to a date approximately 10 days after apps created date
5. apps' client type, grant type, opt in/out of demographic info access are also randomly generated per a percent distribution

the data generation command assumes that the 30k synthetic beneficiary records in rif files are present
under BB2 local repo base directory:

<bb2_local_repo_base>/synthetic-data/

for detailed info about the synthetic data and how to fetch them, refer to: https://github.com/CMSgov/beneficiary-fhir-data/blob/master/apps/bfd-model/bfd-model-rif-samples/dev/design-sample-data-sets.md


## Running tests from your host

To run the Django unit tests, run the following command:

```
docker-compose exec web python runtests.py
```

You can run individual applications tests or tests with in a specific area as well.

The following are a few examples (drilling down to a single test):
```bash
docker-compose exec web python runtests.py apps.dot_ext.tests
```
```bash
docker-compose exec web python runtests.py apps.dot_ext.tests.test_templates
```
```bash
docker-compose exec web python runtests.py apps.dot_ext.tests.test_templates.TestDOTTemplates.test_application_list_template_override
```
Multiple arguments can be provided too:
```bash
docker-compose exec web python runtests.py apps.dot_ext.tests apps.accounts.tests.test_login
```

# Work on Windows

This requires the use of a linux sub system. This includes a choice of Cygwin, WSL, or VirtualBox + Linux.
Install the Docker Desktop on your Windows host, and set the DOCKER_HOST environment 
variable in linux sub system. Also enable the git configuration for proper EOL CRLF/LF 
convertion using the following command: 

```
git config --global core.autocrlf true

```
in case, with above git core.autocrlf setting, some steps e.g. migrate.sh still chokes (file not found etc.),
fix script manually, e.g. using dos2unix.

If needing to pass the docker compose environment variable, make a copy of the .env.example and
change it accordingly.

### In the .env file add the below hint to properly handle path:

```
COMPOSE_CONVERT_WINDOWS_PATHS=1
```

## Remote debugging BB2 server

Add the line below to the .env file to enable remote PTVSD debugging
of BB2 server in a docker container:

```
REMOTE_DEBUG=true
```

After BB2 server is up, ptvsd is listening on port 5678.
Afterward, attach to it from your IDE (e.g. VSCode) and put break 
points on the execution path. You can now start debugging.

Add the line below to the .env file to make ptvsd agent wait on attaching, before execute
bluebutton server, this is needed when debugging logic during bluebutton server bootstrap.

```
REMOTE_DEBUG_WAIT=true
```

## Remote debugging Blue Button unit tests

Run the docker-compose command below to start the unittests with PTVSD and for it to wait on port 6789 for the debugger to attach.
Attach to the unittests from an IDE (e.g. VSCode), then put break points in the test cases and debugging.

```
docker-compose up -d unittests

```

## Test and Verify Using Sample Clients

After the container is up, go to http://localhost:8000 (default) address location, and you will see the CMS Blue Button landing page,
Follow the documentation to create accounts, register applications, and other tasks in the local development environment. Note that some features, like email, work differently when running locally.  For example, a text version of an email is sent in to the main server log and is where you will find your signup confirmation activation link. 

You are also able to manually modify Django model objects when needed by using the Django ADMIN at: http://localhost:8000/admin.

To test if there is connectivity to the back end BFD FHIR server, go to the following URL at: http://localhost:8000/health/external.

###Test from clients:


* You can test from in the browser on the homepage using the testclient. This is located from the top of the page by clicking the link `testclient`
* You can test using one of our sample clients applications. See the related blog posts for more information: 
  * [Sample Client Applications](https://bluebutton.cms.gov/blog/Sample-Applications.html) 
  * [More Sample Client Applications](https://bluebutton.cms.gov/blog/More-Sample-Applications.html)
  * [Install a Django Client](https://bluebutton.cms.gov/blog/Installing-a-Django-client-application.html)

Make changes to configurations by following the sample clients instructions and test the end to end scenarios.

## Test with Sample Beneficiary

The following can be used to test FHIR resource calls using CURL commands. These use the sample beneficiary user `fred` that is setup when running the `migration.sh` script in the initial setup.

```
export ACCESS_TOKEN="sample-token-string"
export BENE_ID="-20140000008325"
export HOST="http://localhost:8000"

```

Get Pateint FHIR Resource json


```
curl --header "Authorization: Bearer ${ACCESS_TOKEN}"  "${HOST}/v1/fhir/Patient/${BENE_ID}"

```

Get ExplanationOfBenefit FHIR Resource json

```
curl -k -v --header "Authorization: Bearer ${ACCESS_TOKEN}"  "${HOST}/v1/fhir/ExplanationOfBenefit/?Patient=${BENE_ID}"

```
