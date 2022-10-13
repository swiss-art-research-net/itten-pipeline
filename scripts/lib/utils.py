import chardet
import csv
import json
import re
import requests
import sys
from bs4 import BeautifulSoup
from os import listdir
from os.path import join

class RetrieveVLIDfromDOI:
    # Class to retrieve VLIDs based on DOI
    # Uses a Map file to retrieve corresponding VLID from DOI
    # If VLID is not present, scrapes it from e-manuscripta
    
    vlidMap = {}
    vlidMapFile = ''
    
    def __init__(self, *, vlidMapFile):
        self.vlidMapFile = vlidMapFile
        try:
            with open(vlidMapFile,'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.vlidMap[row['doi']] = row['vlid']
        except:
            self.vlidMap = {}

    def getVlidForDoi(self, doi):
        if doi in self.vlidMap:
            return self.vlidMap[doi]
        return self._retrieveVlidForDoi(doi)
    
    def writeVlidMap(self):
        with open(self.vlidMapFile,'w') as f:
            writer = csv.DictWriter(f, fieldnames=['doi','vlid'])
            writer.writeheader()
            for doi, vlid in sorted(self.vlidMap.items()):
                writer.writerow({'doi': doi, 'vlid': vlid})
    
    def _retrieveVlidForDoi(self, doi):
        # Parse HTML returned from e-manuscripta to get VLID
        rawHtml = requests.get(doi).text
        soup = BeautifulSoup(rawHtml, 'html.parser')
        try:
            link = soup.find('a', {"target": "iiif-manifest"}).get('href')
        except:
            print("No link found for DOI %s" % doi)
            return None
        idSearch = re.search(r'/i3f/v20/(\d*)/manifest', link)
        if idSearch:
            vlid = idSearch.group(1)
            self._updateVlidMap(doi=doi, vlid=vlid)
            return vlid
        else:
            return None
        
    def _updateVlidMap(self, *, doi, vlid):
        self.vlidMap[doi] = vlid


def readRecords(directory, *, detectEncoding=False, encoding='Windows-1252'):
    """
    Reads all JSON files in the given directory and returns a list of records.
    The link to the digitised version is extracted and stored in the doi field.

    :param directory: directory containing the JSON files
    :return: list of records
    """
    inputFiles = [join(directory, d) for d in listdir(directory) if d.endswith('.json')]
    records = []
    for file in inputFiles:
        if detectEncoding:
            fileEncoding = chardet.detect(open(file, 'rb').read())['encoding']
        else:
            fileEncoding = encoding
        with open(file, 'r', encoding=fileEncoding) as f:
            try:
                text = f.read()
            except Exception as e:
                print('Error while reading the data: %s' % e)
                sys.exit(1)

            decodedData = text.encode().decode('utf-8-sig') 
            try:
                data = json.loads(decodedData, strict=False)
                records += data
            except Exception as e:
                print('Error while parsing the file %s: %s' % (file, e))
                charSearch = re.search(r'char (\d+)', str(e))
                if charSearch:
                    charPos = int(charSearch.group(1))
                    padding = 10
                    print(decodedData[charPos-padding:charPos-1] + "-->" + decodedData[charPos] + "<--" + decodedData[charPos+1:charPos+padding])
                    sys.exit(1)

    for record in records:
        if record['Link zu Digitalisat']:
            link = BeautifulSoup(record['Link zu Digitalisat'], 'html.parser')
            record['doi'] = link.find('a').text
            
    # Return only unique records based on GUID
    records = list({v['GUID']:v for v in records}.values())
            
    return records
