"""
This script prepares the data for mapping. 
It converts the source data to XML and adds the XML data retrieved from e-manuscripta via OAI.

Todo:
- Add curated and enriched data

Usage:

python prepareDataForMapping.py --sourceFolder=<sourceFolder> --oaiXMLFolder=<oaiXMLFolder> --outputFolder=<outputFolder>

Parameters:
    --sourceFolder        The folder containing the source JSON data
    --oaiXMLFolder        The folder containing the XML data retrieved from e-manuscripta
    --outputFolder        The folder to write the output XML files to
    --alignmentDataPrefix The prefix of the alignment data files. Defaults to "alignment-" (optional)
    --vlidMapFile         The path to the file containing the mapping between VLIDs and DOIs (optional)
    --onlyWithDoi         If set to true, only records that contain a DOI are output (optional)
"""

import csv
import json
import sys
import unicodedata
import urllib
from dicttoxml import dicttoxml
from lxml import etree
from os.path import join, isfile
from tqdm import tqdm

from lib.utils import readRecords, RetrieveVLIDfromDOI

def prepareData(options):
    sourceFolder = options['sourceFolder']
    oaiXMLFolder = options['oaiXMLFolder']
    manifestsFolder = options['manifestsFolder']
    outputFolder = options['outputFolder']
    alignmentDataPrefix = options['alignmentDataPrefix']
    vlidMapFile = options['vlidMapFile']
    
    # Read records from input folder
    records = readRecords(sourceFolder)

    if options['onlyWithDoi']:
        records = [d for d in records if 'doi' in d]

    if 'limit' in options:
        records = records[:options['limit']]

    # Retrieve OAI records for records that have VLIDs
    oaiXmlData = retrieveOaiXMLData(records=records, oaiXMLFolder=oaiXMLFolder, vlidMapFile=vlidMapFile)

    # Add alignment data
    records = addAlignmentData(records, sourceFolder=sourceFolder, alignmentDataPrefix=alignmentDataPrefix)
    
    # Convert to XML
    recordsXML = convertRecordsToXML(records)

    # Add data from OAI XML files
    recordsXML = addOaiXMLData(recordsXML, oaiXmlData)

    # Add IIIF image data
    recordsXML = addImageDataFromManifests(recordsXML, manifestsFolder)

    # Write to files
    writeXMLRecordsToFiles(recordsXML, outputFolder)

def addAlignmentData(records, *, sourceFolder, alignmentDataPrefix):
    """
    Adds the data from alignment files to the records.
    The alignment files are expected to be in the source folder and identiferd by the alignmentDataPrefix.

    :param records: list of CMI records in JSON format
    :param sourceFolder: folder containing the alignment files
    :param alignmentDataPrefix: prefix of the alignment files
    """
    
    def customHash(l):
        def NFD(s):
            return unicodedata.normalize('NFD', s)

        return hash(NFD(json.dumps(l, ensure_ascii=False)))

    def getValueByPath(node, path):
        """
        Get the value of a node by a path given as a list of strings.

        Usage:
        >>> record = {"id": 1, "classification" : {"types": ["a", "b"]}}
        >>> getValueByPath(record, ["classification", "types"])
        ["a", "b"]
        """
        if len(path) == 1:
            return node
        return getValueByPath(record[path[0]], path[1:])

    def readAlignmentFiles(fieldsToAlign, sourceFolder, alignmentDataPrefix):
        """
        Reads the alignment files and returns a dictionary of the values, including a hash for looking up by the value

        :param fieldsToAlign: list of fields to align specified as a dict with keys as identifier and the path to the value
        :param sourceFolder: folder containing the alignment files
        :param alignmentDataPrefix: prefix of the alignment files
        :return: dictionary of the values, including a hash for looking up by the value
        """
        alignmentData = {}
        for key, path in fieldsToAlign.items():
            filename = join(sourceFolder, alignmentDataPrefix + key + ".csv")
            try:
                content = []
                with open(filename, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        content.append(row)
                
                lookup = {}
                for i, row in enumerate(content):
                    lookupHash = customHash(row['value'])
                    lookup[lookupHash] = i
                alignmentData[key] = {
                    "path": path,
                    "lookup": lookup,
                    "content": content
                }
            except:
                print("Could not read alignment file: " + filename)
                sys.exit(1)
        return alignmentData
    
    def setValueByPathAndKey(record, path, key, value, index=False):
        """
        Mutates the original record. A bit hacky and only supports up to 3 levels of nesting.

        :param record: the record to mutate
        :param path: the path to the node to mutate provided as a list of strings, e.g. ['Archivalienarten', 'Bezeichnung']
        """
        if len(path) == 1:
            if (isinstance(record[path[0]], list)):
                record[index] = value
            else:
                record[path[0]] = value
        if len(path) == 2:
            if isinstance(record[path[0]], list):
                record[path[0]][index] = value
            else:
                record[path[0]][path[1]] = value
        if len(path) == 3:
            if isinstance(record[path[0]], list):
                record[path[0]][index][path[1]] = value
            else:
                record[path[0]][path[1]][path[2]] = value
       
    fieldsToAlign = {
        "archivalienarten": ["Archivalienarten", "Bezeichnung"]
    }

    alignmentData = readAlignmentFiles(fieldsToAlign, sourceFolder=sourceFolder, alignmentDataPrefix=alignmentDataPrefix)
    
    for field, data in alignmentData.items():
        for record in records:
            # Get record value by path
            values = getValueByPath(record, data['path'])
            key = data['path'][-1]
            if isinstance(values, list):
                for index, value in enumerate(values):
                    if key in value:
                        try:
                            alignmentValues = data['content'][data['lookup'][customHash(value[key])]]
                        except:
                            print("Could not find alignment value for: " + str(value))
                            sys.exit(1)
                        for alignmentKey, alignmentValue in alignmentValues.items():
                            if alignmentKey not in ['key', 'path', 'value']:
                                value[alignmentKey] = alignmentValue
                    setValueByPathAndKey(record, data['path'], key, value, index)


    return records
            
def addImageDataFromManifests(records, manifestsFolder):

    def getImagesFromCachedManifest(manifest):
        manifestFilePath = join(manifestsFolder, urllib.parse.quote(manifest, safe='') + '.json')
        if isfile(manifestFilePath):
            with open(manifestFilePath, 'r') as f:
                content = json.load(f)
                if 'sequences' in content and len(content['sequences']) > 0:
                    canvases = [d for d in content['sequences'][0]['canvases']]
                    images = [{
                        'image': c['images'][0]['resource']['service']['@id'],
                        'width': c['width'],
                        'height': c['height']
                    } for c in canvases]
                    return {
                        "status": "success",
                        "images": images
                    }
                else:
                    return {
                        "status": "error",
                        "error": "No sequences found in manifest %s" % manifest
                    }
        else:
            return {
                "status": "error",
                "error": "Manifest file not cached: %s" % manifest
            }

    def imageListToXml(images):
        imagesNode = etree.Element("images")
        for image in images:
            imageNode = etree.SubElement(imagesNode, "image")
            etree.SubElement(imageNode, "height").text = str(image['height'])
            etree.SubElement(imageNode, "width").text = str(image['width'])
            etree.SubElement(imageNode, "url", type="iiif").text = image['image']
        return imagesNode

    errors = []
    for record in records:
        for presentation in record.findall(".//dv:iiif", namespaces={"dv": "http://dfg-viewer.de/"}):
            result = getImagesFromCachedManifest(presentation.text)
            if result['status'] == "success" and result['images']:
                presentation.getparent().append(imageListToXml(result['images']))
            else:
                errors.append(result['error'])
    errors = list(set(errors))
    if len(errors) > 0:
        print("The following errors occured:")
        for error in errors:
            print("    " + error)

    return records

def addOaiXMLData(records, oaiData):
    """
    Add the XML data retrieved from e-manuscripta via OAI to the records.
    All nodes are added to a new node called "oai". Some tags that are not
    used in the mapping are removed.

    :param records: list of CMI records
    :param oaiData: dictonary of XML data, where the key is the GUID of the record
    :return: list of CMI records with added XML data
    """

    def prepareForMerge(node):
        # Remove some nodes that will not be used in the apping
        pathsToRemove = [
            ".//{http://www.loc.gov/METS/}metsHdr",
            ".//{http://www.loc.gov/METS/}fileSec",
            ".//{http://www.loc.gov/METS/}structMap",
            ".//{http://www.loc.gov/METS/}structLink"
        ]
        nodesToRemove = [item for sublist in [node.findall(d) for d in pathsToRemove] for item in sublist]
        
        for unneeded in nodesToRemove:
            unneeded.getparent().remove(unneeded)
        
        # Remove namespaces
        for elem in node.getiterator():
            elem.tag = etree.QName(elem).localname

        return node

    for record in records:
        guid = record.find('guid').text
        if guid in oaiData:
            oaiNode = etree.SubElement(record, 'oai')
            oaiRecord = prepareForMerge(oaiData[guid])
            for child in oaiRecord.getroot():
                oaiNode.append(child)
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
        
        xml = dicttoxml(cleanedRecord, attr_type=False, custom_root='record')
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
        root = etree.XML("<collection/>")
        root.append(record)
        with open(filename, 'wb') as f:
            f.write(etree.tostring(root, pretty_print=True))

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
    if not 'manifestsFolder' in options:
        print("An input directory that contains the manifest files must be specified via the --manifestsFolder option")
        sys.exit(1)

    if not 'outputFolder' in options:
        print("An output directory must be specified via the --outputFolder option")
        sys.exit(1)

    if not 'vlidMapFile' in options:
        options['vlidMapFile'] = join(options['sourceFolder'], 'map_doi_vlid.csv')

    if not 'alignmentDataPrefix' in options:
        options['alignmentDataPrefix'] = 'alignment-'
    
    if 'limit' in options:
        options['limit'] = int(options['limit'])

    if 'onlyWithDoi' in options:
        if options['onlyWithDoi'].lower() == 'true':
            options['onlyWithDoi'] = True
        else:
            options['onlyWithDoi'] = False
    else:
        options['onlyWithDoi'] = False

    prepareData(options)
