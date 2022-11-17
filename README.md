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
docker compose up -d
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

```sh
docker compose exec jobs task
```

To limit the pipeline to a subset of records use the `--limit` parameter. To include only records that have a doi, use the `--onlyWithDoi` parameter. Both parameters can be combined.

```sh
docker compose exec jobs task -- --limit 20 --onlyWithDoi true
```

To list available tasks, run:

```sh
docker compose exec jobs task --list
```

This will output a list of tasks:
```
task: Available tasks for this project:
* cache-iiif-manifests:                 Cache the IIIF manifests linked in the OAI XML records
* default:                              Runs the entire pipeline
* generate-example-record:              Generates an example record for developing the mapping in the X3ML editor
* ingest-data-additional:               Ingest the TTL and Trig files located in the data/ttl/additional folder to the Blazegraph instance.
* ingest-data-from-folder:              Ingests data from a specified folder. If a named graph is specified (GRAPH), TTL files will be ingested into it. Otherwise, the filename will be used as named graph. Named Graphs specified in Trig files will be used as defined
* ingest-data-main:                     Ingest the TTL files located  in /data/ttl to the Blazegraph instance
* ingest-ontologies:                    Ingests the ontologies into individual named Graphs
* perform-mapping:                      Map the input XML data to CIDOC/RDF
* prepare-data-for-mapping:             Prepare the source and OAI data for mapping. To include only a subset of the data, use the `--limit` option. To include only records with DOIs, use the `--onlyWithDoi` option.
* retrieve-additional-data:             Retrieve additional reference data for the mapped data
* retrieve-data-from-e-manuscripta:     Retrieve the OAI records from from e-manuscripta
```

To run a specific task type `task` followed by the task name, e.g.:

```sh
docker compose exec jobs task prepare-data-for-mapping
```

If the task is already up to date, it will not run. To force a task to run, type the command followed by `--force`

```sh
docker compose exec jobs task prepare-data-for-mapping --force
```

To add additional arguments to the task itself, enter the arguments after a `--` sign, e.g.:

```sh
docker compose exec jobs task prepare-data-for-mapping -- --limit 100 --onlyWithDoi true
```
