import sys
from dicttoxml import dicttoxml
from lxml import etree
from os.path import join, isfile
from tqdm import tqdm

from lib.utils import readRecords, RetrieveVLIDfromDOI

def performMerge(options):
    sourceFolder = options['sourceFolder']
    oaiXMLFolder = options['oaiXMLFolder']
    outputFolder = options['outputFolder']
    vlidMapFile = options['vlidMapFile']
    
    # Read records from input folder
    records = readRecords(sourceFolder)

    # Retrieve VLIDs for records that have DOIs    
    vlidRetriever = RetrieveVLIDfromDOI(vlidMapFile=vlidMapFile)
    for record in tqdm([d for d in records if 'doi' in d]):
        record['vlid'] = vlidRetriever.getVlidForDoi(record['doi'])

    for record in [d for d in records if 'doi' in d]: # for now just use the ones with a doi
        if record['vlid'] is not None:
            filename = join(oaiXMLFolder, record['vlid'] + ".xml")
            if isfile(filename):
                oaiData = etree.parse(filename)
        root = convertCmiJSONtoXML(record)
        outputFile = join(outputFolder, record['GUID'] + ".xml")
        with open(outputFile, 'wb') as f:
            f.write(root)


def convertCmiJSONtoXML(record):

    def cleanTag(tag):
        cleanTag = replace_umlauts(tag.lower())
        cleanTag = cleanTag.replace(' ', '_')
        return cleanTag

    def replace_umlauts(text:str) -> str:
        """replace special German umlauts (vowel mutations) from text. 
        ä -> ae...
        ü -> ue 
        """
        vowel_char_map = {ord('ä'):'ae', ord('ü'):'ue', ord('ö'):'oe', ord('ß'):'ss'}
        return text.translate(vowel_char_map)

    cleanedRecord = {}
    oldKeys = []

    for key in record.keys():
        oldKeys.append(key)
    for key in oldKeys:
        cleanedRecord[cleanTag(key)] = record[key]

    return dicttoxml(cleanedRecord, attr_type=False)


if __name__ == "__main__":
    options = {}

    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--"):
            if not sys.argv[i + 2].startswith("--"):
                options[arg[2:]] = sys.argv[i + 2]
            else:
                print("Malformed arguments")
                sys.exit(1)

    if not 'sourceFolder' in options:
        print("An input directory that contains the source JSON files must be specified via the --sourceFolder option")
        sys.exit(1)
    if not 'oaiXMLFolder' in options:
        print("An input directory that contains the OAI XML files must be specified via the --oaiXMLFolder option")
        sys.exit(1)

    if not 'outputFolder' in options:
        print("An output directory must be specified via the --outputFolder option")
        sys.exit(1)

    if not 'vlidMapFile' in options:
        options['vlidMapFile'] = join(options['sourceFolder'], 'map_doi_vlid.csv')
    
    performMerge(options)
