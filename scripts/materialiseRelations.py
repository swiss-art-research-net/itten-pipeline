"""
This script inserts relations defined in a YAML file by executing
CONSTRUCT queries to a SPARQL endpoint. It is used to materialise
relations in the Knowledge Graph that cannot be defined through
field definitions.

The YAML file must contain the following fields:
- namespaces: a dictionary of namespaces used in the queries
- relations: a list of relations to be materialised
- (optional) types: a list of types that should be materialised

A relation is defined as follows:
- id: a unique identifier for the relation
- domain: the domain of the relation defined as an RDF type
- range: the range of the relation defined as an RDF type
- queryPattern: a query pattern that defines the relation
    The relation will be written as:
        ?subject ?predicate ?object .
    The ?subject variable will be injected into the query pattern.
    ?predicate and ?object must be bound in the query pattern.

If specific types should be materialised in the graph for the
?subject and ?object variables then the list of types can be
provided in the types field. The types field must be a list of
RDF types.

Example of a YAML file:

namespaces:
    rdfs: http://www.w3.org/2000/01/rdf-schema#
    skos: http://www.w3.org/2004/02/skos/core#
    schema: http://schema.org/
    dcterms: http://purl.org/dc/terms/
    foaf: http://xmlns.com/foaf/0.1/
    owl: http://www.w3.org/2002/07/owl#

types:
    - schema:Person
    - schema:Organization

relations:
    - id: hasParent
      domain: schema:Person
      range: schema:Person
      queryPattern: '{
            ?subject schema:parent ?object .
        }'
    
    - id: hasChild
      domain: schema:Person
      range: schema:Person
      queryPattern: '{
        ?object schema:parent ?subject .
        }'

Arguments:

--definitions: path to the YAML file containing the definitions
--endpoint: the SPARQL endpoint to which the queries should be sent
--graph: the named graph to which the relations should be inserted (optional)

Usage:

python materialiseRelations.py --definitions <path to YAML file> --endpoint <SPARQL endpoint> --graph <named graph>    
"""

import re
import sys
import yaml
from string import Template
from SPARQLWrapper import SPARQLWrapper

def performMaterialisation(options):

    definitionsFile = options['definitions']
    endpoint = options['endpoint']
    namedGraph = options['graph']

    with open(definitionsFile, "r") as f:
        model = yaml.safe_load(f)

    try:
        updateQuery = generateUpdateQuery(model, namedGraph=namedGraph)
    except Exception as e:
        print("Error: %s" % e)
        sys.exit(1)
    
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(updateQuery)
    sparql.setMethod('POST')

    result = sparql.query()
    if result.response.status != 200:
        print("Error: %s" % result.response.read())
        sys.exit(1)
    
    if namedGraph:
        print(f"Successfully materialised definitions from {definitionsFile} to {endpoint} in graph {namedGraph}")
    else:
        print(f"Successfully materialised definitions from {definitionsFile} to {endpoint}")

def generateUpdateQuery(model, namedGraph=None):
    output = ''

    for prefix in model['namespaces'].keys():
        output += "PREFIX %s: <%s>\n" % (prefix, model['namespaces'][prefix])

    if namedGraph:
        output += "DROP GRAPH <%s> ;" % namedGraph
    
    insertClause = """
        ?subject ?predicate ?object .
    """

    whereClause = """
        ?subject a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* $domain .
        ?object a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* $range .
    """

    if 'types' in model and len(model['types']) > 0:
        insertClause += """
            ?subject a ?subjectType .
            ?object a ?objectType .
        """
        whereClause += """
            ?subject a ?subjectType .
            ?object a ?objectType .
            VALUES(?subjectType) {""" + " ".join([f"({d})" for d in model['types']]) + """}
            VALUES(?objectType) {""" + " ".join([f"({d})" for d in model['types']]) + """}
        """

    templateString = "INSERT {"
    if namedGraph:
        templateString += "GRAPH <$graph> {"
    templateString += insertClause
    if namedGraph:
        templateString += "}"
    templateString += "} WHERE {"
    templateString += whereClause
    templateString += "\n$queryPattern\n"
    templateString += "};"

    template = Template(templateString)

    for relation in model['relations']:
        # Raise an error if not all required fields are present
        if not 'id' in relation or not 'queryPattern' in relation or not 'domain' in relation or not 'range' in relation:
            raise Exception(f"Relation {relation['id'] if 'id' in relation else ''} is missing required fields")

        queryPattern = relation['queryPattern']
        queryPattern = queryPattern.replace('$','?')

        # Make sure that the query contains ?subject, ?predicate and ?object
        # Return an error if it does not contain all three
        if not '?subject' in queryPattern or not '?predicate' in queryPattern or not '?object' in queryPattern:
            raise Exception(f"The query pattern '{relation['id']}' must contain ?subject, ?predicate and ?object")

        query = template.substitute(domain=relation['domain'], range=relation['range'], queryPattern=queryPattern, graph=namedGraph)
        output += query

    return output

if __name__ == '__main__':
    options = {}

    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--"):
            if not sys.argv[i + 2].startswith("--"):
                options[arg[2:]] = sys.argv[i + 2]
            else:
                print("Malformed arguments")
                sys.exit(1)

    if not "definitions" in options:
        print("Please provide a path to the relation definitions via the --definitions argument")
        sys.exit(1)

    if not "endpoint" in options:
        print("Please provide a SPARQL endpoint via the --endpoint argument")
        sys.exit(1)

    if not "graph" in options:
        options['graph'] = False

    performMaterialisation(options)