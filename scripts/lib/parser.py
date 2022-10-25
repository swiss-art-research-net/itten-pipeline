import re

class Parser:
    """
    Parser to extract structured information from free text remarks in the CMI export. 
    These remarks are currently used to capture information that cannot be stored in the reference fields. 
    For example, persons that cannot unambiguously be identified in the reference fields (e.g. "Schülerin Ittens", "BesucherInnen"),
    or entities for which no reference fields exist (events, works, etc.).

    The parser defines a standard set of fields and syntax for separating fields and records. However, these can be overrwriten by the user.

    Basic Usage:
    
    >>> p = Parser()
    >>> p.parse("Person: Elfriede Rolle: Erwähnt Bemerkungen: Eine Person namens Elfriede wurde erwähnt.")
    [{'Person': {'value': 'Elfriede'}, 'Rolle': {'value': 'Erwähnt'}, 'Bemerkungen': {'value': 'Eine Person namens Elfriede wurde erwähnt.'}}]

    Custom field and record separators:

    >>> p = Parser(fieldSeparator="::", recordSeparator="|")
    >>> p.parse("Person:: Olle Rolle:: Erwähnt | Person:: Ikke Rolle:: Erwähnt")
    [{'Person': {'value': 'Olle'}, 'Rolle': {'value': 'Erwähnt'}}, {'Person': {'value': 'Ikke'}, 'Rolle': {'value': 'Erwähnt'}}]

    Custom field definitions:

    >>> fields = {"type": {}, "identifier": {"options": {"qualifier": True}}}
    >>> p = Parser(fields=fields)
    >>> p.parse("type: place identifier: Q90 (Wikidata); type: place identifier: 4044660-8 (GND)")
    [{'type': {'value': 'place'}, 'identifier': {'value': 'Q90', 'qualifier': 'Wikidata'}}, {'type': {'value': 'place'}, 'identifier': {'value': '4044660-8', 'qualifier': 'GND'}}]
    """

    FIELDS = {
        "Anzahl": {},
        "Bemerkungen": {},
        "Entität": {
            "options": {
                "qualifier": True
            }
        },
        "Typ": {},
        "Person": {
            "options": {
                "qualifier": True
            }
        },
        "Rolle": {
            "options": {
                "qualifier": True
            }
        }
    }
    
    FIELD_SEPARATOR = ":"
    RECORD_SEPARATOR = ";"

    def __init__(self, *, fields=None, fieldSeparator=None, recordSeparator=None):
        if fields:
            self.FIELDS = fields
        if fieldSeparator:
            self.FIELD_SEPARATOR = fieldSeparator
        if recordSeparator:
            self.RECORD_SEPARATOR = recordSeparator
    
    def _extractRecordBlocks(self, text):
        try:
            records = [d.strip() for d in text.split(self.RECORD_SEPARATOR)]
        except Exception as e:
            raise e
        return records    
    
    def _parseRecordBlock(self, text):
        record = {}
        pattern = f'({ "|".join(self.FIELDS.keys())}){ self.FIELD_SEPARATOR}'
        matches = re.finditer(pattern, text)
        spans = []
        for match in matches:
            spans.append(match.span())
        for i, span in enumerate(spans):
            key = text[span[0]:span[1] - len(self.FIELD_SEPARATOR)]
            record[key] = {}
            raw = text[span[1] + 1 : spans[i + 1][0] if i < len(spans) - 1 else None ].strip()
            if 'options' in self.FIELDS[key] and self.FIELDS[key]['options']['qualifier']:
                qualifier = re.search(r'\((.*?)\)$', raw)
                if qualifier:
                    record[key]['value'] = raw.replace(f'({qualifier.group(1)})', '').strip()
                    record[key]['qualifier'] = qualifier.group(1)
                else:
                    record[key]['value'] = raw
            else:
                    record[key]['value'] = raw
            if "#" in record[key]['value']:
                record[key] = self._processIdentifiers(record[key])
        return record

    def _processIdentifiers(self, item):
        """
        If an identifier is set in the value (e.g. #GND4127793-4) extract it and add it as key 'identifier' to the item.
        The extracted identifier is then removed from the value
        """
        sources = ['GND']
        identifiers = re.findall(r'#([\w\d\-]+)', item['value'])
        if len(identifiers):
            item['identifiers'] = []
            for identifier in identifiers:
                position = item['value'].find("#%s" % identifier)
                item['value'] = item['value'].replace(f' #{identifier}', '').strip()
                identifierObject = {'position': position}
                for source in sources:
                    if identifier.startswith(source):
                        identifierObject['source'] = source
                        identifierObject['value'] = identifier.replace(source, '')
                item['identifiers'].append(identifierObject)
        return item
        
    
    def parse(self, text):
        """
        Parse an internal remarks string into a set of records

        >>> p = Parser()
        >>> example1 = "Person: Hans Rolle: Erwähnt Bemerkungen: Eine Person namens Hans wurde erwähnt."
        >>> p.parse(example1)
        [{'Person': {'value': 'Hans'}, 'Rolle': {'value': 'Erwähnt'}, 'Bemerkungen': {'value': 'Eine Person namens Hans wurde erwähnt.'}}]

        >>> example2 = "Person: Schülerin Ittens Rolle: Erwähnt (Empty) Bemerkungen: Eine Schülerin, eventuell Natascha D., wird erwähnt."
        >>> p.parse(example2)
        [{'Person': {'value': 'Schülerin Ittens'}, 'Rolle': {'value': 'Erwähnt', 'qualifier': 'Empty'}, 'Bemerkungen': {'value': 'Eine Schülerin, eventuell Natascha D., wird erwähnt.'}}]

        >>> example3 = "Person: BesucherInnen Rolle: Erwähnt Anzahl: >1; Person: Mitarbeitende Rolle: Erwähnt Anzahl: 10 Bemerkungen: Die Mitarbeitenden haben die Ausstellung betreut"
        >>> p.parse(example3)
        [{'Person': {'value': 'BesucherInnen'}, 'Rolle': {'value': 'Erwähnt'}, 'Anzahl': {'value': '>1'}}, {'Person': {'value': 'Mitarbeitende'}, 'Rolle': {'value': 'Erwähnt'}, 'Anzahl': {'value': '10'}, 'Bemerkungen': {'value': 'Die Mitarbeitenden haben die Ausstellung betreut'}}]

        >>> example4 = 'Person: Direktor (Chirurgische Klinik (Zürich)) Rolle: Erwähnt (Empty) Bemerkungen: vermutlich Brunner, Alfred (Link zur GND: <a href=http://d-nb.info/gnd/13133056Xtarget="_blank">GND</a>)'
        >>> p.parse(example4)
        [{'Person': {'value': 'Direktor', 'qualifier': 'Chirurgische Klinik (Zürich)'}, 'Rolle': {'value': 'Erwähnt', 'qualifier': 'Empty'}, 'Bemerkungen': {'value': 'vermutlich Brunner, Alfred (Link zur GND: <a href=http://d-nb.info/gnd/13133056Xtarget="_blank">GND</a>)'}}]

        >>> example5 = 'Entität: Mona Lisa #GND4074156-4 Typ: Werk Rolle: Erwähnt Bemerkung: ...'
        >>> p.parse(example5)
        [{'Entität': {'value': 'Mona Lisa #GND4074156-4'}, 'Typ': {'value': 'Werk'}, 'Rolle': {'value': 'Erwähnt Bemerkung: ...'}}]
        """
        records = []
        recordBlocks = self._extractRecordBlocks(text)
        for recordBlock in recordBlocks:
            parsedBlock = self._parseRecordBlock(recordBlock)
            if len(parsedBlock):
                records.append(parsedBlock)
        return records

if __name__ == '__main__':
    import doctest
    doctest.testmod()