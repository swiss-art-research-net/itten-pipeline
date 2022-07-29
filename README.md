# JILA Pipeline

## About

This contains the pipeline for the Johannes Itten Linked Archive (JILA) project.

## How to use

Prerequisites: [Docker](http://docker.io) including Docker Compose

Copy and (if required) edit the .env.example
```
cp .env.example .env
```

Run the project with
```
docker-compose up -d
```

## Initialisation

To include the [JILA App](https://github.com/swiss-art-research-net/itten-app) when cloning, clone with:
```
git clone --recurse-submodules git@github.com:swiss-art-research-net/itten-pipeline.git
```

To download the source data create a [GitHub personal access token](https://github.com/settings/tokens) and add it to the `.env` file, along with your username.

Download the source files by runnning
```sh
bash downloadSources.sh
```

### Tasks

The pipeline can be controlled by the Task runner. To run the entire pipeline, run

`docker compose exec jobs task`

To list available tasks, run:

`dockec compose exec task --list`

This will output a list of tasks:
```
task: Available tasks for this project:
* default:                              Runs the entire pipeline
* prepare-data-for-mapping:             Prepare the source and OAI data for mapping. To include only a subset of the data, use the `--liimit` option. To include only records with DOIs, use the `--onlyWithDoi` option.
* retrieve-data-from-e-manuscripta:     Retrieve the OAI records from from e-manuscripta                                       
```

To run a specific task type `task` followed by the task name, e.g.:

`task prepare-data-for-mapping`

If the task is already up to date, it will not run. To force a task to run, type the command followed by `--force`

`task prepare-data-for-mapping --force`

To add additional arguments to the task itself, enter the arguments after a `--` sign, e.g.:

`task prepare-data-for-mapping -- --limit 100 --onlyWithDoi true`
