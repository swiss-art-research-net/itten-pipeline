#!/bin/bash
source .env
REPO=swiss-art-research-net/itten-data

download () {
  remotepath=$1
  localpath=$2

  echo -n "Downloading $remotepath: "
  python3 scripts/getFileContentsFromGit.py $GITHUB_USERNAME $GITHUB_PERSONAL_ACCESS_TOKEN $REPO $remotepath $localpath
}

download "source/Update20220615_ver01.json" "data/source/cmi-export.json"
download "data/csv/archivalienarten.csv" "data/source/alignment-archivalienarten.csv"