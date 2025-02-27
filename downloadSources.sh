#!/bin/bash
source .env

download () {
  repo=$1
  remotepath=$2
  localpath=$3

  echo -n "Downloading $remotepath: "
  python3 scripts/getFileContentsFromGit.py $GITHUB_USERNAME $GITHUB_PERSONAL_ACCESS_TOKEN $repo $remotepath $localpath
}

download "swiss-art-research-net/itten-data" "source/source.json" "data/source/cmi-export.json"
download "swiss-art-research-net/itten-data" "data/csv/archivalienarten.csv" "data/source/alignment-archivalienarten.csv"
download "swiss-art-research-net/itten-data" "data/csv/register_id.csv" "data/source/alignment-register_id.csv"
download "swiss-art-research-net/itten-data" "data/csv/sprachen.csv" "data/source/alignment-sprachen.csv"
download "swiss-art-research-net/itten-data" "data/csv/verzeichnungsstufe.csv" "data/source/alignment-verzeichnungsstufe.csv"
download "swiss-art-research-net/itten-data" "data/rdf/conceptLabels.trig" "data/ttl/additional/conceptLabels.trig"
download "swiss-art-research-net/itten-data" "data/rdf/networkLabels.trig" "data/ttl/additional/networkLabels.trig"
download "swiss-art-research-net/itten-data" "data/rdf/deducedGenders.trig" "data/ttl/additional/deducedGenders.trig"
download "swiss-art-research-net/itten-data" "external/gnd/agrelon_20191015.ttl" "data/ttl/additional/agrelon.ttl"

download "swiss-art-research-net/itten-data" "external/sikart/sikart.ttl" "data/ttl/additional/sikart.ttl"
download "swiss-art-research-net/itten-data" "external/heidelberg/wvitten03.nq" "data/external/heidelberg.nq"