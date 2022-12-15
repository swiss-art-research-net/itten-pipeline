"""
This script prepares the data for mapping. 
It converts the source data to XML and adds the XML data retrieved from e-manuscripta via OAI.

Usage:

python prepareDataForMapping.py --sourceFolder=<sourceFolder> --oaiXMLFolder=<oaiXMLFolder> --outputFolder=<outputFolder>

Parameters:
    --sourceFolder        The folder containing the source JSON data
    --oaiXMLFolder        The folder containing the XML data retrieved from e-manuscripta
    --manifestsFolder     The folder containing the cached IIIF manifests
    --outputFolder        The folder to write the output XML files to
    --limit               Limit the number of records to process
    --offset              Offset the number of records to process
    --idsToOutput         Only output records with the given ids (pass as comma separated list) (optional)
    --alignmentDataPrefix The prefix of the alignment data files. Defaults to "alignment-" (optional)
    --vlidMapFile         The path to the file containing the mapping between VLIDs and DOIs (optional)
    --onlyWithDoi         If set to true, only records that contain a DOI are output (optional)
    --logFile             The path to a log file (optional)
"""

import csv
import json
import logging
import re
import sys
import unicodedata
import urllib
from dicttoxml import dicttoxml
from lxml import etree
from os.path import join, isfile
from tqdm import tqdm

from edtf import parse_edtf
from lib.utils import readRecords, RetrieveVLIDfromDOI
from lib.parser import Parser
from sariDateParser.dateParser import parse

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
        records = records[options['offset']:options['offset'] + options['limit']]
    elif 'offset' in options:
        records = records[options['offset']:]

    # Limit to records with given ids if specified
    if 'idsToOutput' in options:
        idsToOutput = options['idsToOutput'].split(',')
        records = [d for d in records if d['GUID'] in idsToOutput]

    # Retrieve OAI records for records that have VLIDs
    oaiXmlData = retrieveOaiXMLData(records=records, oaiXMLFolder=oaiXMLFolder, vlidMapFile=vlidMapFile)

    # Add alignment data
    records = addAlignmentData(records, sourceFolder=sourceFolder, alignmentDataPrefix=alignmentDataPrefix)
    
    # Parse internal remarks
    records = parseInternalRemarks(records)

    # Convert to XML
    recordsXML = convertRecordsToXML(records, flattenLists=True)

    # Remove null values
    recordsXML = removeNullValues(recordsXML)

    # Add data from OAI XML files
    recordsXML = addOaiXMLData(recordsXML, oaiXmlData)

    # Remove Itten Archive node from XML
    recordsXML = removeIttenArchiveNode(recordsXML)

    # Add role codes to Register entries
    recordsXML = addRoleCodesToRegisters(recordsXML)

    # Parse dates
    recordsXML = parseDates(recordsXML)

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
        "archivalienarten": ["Archivalienarten", "Bezeichnung"],
        "sprachen": ["Sprachen", "Bezeichnung"],
        "verzeichnungsstufe": ["Verzeichnungsstufe"]
    }

    alignmentData = readAlignmentFiles(fieldsToAlign, sourceFolder=sourceFolder, alignmentDataPrefix=alignmentDataPrefix)
    
    for data in alignmentData.values():
        for record in records:
            # Get record value by path
            if len(data['path']) > 1:
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
                                if alignmentKey not in ['key', 'path', 'value', None]:
                                    value[alignmentKey] = alignmentValue
                            setValueByPathAndKey(record, data['path'], key, value, index)
            else:
                value = record[data['path'][0]]
                key = data['path'][0]
                if isinstance(value, str):
                    try:
                        alignmentValue = data['content'][data['lookup'][customHash(value)]]
                    except:
                        print("Could not find alignment value for: " + str(value))
                        sys.exit(1)
                    newValue = {'value': value}
                    for alignmentKey, alignmentValue in alignmentValue.items():
                        if alignmentKey not in ['key', 'path', None]:
                            if alignmentValue:
                                newValue[alignmentKey] = alignmentValue
                    setValueByPathAndKey(record, data['path'], key, newValue, index)


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
            imageNode.set("id",image['image'].rsplit('/', 1)[-1])
            etree.SubElement(imageNode, "height").text = str(image['height'])
            etree.SubElement(imageNode, "width").text = str(image['width'])
            etree.SubElement(imageNode, "url", type="iiif").text = image['image']
        return imagesNode

    errors = []
    for record in records:
        for presentation in record.findall(".//iiif"):
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

def addRoleCodesToRegisters(records):
    """
    The registereintrage/item nodes contain a tag register_rolle that
    specifies the role of the linked entity in free text. The text contains
    a LOC role code, which we extract here and add as an attribute to the register_rolle node.
    We also add the label as an attribute. If no LOC role code is present only the label is added.

    :param records: list of CMI records
    :return: list of CMI records with added role codes and labels
    """

    def convertUmlauts(text):
        """
        Convert Umlauts to two characters
        """
        text = text.replace("ä", "ae")
        text = text.replace("ö", "oe")
        text = text.replace("ü", "ue")
        text = text.replace("Ä", "Ae")
        text = text.replace("Ö", "Oe")
        text = text.replace("Ü", "Ue")
        text = text.replace("ß", "ss")
        return text

    rTwoCodes = r'(\w{3})(?=\))\)\s\(([^)]*)\)'
    rOneCode = r'\(([^)]*)\)$'
    rRole = r'^(\S*)'

    for record in records:
        for item in record.findall(".//registereintraege"):
            role = item.find("register_rolle")
            if role is not None:
                if re.search(rTwoCodes, role.text):
                    role.set("code", re.search(rTwoCodes, role.text).group(1))
                    role.set("label", re.search(rTwoCodes, role.text).group(2).lower())
                elif re.search(rOneCode, role.text):
                    role.set("label", re.search(rOneCode, role.text).group(1).lower())
                if re.search(rRole, role.text):
                    term = re.search(rRole, role.text).group(1).lower()
                    term = convertUmlauts(term)
                    role.set("term", term)
    return records

def convertRecordsToXML(records, *, removeEmptyNodes=True, flattenLists=False):
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
        
        xmlString = dicttoxml(cleanedRecord, attr_type=False, custom_root='record')
        try:
            xml = etree.fromstring(xmlString)
        except Exception as e:
            print("Error converting record to XML: %s" % e)
            column = int(re.findall(r'column (\d+)', str(e))[0])
            padding = 20
            print("Error in column %s" % column)
            print(xmlString[column-padding:column-1].decode('utf-8-sig') + "-->" + xmlString[column:column+1].decode('utf-8-sig') + "<--" + xmlString[column+1:column+padding].decode('utf-8-sig'))
            sys.exit(1)

        if flattenLists:
            for item in xml.findall(".//item"):
                parent = item.getparent()
                grandparent = parent.getparent()
                item.tag = parent.tag
                parent.addnext(item)
                if len(parent) == 0:
                    grandparent.remove(parent)

        # Remove empty nodes
        if removeEmptyNodes:
            for empty in xml.xpath('//*[not(node())]'):
                empty.getparent().remove(empty)
        
        # Add indices to nodes. We use this to create unique URIs for repeating nodes.
        prevTag = None
        index = 0
        for node in xml.getchildren():
            if node.tag != prevTag:
                index = 0
            node.set('index', str(index))
            index += 1
            prevTag = node.tag

        return xml

    xmlRecords = []
    for record in records:
        xmlRecords.append(convertCmiJSONtoXML(record))
    return xmlRecords

def parseDates(records):
    """
    Parse dates in XML records and add them in machine readable format as attributes.

    :param records: list of XML records
    :return: list of XML records with added dates
    """

    def parseDate(dateString):
        """
        Parse a date string and return a list containing one or two dates (date range).
        The date can be a single date or of the form "DD.MM.YYYY - DD.MM.YYYY".
        Therefore we need to split the string and parse the two dates separately.
        """
        dates = []
        if " - " in dateString:
            for date in dateString.split(" - "):
                parsedDate = parse(date)
                if parsedDate:
                    dates.append(parsedDate)
        else:
            parsedDate = parse(dateString)
            if parsedDate:
                dates.append(parsedDate)

        return dates

    tagsWithDates = ['register_datum']
    for record in records:
        for tag in tagsWithDates:
            for tagWithDate in record.findall(".//%s" % tag):
                if tagWithDate.text is not None and tagWithDate.text != "null":
                    dates = parseDate(tagWithDate.text)
                    if dates is not None:
                        tagWithDate.set("dateFrom", dates[0])    
                        if len(dates) == 2:
                            tagWithDate.set("dateTo", dates[1])
    return records

def parseInternalRemarks(records):
    """
    Parse the semi-structured information specified as part of the internal remarks node ("Allgemeine Interne Anmerkungen")

    :param records: list of CMI records in source format
    :return: list of CMI records in source format with parsed internal remarks
    """
    p = Parser()
    internalRemarksKey = "Allgemeine Interne Anmerkungen"
    for record in records:
        remarks = record[internalRemarksKey]
        if remarks:
            record["parsed internal remarks"] = p.parse(remarks)

    return records

def removeIttenArchiveNode(records):
    """
    Remove the node in the data retrieved from e-manuscripta that refers to the Itten Archive as a whole.
    It is found the oai/metadata/mets/dmdsec node where mdWrap/xmlData/mods/recordInfo/recordIdentifier/text() is 43a2ab3eb18841db9ec1af3669b74f39

    :param records: list of CMI records
    :return: list of CMI records with removed Itten Archive node
    """
    for record in records:
        for node in record.findall(".//oai/metadata/mets/dmdSec"):
            if node.find('mdWrap/xmlData/mods/recordInfo/recordIdentifier').text == '43a2ab3eb18841db9ec1af3669b74f39':
                node.getparent().remove(node)
    return records

def removeNullValues(records):
    """
    The JSON export coming from CMI encodes null values as strings "null". This function removes these values.
    After converting to XML, these appear as XML nodes with the text "null". This function removes the text of these nodes.
    Note: This is a workaround that should no longer be necessary when the JSON export from CMI is fixed. Otherwise it might produce side effects in cases where the string "null" is actually intended.
    """
    for record in records:
        for node in record.xpath(".//*[text()='null']"):
            node.text = None
    return records

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
    
    if 'offset' in options:
        options['offset'] = int(options['offset'])
    else:
        options['offset'] = 0

    if 'logfile' in options:
        logging.basicConfig(filename=options['logfile'], level=logging.DEBUG)

    if 'onlyWithDoi' in options:
        if options['onlyWithDoi'].lower() == 'true':
            options['onlyWithDoi'] = True
        else:
            options['onlyWithDoi'] = False
    else:
        options['onlyWithDoi'] = False

    prepareData(options)
