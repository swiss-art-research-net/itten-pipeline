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
        "Anzahl": {
            "options": {
                "qualifier": True
            }
        },
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
            raw = text[span[1] + 1 : spans[i + 1][0] if i < len(spans) - 1 else None ].strip()
            if 'options' in self.FIELDS[key] and self.FIELDS[key]['options']['qualifier']:
                qualifier = re.search(r'\((.*?)\)$', raw)
                if qualifier:
                    value = raw.replace(f'({qualifier.group(1)})', '').strip()
                    qualifier = qualifier.group(1)
                    record = self._updateRecord(record, key=key, value=value, qualifier=qualifier)
                else:
                    record = self._updateRecord(record, key=key, value=raw)
            else:
                    record = self._updateRecord(record, key=key, value=raw)
        return record
        
    def _updateRecord(self, record, *, key, value, qualifier=False):
        """
        Update a record with a new key/value pair and an optional identifier.
        The value is converted to an object that contains the value as well as any identifiers that are extracted automatically.
        If the key does not yet exist in the record, it is created and the data is added.
        If the key already exists, the new value is appended to a list of values, converting the previous value to a list if necessary.

        :param record: The record to update
        :param key: The key to update
        :param value: The value to add
        :param qualifier: An optional qualifier for the value
        :return: The updated record
        """
        obj = { 'value': value }
        if "#" in value:
            value, identifiers = self.processIdentifiers(value)
            obj['value'] = value
            obj['identifiers'] = identifiers
            
        if qualifier:
            obj['qualifier'] = qualifier
            
        if not key in record:
            # If key is not yet set we just add the data under the key
            record[key] = obj
        elif isinstance(record[key], list):
            # If the key already contains a list we add a new object to that list
            record[key].append(obj)
        else:
            # If the key exists but is not yet a list we convert it into a list, appendig the new object
            record[key] = [ record[key], obj]
        return record
    
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
        [{'Entität': {'value': 'Mona Lisa', 'identifiers': [{'position': 10, 'source': 'GND', 'value': '4074156-4'}]}, 'Typ': {'value': 'Werk'}, 'Rolle': {'value': 'Erwähnt Bemerkung: ...'}}]
        
        >>> example6 = 'Entität: Taube Rolle: Abgebildet Rolle: Erwähnt Bemerkungen: Eine Taube ist auf dem Bild zu sehen und wird im Brief mehrfach erwähnt.'
        >>> p.parse(example6)
        [{'Entität': {'value': 'Taube'}, 'Rolle': [{'value': 'Abgebildet'}, {'value': 'Erwähnt'}], 'Bemerkungen': {'value': 'Eine Taube ist auf dem Bild zu sehen und wird im Brief mehrfach erwähnt.'}}]
        
        """
        records = []
        recordBlocks = self._extractRecordBlocks(text)
        for recordBlock in recordBlocks:
            parsedBlock = self._parseRecordBlock(recordBlock)
            if len(parsedBlock):
                records.append(parsedBlock)
        return records

    def processIdentifiers(self, value):
        """
        If an identifier is set in the value (e.g. #GND4127793-4) extract them.
        The extracted identifier is then removed from the value.
        The function returns the changed value and a list of extracted identifiers

        >>> p = Parser()
        >>> text, identifiers = p.processIdentifiers("Eine Person namens Elfriede wurde erwähnt. Möglicherweise Elfriede Röllich #GND1091599890 die in dieser Zeit am Institut gearbeitet hat")
        >>> print(identifiers)
        [{'position': 75, 'source': 'GND', 'value': '1091599890'}]

        >>> text, identifiers = p.processIdentifiers("Stammt ursprünglich aus Krefeld #GND4032952-5")
        >>> print(identifiers)
        [{'position': 32, 'source': 'GND', 'value': '4032952-5'}]

        >>> text, identifiers = p.processIdentifiers("Rudolf, möglicherweise Rudolf Braun #GND120094478X, alternativ Rudolf Brun #GND1196571228")
        >>> print(identifiers)
        [{'position': 36, 'source': 'GND', 'value': '120094478X'}, {'position': 60, 'source': 'GND', 'value': '1196571228'}]

        >>> text, identifiers = p.processIdentifiers("Möglicherweise Lilly von Andrese #WDQ115482867")
        >>> print(identifiers)
        [{'position': 33, 'source': 'WD', 'value': 'Q115482867'}]
        """
        sources = ['GND', 'WD']
        extractedIdentifiers = re.findall(r'#([\w\d\-]+)', value)
        if len(extractedIdentifiers):
            identifiers = []
            for extractedIdentifier in extractedIdentifiers:
                position = value.find("#%s" % extractedIdentifier)
                value = value.replace(f' #{extractedIdentifier}', '').strip()
                identifierObject = {'position': position}
                for source in sources:
                    if extractedIdentifier.startswith(source):
                        identifierObject['source'] = source
                        identifierObject['value'] = extractedIdentifier.replace(source, '')
                if 'source' in identifierObject:
                    identifiers.append(identifierObject)
        return value, identifiers

if __name__ == '__main__':
    import doctest
    print("Running doctests...")
    doctest.testmod()