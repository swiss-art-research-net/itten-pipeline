import json
import sys

from rdflib import Graph
from urllib import request
from os import path, walk
from tqdm import tqdm

PREFIXES = """
    PREFIX gvp:  <http://vocab.getty.edu/ontology#>
    PREFIX gndo:  <https://d-nb.info/standards/elementset/gnd#>
    """

def retrieveData(options):
    sourceFolder = options['sourceFolder']
    targetFolder = options['targetFolder']
    sources = options['sources']

    sourceIdentifiers = extractIdentifiers(sourceFolder, sources)

    if 'gnd' in sourceIdentifiers and len(sourceIdentifiers['gnd']) > 0:
        status = retrieveGndData(sourceIdentifiers['gnd'], targetFolder)
        if status['status'] == 'success':
            print(status['message'])
        else:
            print("Error:", status['message'])
            sys.exit(1)
    

def extractIdentifiers(folder, sources):
    """
    Extracts the identifiers from the Turtle files in the given folder.
    The kind of identifiers that are extracted are specified in the sources parameter.

    :param folder: The folder where the Turtle files are stored.
    :param sources: The kind of identifiers that are extracted given as a list of strings.
    :return: A dictionary with the sources as keys and the list of distinct identifiers as value.
    """

    identifierQueries = {
        "aat": "?identifier a gvp:Concept .",
        "gnd": """
            ?s ?p ?identifier .
            FILTER(REGEX(STR(?identifier),"https://d-nb.info/gnd/"))
        """,
        "loc": """
            ?s ?p ?identifier .
            FILTER(REGEX(STR(?identifier),"http://id.loc.gov/"))
        """,
        "wd": """
            ?identifier ?p ?o .
            FILTER(REGEX(STR(?identifier),"http://www.wikidata.org/entity/"))
        """
    }

    identifiers = {}
    for source in sources:
        identifiers[source] = []

    files = [path.join(root, name)
             for root, dirs, files in walk(folder)
             for name in files
             if name.endswith((".ttl"))]
    
    for file in tqdm(files):
        g = Graph() 
        g.parse(file)
        for source in sources:
            query = PREFIXES + "SELECT DISTINCT ?identifier WHERE { " + identifierQueries[source] + " }"
            queryResults = g.query(query)
            for row in queryResults:
                identifiers[source].append(str(row[0]))
    
    return identifiers
    
def queryIdentifiersInFile(sourceFile, queryPart):
    identifiers = []
    if path.isfile(sourceFile):
        data = Graph()
        data.parse(sourceFile, format='turtle')
        queryResults = data.query("SELECT DISTINCT ?identifier WHERE {" + queryPart + "}")
        for row in queryResults:
            identifiers.append(str(row[0]))
    return identifiers

def retrieveGndData(identifiers, targetFolder):
    # Read the output file and query for existing URIs
    targetFile = path.join(targetFolder, 'gnd.ttl')
    existingIdentifiers = queryIdentifiersInFile(targetFile, "?identifier a gndo:AuthorityResource .")
    # Filter out existing identifiers
    identifiersToRetrieve = [d for d in identifiers if d not in existingIdentifiers]
    # Retrieve ttl data from GND and append to ttl file
    with open(targetFile, 'a') as outputFile:
        for identifier in tqdm(identifiersToRetrieve):
            url = "%s.ttl" % identifier.replace("https://d-nb.info/gnd/","https://lobid.org/gnd/")
            try:
                with request.urlopen(url) as r:
                    content = r.read().decode()
                outputFile.write(content + "\n")
                outputFile.flush()
            except:
                print("Could not retrieve", url)
    return {
        "status": "success",
        "message": "Retrieved %d additional GND identifiers (%d present in total)" % (len(identifiersToRetrieve), len(identifiers))
    }


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
        print("An input directory that contains the source TTL files must be specified via the --sourceFolder option")
        sys.exit(1)

    if not 'targetFolder' in options:
        print("An output directory must be specified via the --targetFolder option")
        sys.exit(1)
  
    if not 'sources' in options:
        print("A comma-separated list of sources must be specified via the --sources option")
        sys.exit(1)
    
    if 'limit' in options:
        options['limit'] = int(options['limit'])

    options['sources'] = options['sources'].split(',')

    # Check if list of sources only contains supported sources
    supportedSources = ["aat", "gnd", "loc", "wd"]
    for source in options['sources']:
        if source not in supportedSources:
            print("Source {} is not supported".format(source))
            print("Supported sources are: {}".format(", ".join(supportedSources)))
            sys.exit(1)

    retrieveData(options)
