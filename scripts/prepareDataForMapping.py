"""
This script prepares the data for mapping. 
It converts the source data to XML and adds the XML data retrieved from e-manuscripta via OAI.

Todo:
- Add curated and enriched data

Usage:

python prepareDataForMapping.py --sourceFolder=<sourceFolder> --oaiXMLFolder=<oaiXMLFolder> --outputFolder=<outputFolder>

Parameters:
    --sourceFolder       The folder containing the source JSON data
    --oaiXMLFolder       The folder containing the XML data retrieved from e-manuscripta
    --outputFolder       The folder to write the output XML files to
    --vlidMapFile        The path to the file containing the mapping between VLIDs and DOIs (optional)
"""

import sys
from dicttoxml import dicttoxml
from lxml import etree
from os.path import join, isfile
from tqdm import tqdm

from lib.utils import readRecords, RetrieveVLIDfromDOI

def prepareData(options):
    sourceFolder = options['sourceFolder']
    oaiXMLFolder = options['oaiXMLFolder']
    outputFolder = options['outputFolder']
    vlidMapFile = options['vlidMapFile']
    
    # Read records from input folder
    records = readRecords(sourceFolder)

    if 'onlyWithDoi' in options and options['onlyWithDoi'] == 'true':
        records = [d for d in records if 'doi' in d]

    if 'limit' in options:
        records = records[:options['limit']]

    # Retrieve OAI records for records that have VLIDs
    oaiXmlData = retrieveOaiXMLData(records=records, oaiXMLFolder=oaiXMLFolder, vlidMapFile=vlidMapFile)
    
    # Convert to XML
    recordsXML = convertRecordsToXML(records)

    # Add data from OAI XML files
    recordsXML = addOaiXMLData(recordsXML, oaiXmlData)

    # Write to files
    writeXMLRecordsToFiles(recordsXML, outputFolder)

def addOaiXMLData(records, oaiData):
    """
    Add the XML data retrieved from e-manuscripta via OAI to the records.
    All nodes are added to a new node called "oai". Some tags that are not
    used in the mapping are removed.

    :param records: list of CMI records
    :param oaiData: dictonary of XML data, where the key is the GUID of the record
    :return: list of CMI records with added XML data
    """

    def removeUnneededTags(node):
        pathsToRemove = [
            ".//{http://www.loc.gov/METS/}metsHdr",
            ".//{http://www.loc.gov/METS/}fileSec",
            ".//{http://www.loc.gov/METS/}structMap",
            ".//{http://www.loc.gov/METS/}structLink"
        ]
        nodesToRemove = [item for sublist in [node.findall(d) for d in pathsToRemove] for item in sublist]
        
        for unneeded in nodesToRemove:
            unneeded.getparent().remove(unneeded)
            
        return node

    for record in records:
        guid = record.find('guid').text
        if guid in oaiData:
            oaiNode = etree.SubElement(record, 'oai')
            oaiNode.append(removeUnneededTags(oaiData[guid]).getroot())
    return records

def convertRecordsToXML(records):
    """
    Convert CMI records to XML.

    :param records: list of CMI records
    :return: list of XML records
    """

    def convertCmiJSONtoXML(record):
        """
        Convert a CMI record to XML.
        """

        def cleanTag(tag):
            """
            Make sure that the tag is valid XML tag.
            Removes umlauts and replaces some special characters.

            Usage:
            >>> cleanTag("Kürzel")
            >>> kuerzel
            """
            cleanTag = replace_umlauts(tag.lower())
            cleanTag = cleanTag.replace(' ', '_')
            cleanTag = cleanTag.replace('/', '-')
            return cleanTag

        def replace_umlauts(text:str) -> str:
            """replace special German umlauts (vowel mutations) from text. 
            ä -> ae...
            ü -> ue 
            """
            vowel_char_map = {ord('ä'):'ae', ord('ü'):'ue', ord('ö'):'oe', ord('ß'):'ss'}
            return text.translate(vowel_char_map)

        def convertToSafeKeys(dictionary):
            """
            Convert keys in dictionary to keys that are valid XML tags.
            Nested dictionaries are converted recursively.
            """
            newDict = {}
            for key, value in dictionary.items():
                if isinstance(value, dict):
                    newDict[cleanTag(key)] = convertToSafeKeys(value)
                elif isinstance(value, list):
                    newDict[cleanTag(key)] = [convertToSafeKeys(v) for v in value]
                else:
                    newDict[cleanTag(key)] = value
            return newDict

        cleanedRecord = convertToSafeKeys(record)
        
        xml = dicttoxml(cleanedRecord, attr_type=False)
        return etree.fromstring(xml)
    
    xmlRecords = []
    for record in records:
        xmlRecords.append(convertCmiJSONtoXML(record))
    return xmlRecords

def retrieveOaiXMLData(*, records, oaiXMLFolder, vlidMapFile):
    """
    Retrieve the XML data from e-manuscripta via OAI.

    :param records: list of CMI records
    :param oaiXMLFolder: folder containing the XML data retrieved from e-manuscripta
    :param vlidMapFile: path to the file containing the mapping between VLIDs and DOIs
    :return: dictonary of XML data, where the key is the GUID of the record
    """
    oaiXmlData = {}

    # Retrieve VLIDs for records that have DOIs    
    vlidRetriever = RetrieveVLIDfromDOI(vlidMapFile=vlidMapFile)

    for record in tqdm([d for d in records if 'doi' in d]):
        vlid = vlidRetriever.getVlidForDoi(record['doi'])
        if vlid is not None:
            filename = join(oaiXMLFolder, vlid + ".xml")
            if isfile(filename):
                oaiXmlData[record['GUID']] = etree.parse(filename)
    
    return oaiXmlData

def writeXMLRecordsToFiles(records, outputFolder):
    """
    Write CMI records to XML files.

    :param records: list of CMI records
    :param outputFolder: folder to write the XML files to
    """
    for record in tqdm(records):
        filename = join(outputFolder, record.find('guid').text + ".xml")
        with open(filename, 'wb') as f:
            f.write(etree.tostring(record, pretty_print=True))

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
    
    if 'limit' in options:
        options['limit'] = int(options['limit'])

    prepareData(options)
