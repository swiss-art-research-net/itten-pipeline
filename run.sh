#!/bin/bash

source .env

JOBSCONTAINER=$(echo $PROJECT_NAME)_jobs

bash downloadSources.sh
docker exec $JOBSCONTAINER task