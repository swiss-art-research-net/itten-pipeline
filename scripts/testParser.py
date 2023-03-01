
import sys
import json
from lib.parser import Parser


def testParser(inputString):
    p = Parser()
    result = p.parse(inputString)
    print(json.dumps(result, indent=4, sort_keys=True))

if __name__ == "__main__":
    options = {}

    for i, arg in enumerate(sys.argv[1:]):
        if arg.startswith("--"):
            if not sys.argv[i + 2].startswith("--"):
                options[arg[2:]] = sys.argv[i + 2]
            else:
                print("Malformed arguments")
                sys.exit(1)

    if 'input' not in options:
        print("No input string specified")
        sys.exit(1)

    testParser(options['input'])
