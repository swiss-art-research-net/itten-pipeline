
import csv
import json
import re
import requests
import sys
from bs4 import BeautifulSoup
from dicttoxml import dicttoxml
from lxml import etree
from sickle import Sickle
from tqdm import tqdm
from os import listdir
from os.path import join, isfile

from lib.utils import RetrieveVLIDfromDOI

def performRetrieval(options):
    inputFolder = options['inputFolder']
    outputFolder = options['outputFolder']
    vlidMapFile = options['vlidMapFile']
    oaiEndpoint = options['oaiEndpoint']

    # Read records from input folder
    records = readRecords(inputFolder)
    
    # Filter records that have links to e-manuscripta
    recordsToProcess = [d for d in records if 'doi' in d]
    print("Found %d records, of which %d have DOIs" % (len(records), len(recordsToProcess)))

    # Retrieve VLIDs for records that have DOIs    
    vlidRetriever = RetrieveVLIDfromDOI(vlidMapFile=vlidMapFile)
    for record in tqdm(recordsToProcess):
        record['vlid'] = vlidRetriever.getVlidForDoi(record['doi'])

    # Write VLID map to file
    vlidRetriever.writeVlidMap()

    # Retrieve OAI records for records that have VLIDs
    sickle = Sickle(oaiEndpoint)
    oaiRecords = {}
    ids = [d['vlid'] for d in recordsToProcess if d['vlid'] is not None]
    for identifier in tqdm(ids):
        if not isfile(join(outputFolder, identifier + ".xml")):
            oaiRecords[identifier] = (sickle.GetRecord(identifier=identifier, metadataPrefix='mets'))

    # Write OAI records with CMI data and write to XML to file
    for identifier in oaiRecords.keys():
        root = etree.fromstring(oaiRecords[identifier].raw.encode('utf8'))
        with open(join(outputFolder, identifier + ".xml"), 'wb') as f:
            f.write(etree.tostring(root, pretty_print=True))


def readRecords(directory):
    inputFiles = [join(directory, d) for d in listdir(directory) if d.endswith('.json')]
    records = []
    for file in inputFiles:
        with open(file, 'r') as f:
            text = f.read()
            decodedData = text.encode().decode('utf-8-sig') 
            try:
                data = json.loads(decodedData, strict=False)
                records += data
            except Exception as e:
                print(file, e)
    for record in records:
        if record['Link zu Digitalisat']:
            link = BeautifulSoup(record['Link zu Digitalisat'], 'html.parser')
            record['doi'] = link.find('a').text
            
    # Return only unique records based on GUID
    records = list({v['GUID']:v for v in records}.values())
            
    return records

if __name__ == "__main__":
    options = {}

    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--"):
            if not sys.argv[i + 2].startswith("--"):
                options[arg[2:]] = sys.argv[i + 2]
            else:
                print("Malformed arguments")
                sys.exit(1)

    if not 'inputFolder' in options:
        print("An input directory must be specified via the --inputFolder option")
        sys.exit(1)
    if not 'outputFolder' in options:
        print("An output directory must be specified via the --outputFolder option")
        sys.exit(1)

    if not 'vlidMapFile' in options:
        options['vlidMapFile'] = join(options['inputFolder'], 'map_doi_vlid.csv')
    if not 'oaiEndpoint' in options:
        options['oaiEndpoint'] = 'https://www.e-manuscripta.ch/zuzcmi/oai'

    performRetrieval(options)
