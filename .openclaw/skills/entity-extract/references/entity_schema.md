# Entity and Relation JSON Schema

## Entity

```json
{
  "text": "Entity name",
  "label": "PERSON|ORG|GPE|EVENT|WORK_OF_ART|CONCEPT",
  "start": 0,
  "end": 5,
  "confidence": 0.9
}
```

### Supported Entity Types (label)

| Label | Description | Examples |
|-------|-------------|----------|
| PERSON | Person name | Zhang San, Li Si |
| ORG | Organization | Peking University, China Computer Federation |
| GPE | Geopolitical entity (country/city) | China, Beijing, Shanghai |
| EVENT | Event | 2024 Conference |
| WORK_OF_ART | Work title | "Introduction to AI" |
| CONCEPT | Abstract concept | Machine Learning, Deep Learning |

## Relation

```json
{
  "source": "Source entity name",
  "target": "Target entity name",
  "relation": "Relation type",
  "timestamp": null,
  "context": "Context snippet",
  "confidence": 0.8
}
```

### Common Relation Types

| Relation | Description | Example |
|----------|-------------|---------|
| WORKS_AT | Works at | Zhang San -> Peking University |
| LIVES_IN | Lives in | Zhang San -> Beijing |
| WON | Won/received | Zhang San -> Award name |
| MEMBER_OF | Member of | Zhang San -> Association name |
| RELATED_TO | Generic association | Entity A -> Entity B |
| MENTIONED_IN | Appears in video | Entity -> Video URL |
