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

    def convertCmiJSONtoXML(record):

        def cleanTag(tag):
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
    for i, record in enumerate(records):
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
