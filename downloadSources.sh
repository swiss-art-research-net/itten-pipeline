#!/bin/bash
source .env
REPO=swiss-art-research-net/itten-data

download () {
  remotepath=$1
  localpath=$2

  echo -n "Downloading $remotepath: "
  python3 scripts/getFileContentsFromGit.py $GITHUB_USERNAME $GITHUB_PERSONAL_ACCESS_TOKEN $REPO $remotepath $localpath
}

download "source/source.json" "data/source/cmi-export.json"
download "data/csv/archivalienarten.csv" "data/source/alignment-archivalienarten.csv"
download "data/csv/register_id.csv" "data/source/alignment-register_id.csv"
download "data/csv/sprachen.csv" "data/source/alignment-sprachen.csv"
download "data/csv/verzeichnungsstufe.csv" "data/source/alignment-verzeichnungsstufe.csv"