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

    print(updateQuery)

def generateUpdateQuery(model, namedGraph=None):
    output = ''

    for prefix in model['namespaces'].keys():
        output += "PREFIX %s: <%s>\n" % (prefix, model['namespaces'][prefix])

    if namedGraph:
        output += "DROP GRAPH <%s> ;" % namedGraph
        template = Template("""
            INSERT {
                GRAPH <$graph> {
                    ?subject ?predicate ?object .
                    ?subject a $domain .
                    ?object a $range .
                }
            } WHERE {
                ?subject a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* $domain .
                ?object a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* $range .
                $queryPattern
            };
        """)
    else:
        template = Template("""
            INSERT {
                ?subject ?predicate ?object .
                ?subject a $domain .
                ?object a $range .
            } WHERE {
                ?subject a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* $domain .
                ?object a/<http://www.w3.org/2000/01/rdf-schema#subClassOf>* $range .
                $queryPattern
            };
        """)

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