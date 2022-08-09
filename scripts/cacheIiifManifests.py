import json
import requests
import threading
import urllib
import sys
from lxml import etree
from os import listdir
from os.path import isfile, join
from tqdm import tqdm

def performCaching(options):
    oaiXMLFolder = options['oaiXMLFolder']
    outputFolder = options['outputFolder']
    offset = options['offset']
    limit = options['limit']

    # Extract manifests from XML files from input folder
    manifests = extractManifests(oaiXMLFolder)

    messages = fetchManifests(manifests, outputFolder, offset=offset, limit=limit)
    errors = [m for m in messages if m['status'] == 'error']
    print("Found %d manifests" % len(manifests))
    print("Retrieved %d manifests" % len([m for m in messages if m['status'] == "success"]))
    print("Already cached %d manifests" % len([d for d in listdir(outputFolder) if d.endswith(".json")]))
    if len(errors):
        print("Encountered the following errors:")
        for m in errors:
            print("    " + str(m['error']) + ": " + m['url'])

def extractManifests(inputFolder):
    """
    Read the XML files in the given input folder and add the manifests contained in
    the <dv:presentation> element to a list.

    :param inputFolder: The folder containing the XML files.
    :return: A list of manifests.
    """
    manifests = []
    for filename in tqdm(listdir(inputFolder)):
        if isfile(join(inputFolder, filename)) and filename.endswith(".xml"):
            with open(join(inputFolder, filename), 'r') as f:
                xml = f.read()
            root = etree.fromstring(xml)
            for presentation in root.findall(".//dv:iiif", namespaces={"dv": "http://dfg-viewer.de/"}):
                manifests.append(presentation.text)
    return list(set(manifests))

def fetchManifests(manifests, outputFolder, *, offset, limit):
    """
    Fetch the manifests from the given list and write them to the given output folder.
    Returns a list of messages indicating the status of the fetching.
    """
    urlsAndFilenames = [{
        "manifest": d,
        "filename": join(outputFolder, urllib.parse.quote(d, safe='')) + '.json'
        } for d in manifests]

    messages = []
    for row in tqdm(urlsAndFilenames[offset:offset + limit]):
        if not isfile(row['filename']):
            if row['manifest']:
                messages.append(fetchJsonFile(row['manifest'], row['filename']))
    return messages

def fetchJsonFile(url, filename):
    """
    Fetch the JSON file at the given URL and write it to the given filename.
    Returns a message indicating the status of the fetching.
    """
    try:
        urlHandler = urllib.request.urlopen(url)
        data = urlHandler.read()
        content = json.loads(data.decode('utf-8'))
        with open(filename, 'w') as f:
            json.dump(content, f, indent=4)
        return {"status": "success"}
    except urllib.error.HTTPError as e:
        return {"status": "error", "error": e, "url": url}
        



if __name__ == "__main__":
    options = {}

    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--"):
            if not sys.argv[i + 2].startswith("--"):
                options[arg[2:]] = sys.argv[i + 2]
            else:
                print("Malformed arguments")
                sys.exit(1)

    
    if not 'oaiXMLFolder' in options:
        print("An input directory that contains the OAI XML files must be specified via the --oaiXMLFolder option")
        sys.exit(1)

    if not 'outputFolder' in options:
        print("An output directory must be specified via the --outputFolder option")
        sys.exit(1)

    if 'offset' in options:
        options['offset'] = int(options['offset'])
    else:
        options['offset'] = 0

    if 'limit' in options:
        options['limit'] = int(options['limit'])
    else:
        options['limit'] = 999999

    performCaching(options)