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