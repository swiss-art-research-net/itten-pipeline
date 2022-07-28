import csv
import json
import re
import requests
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
