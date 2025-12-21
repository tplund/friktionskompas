# Friktionskompasset API Documentation

## Overview

The Friktionskompasset Customer API provides programmatic access to assessment data, organizational units, and friction analysis results. The API is designed for enterprise integration with HR systems, Power BI, data warehouses, and other business intelligence tools.

**Key Features:**
- RESTful design with JSON responses
- Secure API key authentication
- Multi-tenant data isolation
- Flexible pagination and filtering
- Bulk data export capabilities
- Configurable anonymization levels

## Base URLs

| Environment | URL | Language |
|-------------|-----|----------|
| Production (Danish) | `https://friktionskompasset.dk` | da |
| Production (English) | `https://frictioncompass.com` | en |

All API endpoints are prefixed with `/api/v1`.

## Authentication

All API requests require an API key in the `X-API-Key` header.

```bash
curl https://friktionskompasset.dk/api/v1/assessments \
     -H "X-API-Key: fk_xxx_xxxx_your_secret_key"
```

### Creating API Keys

API keys are created in the admin panel:
1. Navigate to **Settings → API Keys**
2. Click **Create New API Key**
3. Set permissions (read-only or read/write)
4. Copy the generated key (shown only once)

### API Key Format

API keys follow the format: `fk_<8-chars>_<43-chars>`

Example: `fk_a1b2c3d4_abcdefghijklmnopqrstuvwxyz1234567890ABC`

### Permissions

- **Read** - Access to all GET endpoints (default)
- **Write** - Access to POST endpoints (must be explicitly enabled)

## Rate Limiting

- **Limit:** 100 requests per minute per API key
- **Response when exceeded:** HTTP 429 with `Retry-After` header
- **Counter reset:** Rolling 60-second window

Example rate limit response:
```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMITED"
}
```

## Data Isolation

Each API key is scoped to a single customer. The API automatically filters all requests to ensure you can only access your organization's data.

---

## Endpoints

### 1. List Assessments

`GET /api/v1/assessments`

Retrieve a paginated list of all assessments for your organization.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status: `draft`, `sent`, `completed`, `scheduled` |
| `limit` | integer | 50 | Max results per page (max: 100) |
| `offset` | integer | 0 | Pagination offset |

**Example Request:**

```bash
curl "https://friktionskompasset.dk/api/v1/assessments?status=completed&limit=10" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Example Response:**

```json
{
  "data": [
    {
      "id": "assess-abc123",
      "name": "Gruppe-friktion Q1 2025",
      "period": "2025 Q1",
      "status": "completed",
      "type": "gruppe_friktion",
      "unit": {
        "id": "unit-xyz789",
        "name": "Birk Skole",
        "path": "Herning Kommune//Skoler//Birk Skole"
      },
      "tokens_sent": 25,
      "tokens_used": 22,
      "response_rate": 88.0,
      "include_leader": true,
      "created_at": "2025-01-15T10:30:00",
      "sent_at": "2025-01-16T08:00:00",
      "scheduled_at": null
    }
  ],
  "meta": {
    "limit": 10,
    "offset": 0,
    "total": 12
  }
}
```

**Response Fields:**

- `id` - Unique assessment identifier
- `name` - Assessment name
- `period` - Time period (e.g., "2025 Q1")
- `status` - Current status: `draft`, `sent`, `completed`, `scheduled`
- `type` - Assessment type (e.g., `gruppe_friktion`)
- `unit` - Target organizational unit
- `tokens_sent` - Number of invitations sent
- `tokens_used` - Number of completed responses
- `response_rate` - Percentage of responses (0-100)
- `include_leader` - Whether leader assessment is included
- `created_at` - Creation timestamp (ISO 8601)
- `sent_at` - When invitations were sent (ISO 8601, nullable)
- `scheduled_at` - Scheduled send time (ISO 8601, nullable)

---

### 2. Get Assessment Details

`GET /api/v1/assessments/{assessment_id}`

Retrieve detailed information about a specific assessment.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `assessment_id` | string | The assessment ID (e.g., `assess-abc123`) |

**Example Request:**

```bash
curl "https://friktionskompasset.dk/api/v1/assessments/assess-abc123" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Example Response:**

```json
{
  "data": {
    "id": "assess-abc123",
    "name": "Gruppe-friktion Q1 2025",
    "period": "2025 Q1",
    "status": "completed",
    "type": "gruppe_friktion",
    "unit": {
      "id": "unit-xyz789",
      "name": "Birk Skole",
      "path": "Herning Kommune//Skoler//Birk Skole"
    },
    "settings": {
      "min_responses": 5,
      "mode": "anonymous",
      "include_leader_assessment": true,
      "include_leader_self": false
    },
    "tokens": {
      "sent": 25,
      "used": 22
    },
    "response_count": 528,
    "created_at": "2025-01-15T10:30:00",
    "sent_at": "2025-01-16T08:00:00",
    "scheduled_at": null
  }
}
```

**Additional Response Fields:**

- `settings` - Assessment configuration
  - `min_responses` - Minimum responses required for anonymity
  - `mode` - Survey mode (e.g., `anonymous`)
  - `include_leader_assessment` - Leader assesses team
  - `include_leader_self` - Leader self-assessment
- `tokens` - Invitation statistics
- `response_count` - Total number of individual responses

---

### 3. Get Assessment Results

`GET /api/v1/assessments/{assessment_id}/results`

Retrieve friction scores and analysis results for an assessment.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `assessment_id` | string | The assessment ID |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_units` | boolean | false | Include per-unit breakdown |

**Example Request:**

```bash
curl "https://friktionskompasset.dk/api/v1/assessments/assess-abc123/results?include_units=true" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Example Response:**

```json
{
  "data": {
    "assessment": {
      "id": "assess-abc123",
      "name": "Gruppe-friktion Q1 2025",
      "period": "2025 Q1",
      "unit_name": "Birk Skole"
    },
    "scores": {
      "TRYGHED": {
        "score": 3.85,
        "percent": 77.0,
        "severity": "LOW",
        "response_count": 132
      },
      "MENING": {
        "score": 3.42,
        "percent": 68.4,
        "severity": "MEDIUM",
        "response_count": 132
      },
      "KAN": {
        "score": 3.91,
        "percent": 78.2,
        "severity": "LOW",
        "response_count": 132
      },
      "BESVÆR": {
        "score": 2.78,
        "percent": 55.6,
        "severity": "MEDIUM",
        "response_count": 132
      }
    },
    "response_count": 132,
    "unit_breakdown": [
      {
        "id": "unit-team1",
        "name": "Team 1",
        "path": "Birk Skole//Team 1",
        "tokens_sent": 12,
        "tokens_used": 11,
        "besvær_score": 2.65
      }
    ]
  }
}
```

**Friction Dimensions:**

| Field | Danish | English | Description | Interpretation |
|-------|--------|---------|-------------|----------------|
| `TRYGHED` | Tryghed | Safety | Psychological safety | Higher is better |
| `MENING` | Mening | Meaning | Sense of purpose | Higher is better |
| `KAN` | Kan | Capability | Resources & ability | Higher is better |
| `BESVÆR` | Besvær | Hassle | Bureaucracy & obstacles | **Lower is better** |

**Score Interpretation:**

- `score` - Raw score on 1-5 scale
- `percent` - Normalized percentage (0-100)
- `severity` - Friction level:
  - `LOW` - Percent > 70 (acceptable)
  - `MEDIUM` - Percent 50-70 (attention needed)
  - `HIGH` - Percent < 50 (critical)

**Note:** For BESVÆR, severity is inverted (lower scores = less friction = better).

---

### 4. Create Assessment

`POST /api/v1/assessments`

Create a new assessment. Requires **write permission** on the API key.

**Request Body (JSON):**

```json
{
  "name": "Gruppe-friktion Q2 2025",
  "period": "2025 Q2",
  "target_unit_id": "unit-xyz789",
  "type": "gruppe_friktion",
  "include_leader_assessment": true,
  "min_responses": 5
}
```

**Required Fields:**

- `name` - Assessment name
- `period` - Time period identifier
- `target_unit_id` - ID of target organizational unit

**Optional Fields:**

- `type` - Assessment type (default: `gruppe_friktion`)
- `include_leader_assessment` - Include leader assessment (default: `false`)
- `min_responses` - Minimum responses for anonymity (default: `5`)

**Example Request:**

```bash
curl -X POST "https://friktionskompasset.dk/api/v1/assessments" \
     -H "X-API-Key: fk_xxx_xxxx" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Q2 2025 Team Assessment",
       "period": "2025 Q2",
       "target_unit_id": "unit-xyz789",
       "include_leader_assessment": true
     }'
```

**Example Response:**

```json
{
  "data": {
    "id": "assess-new123",
    "name": "Q2 2025 Team Assessment",
    "period": "2025 Q2",
    "target_unit_id": "unit-xyz789",
    "status": "draft"
  },
  "message": "Assessment created successfully"
}
```

**Status Code:** 201 Created

**Notes:**
- Assessments are created with status `draft`
- Invitations must be sent through the admin interface
- The API does not support sending invitations directly

---

### 5. Get Organizational Structure

`GET /api/v1/units`

Retrieve your organization's hierarchical structure.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `flat` | boolean | false | Return flat list instead of hierarchy |
| `parent_id` | string | - | Filter to children of specific unit |

**Example Request (Hierarchical):**

```bash
curl "https://friktionskompasset.dk/api/v1/units" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Example Response (Hierarchical):**

```json
{
  "data": [
    {
      "id": "unit-root",
      "name": "Herning Kommune",
      "path": "Herning Kommune",
      "level": 0,
      "parent_id": null,
      "leader": {
        "name": "HR Afdelingen",
        "email": "hr@herning.dk"
      },
      "employee_count": 450,
      "sick_leave_percent": 3.2,
      "child_count": 3,
      "created_at": "2024-01-10T08:00:00",
      "children": [
        {
          "id": "unit-skoler",
          "name": "Skoler",
          "path": "Herning Kommune//Skoler",
          "level": 1,
          "parent_id": "unit-root",
          "leader": null,
          "employee_count": 200,
          "sick_leave_percent": 2.8,
          "child_count": 5,
          "created_at": "2024-01-10T08:05:00",
          "children": []
        }
      ]
    }
  ],
  "meta": {
    "total": 15,
    "mode": "hierarchical"
  }
}
```

**Example Request (Flat):**

```bash
curl "https://friktionskompasset.dk/api/v1/units?flat=true" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Response Fields:**

- `id` - Unique unit identifier
- `name` - Unit name
- `path` - Full hierarchical path (separator: `//`)
- `level` - Depth in hierarchy (0 = root)
- `parent_id` - Parent unit ID (null for root units)
- `leader` - Leader information (nullable)
  - `name` - Leader name
  - `email` - Leader email
- `employee_count` - Number of employees in unit
- `sick_leave_percent` - Sick leave percentage (nullable)
- `child_count` - Number of direct children
- `created_at` - Creation timestamp (ISO 8601)
- `children` - Array of child units (hierarchical mode only)

---

### 6. Bulk Data Export

`GET /api/v1/export`

Export assessment data in bulk for advanced analytics and data warehousing.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | `json` | Export format: `json` or `csv` |
| `anonymization` | string | `pseudonymized` | Anonymization level: `none`, `pseudonymized`, `full` |
| `assessment_id` | string | - | Filter to specific assessment |
| `include_responses` | boolean | true | Include individual response data |
| `include_scores` | boolean | true | Include aggregated scores |
| `include_questions` | boolean | true | Include question definitions |
| `include_units` | boolean | false | Include organizational structure |

**Anonymization Levels:**

- `none` - Real emails and names
- `pseudonymized` - UUIDs instead of emails (consistent across exports)
- `full` - All identifying information removed

**Example Request:**

```bash
curl "https://friktionskompasset.dk/api/v1/export?format=json&anonymization=pseudonymized&include_units=true" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Example Response (JSON):**

```json
{
  "data": {
    "export_date": "2025-01-20T14:30:00",
    "export_version": "1.0",
    "anonymization_level": "pseudonymized",
    "responses": [
      {
        "response_id": "resp-123",
        "question_id": 1,
        "score": 4,
        "response_date": "2025-01-16T09:23:00",
        "respondent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "is_leader": false,
        "assessment_id": "assess-abc123",
        "unit_id": "unit-xyz789",
        "unit_name": "Birk Skole"
      }
    ],
    "aggregated_scores": [
      {
        "assessment_id": "assess-abc123",
        "unit_id": "unit-xyz789",
        "unit_name": "Birk Skole",
        "field": "TRYGHED",
        "score": 3.85,
        "percent": 77.0,
        "response_count": 22
      }
    ],
    "questions": [
      {
        "id": 1,
        "sequence": 1,
        "field": "TRYGHED",
        "text_da": "Jeg kan tale frit om fejl og problemer",
        "text_en": "I can speak freely about mistakes and problems",
        "reverse_scored": 0
      }
    ],
    "units": [
      {
        "id": "unit-root",
        "name": "Herning Kommune",
        "path": "Herning Kommune",
        "parent_id": null,
        "level": 0
      }
    ]
  }
}
```

**CSV Export:**

For CSV format, the response will be a CSV file with semicolon (`;`) separators and UTF-8 encoding with BOM.

```bash
curl "https://friktionskompasset.dk/api/v1/export?format=csv" \
     -H "X-API-Key: fk_xxx_xxxx" \
     -o export.csv
```

**Use Cases:**

- Power BI integration
- Data warehouse ETL
- Custom analytics
- Compliance reporting
- Cross-system data sync

---

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE",
  "hint": "Optional suggestion for fixing the issue"
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Data returned successfully |
| 201 | Created | Assessment created |
| 400 | Bad Request | Invalid parameters or missing fields |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Insufficient permissions (write required) |
| 404 | Not Found | Assessment or unit not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error (contact support) |

### Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `AUTH_MISSING` | 401 | No X-API-Key header provided |
| `AUTH_INVALID` | 401 | Invalid or inactive API key |
| `FORBIDDEN` | 403 | Operation requires write permission |
| `NOT_FOUND` | 404 | Resource not found or not accessible |
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INVALID_PARAM` | 400 | Invalid query parameter value |

### Example Error Responses

**Missing API Key:**
```json
{
  "error": "API key required",
  "code": "AUTH_MISSING",
  "hint": "Include X-API-Key header with your API key"
}
```

**Insufficient Permissions:**
```json
{
  "error": "Write permission required",
  "code": "FORBIDDEN",
  "hint": "This API key only has read access"
}
```

**Validation Error:**
```json
{
  "error": "Missing required fields: period, target_unit_id",
  "code": "VALIDATION_ERROR"
}
```

---

## Code Examples

### Python

**Basic Usage:**

```python
import requests

API_KEY = "fk_xxx_xxxx"
BASE_URL = "https://friktionskompasset.dk/api/v1"

headers = {"X-API-Key": API_KEY}

# List assessments
response = requests.get(f"{BASE_URL}/assessments", headers=headers)
assessments = response.json()['data']

for assessment in assessments:
    print(f"{assessment['name']} - {assessment['status']}")

# Get detailed results
assessment_id = assessments[0]['id']
response = requests.get(
    f"{BASE_URL}/assessments/{assessment_id}/results",
    headers=headers,
    params={"include_units": "true"}
)
results = response.json()['data']

print(f"TRYGHED: {results['scores']['TRYGHED']['percent']}%")
print(f"Severity: {results['scores']['TRYGHED']['severity']}")
```

**Create Assessment:**

```python
import requests

API_KEY = "fk_xxx_xxxx"
BASE_URL = "https://friktionskompasset.dk/api/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

data = {
    "name": "Q2 2025 Assessment",
    "period": "2025 Q2",
    "target_unit_id": "unit-xyz789",
    "include_leader_assessment": True,
    "min_responses": 5
}

response = requests.post(
    f"{BASE_URL}/assessments",
    headers=headers,
    json=data
)

if response.status_code == 201:
    assessment = response.json()['data']
    print(f"Created: {assessment['id']}")
else:
    print(f"Error: {response.json()['error']}")
```

**Export Data:**

```python
import requests
import pandas as pd

API_KEY = "fk_xxx_xxxx"
BASE_URL = "https://friktionskompasset.dk/api/v1"

headers = {"X-API-Key": API_KEY}

# Export as JSON
response = requests.get(
    f"{BASE_URL}/export",
    headers=headers,
    params={
        "format": "json",
        "anonymization": "pseudonymized",
        "include_units": "true"
    }
)

export = response.json()['data']

# Convert to pandas DataFrames
df_responses = pd.DataFrame(export['responses'])
df_scores = pd.DataFrame(export['aggregated_scores'])

print(f"Total responses: {len(df_responses)}")
print(df_scores.groupby('field')['score'].mean())
```

---

### JavaScript (Node.js)

**Basic Usage:**

```javascript
const API_KEY = 'fk_xxx_xxxx';
const BASE_URL = 'https://friktionskompasset.dk/api/v1';

async function getAssessments() {
  const response = await fetch(`${BASE_URL}/assessments`, {
    headers: { 'X-API-Key': API_KEY }
  });

  const data = await response.json();
  return data.data;
}

async function getResults(assessmentId) {
  const response = await fetch(
    `${BASE_URL}/assessments/${assessmentId}/results?include_units=true`,
    { headers: { 'X-API-Key': API_KEY } }
  );

  const data = await response.json();
  return data.data;
}

// Usage
(async () => {
  const assessments = await getAssessments();
  console.log(`Found ${assessments.length} assessments`);

  const results = await getResults(assessments[0].id);
  console.log('Scores:', results.scores);
})();
```

**Create Assessment:**

```javascript
async function createAssessment(name, period, unitId) {
  const response = await fetch(`${BASE_URL}/assessments`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name,
      period,
      target_unit_id: unitId,
      include_leader_assessment: true,
      min_responses: 5
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error);
  }

  return await response.json();
}

// Usage
createAssessment('Q2 2025', '2025 Q2', 'unit-xyz789')
  .then(result => console.log('Created:', result.data))
  .catch(err => console.error('Error:', err.message));
```

---

### Power BI (M Query)

**Connect to API:**

```m
let
    // Configuration
    ApiKey = "fk_xxx_xxxx",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    // Fetch assessments
    Source = Json.Document(
        Web.Contents(
            BaseUrl & "/assessments",
            [
                Headers = [
                    #"X-API-Key" = ApiKey,
                    #"Content-Type" = "application/json"
                ]
            ]
        )
    ),

    // Extract data array
    Data = Source[data],

    // Convert to table
    ToTable = Table.FromList(Data, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    ExpandColumn = Table.ExpandRecordColumn(ToTable, "Column1",
        {"id", "name", "period", "status", "tokens_sent", "tokens_used", "response_rate", "created_at"}
    ),

    // Type conversions
    TypedTable = Table.TransformColumnTypes(ExpandColumn, {
        {"id", type text},
        {"name", type text},
        {"period", type text},
        {"status", type text},
        {"tokens_sent", Int64.Type},
        {"tokens_used", Int64.Type},
        {"response_rate", type number},
        {"created_at", type datetime}
    })
in
    TypedTable
```

**Fetch Results with Dynamic Assessment ID:**

```m
let
    // Configuration
    ApiKey = "fk_xxx_xxxx",
    BaseUrl = "https://friktionskompasset.dk/api/v1",
    AssessmentId = "assess-abc123",  // Or use parameter

    // Fetch results
    Source = Json.Document(
        Web.Contents(
            BaseUrl & "/assessments/" & AssessmentId & "/results",
            [
                Headers = [#"X-API-Key" = ApiKey],
                Query = [include_units = "true"]
            ]
        )
    ),

    Data = Source[data],
    Scores = Data[scores],

    // Convert scores to table
    ScoresRecord = Record.FromTable(
        Table.FromRecords({Scores})
    ),

    // Extract TRYGHED as example
    Tryghed = ScoresRecord[TRYGHED],
    TryghedScore = Tryghed[score],
    TryghedPercent = Tryghed[percent],
    TryghedSeverity = Tryghed[severity]
in
    #table(
        {"Field", "Score", "Percent", "Severity"},
        {
            {"TRYGHED", Tryghed[score], Tryghed[percent], Tryghed[severity]},
            {"MENING", ScoresRecord[MENING][score], ScoresRecord[MENING][percent], ScoresRecord[MENING][severity]},
            {"KAN", ScoresRecord[KAN][score], ScoresRecord[KAN][percent], ScoresRecord[KAN][severity]},
            {"BESVÆR", ScoresRecord[BESVÆR][score], ScoresRecord[BESVÆR][percent], ScoresRecord[BESVÆR][severity]}
        }
    )
```

**Bulk Export for Data Warehouse:**

```m
let
    // Configuration
    ApiKey = "fk_xxx_xxxx",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    // Export all data
    Source = Json.Document(
        Web.Contents(
            BaseUrl & "/export",
            [
                Headers = [#"X-API-Key" = ApiKey],
                Query = [
                    format = "json",
                    anonymization = "pseudonymized",
                    include_responses = "true",
                    include_scores = "true",
                    include_units = "true"
                ]
            ]
        )
    ),

    Data = Source[data],

    // Extract responses
    Responses = Data[responses],
    ResponsesTable = Table.FromList(Responses, Splitter.SplitByNothing()),
    ExpandResponses = Table.ExpandRecordColumn(ResponsesTable, "Column1",
        {"response_id", "question_id", "score", "response_date", "respondent_id",
         "is_leader", "assessment_id", "unit_id", "unit_name"}
    )
in
    ExpandResponses
```

---

### cURL Examples

**List Assessments:**
```bash
curl "https://friktionskompasset.dk/api/v1/assessments?status=completed&limit=20" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Get Assessment Results:**
```bash
curl "https://friktionskompasset.dk/api/v1/assessments/assess-abc123/results?include_units=true" \
     -H "X-API-Key: fk_xxx_xxxx"
```

**Create Assessment:**
```bash
curl -X POST "https://friktionskompasset.dk/api/v1/assessments" \
     -H "X-API-Key: fk_xxx_xxxx" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Q2 2025 Assessment",
       "period": "2025 Q2",
       "target_unit_id": "unit-xyz789",
       "include_leader_assessment": true
     }'
```

**Export to CSV:**
```bash
curl "https://friktionskompasset.dk/api/v1/export?format=csv&anonymization=full" \
     -H "X-API-Key: fk_xxx_xxxx" \
     -o export.csv
```

**Get Organizational Structure:**
```bash
curl "https://friktionskompasset.dk/api/v1/units?flat=true" \
     -H "X-API-Key: fk_xxx_xxxx"
```

---

## Best Practices

### Performance Optimization

1. **Use Pagination** - Always use `limit` and `offset` for large datasets
2. **Cache Results** - Assessment results don't change once completed
3. **Batch Requests** - Group related API calls when possible
4. **Filter Early** - Use query parameters to reduce response size

### Security

1. **Protect API Keys** - Never commit keys to version control
2. **Use Environment Variables** - Store keys in secure configuration
3. **Rotate Keys** - Regularly rotate API keys (recommended: quarterly)
4. **Monitor Usage** - Review API logs for unusual activity
5. **Least Privilege** - Use read-only keys unless write access is required

### Data Privacy

1. **Use Anonymization** - For external analytics, use `pseudonymized` or `full`
2. **Respect GDPR** - Only export data when legally compliant
3. **Secure Storage** - Encrypt exported data at rest
4. **Access Control** - Limit who can create/use API keys

### Error Handling

1. **Check Status Codes** - Always verify HTTP status before parsing
2. **Retry with Backoff** - For 429/500 errors, use exponential backoff
3. **Log Errors** - Capture error codes and messages for debugging
4. **Graceful Degradation** - Have fallback behavior for API failures

### Integration Patterns

**Polling Pattern:**
```python
import time

def wait_for_completion(assessment_id, timeout=3600):
    """Poll until assessment is completed."""
    start = time.time()
    while time.time() - start < timeout:
        response = requests.get(
            f"{BASE_URL}/assessments/{assessment_id}",
            headers=headers
        )
        status = response.json()['data']['status']

        if status == 'completed':
            return True
        elif status == 'failed':
            return False

        time.sleep(60)  # Check every minute

    raise TimeoutError("Assessment did not complete in time")
```

**Incremental Sync:**
```python
def sync_new_assessments(last_sync_date):
    """Sync only new assessments since last run."""
    response = requests.get(
        f"{BASE_URL}/assessments",
        headers=headers,
        params={"limit": 100}
    )

    assessments = response.json()['data']
    new_assessments = [
        a for a in assessments
        if a['created_at'] > last_sync_date
    ]

    return new_assessments
```

---

## Interactive Documentation

### Swagger UI

Interactive API documentation is available at:

**https://friktionskompasset.dk/api/docs**

Features:
- Try API calls directly in the browser
- See example requests and responses
- View complete schema definitions
- Download OpenAPI specification

### OpenAPI Specification

The full OpenAPI 3.0 specification is available at:

**https://friktionskompasset.dk/static/openapi.yaml**

Use this for:
- Generating client libraries
- API mocking and testing
- Contract-first development
- Documentation generation

---

## Support

### Contact

- **Email:** support@friktionskompasset.dk
- **Documentation:** https://friktionskompasset.dk/help
- **Status Page:** https://friktionskompasset.dk/api/status

### Common Issues

**Issue: 401 Unauthorized**
- Verify API key is correct
- Check key is active in admin panel
- Ensure X-API-Key header is set

**Issue: 429 Rate Limited**
- Implement exponential backoff
- Reduce request frequency
- Contact support for higher limits

**Issue: Empty Results**
- Verify assessment is completed
- Check minimum response threshold
- Ensure assessment belongs to your customer

**Issue: Slow Response Times**
- Use pagination to reduce payload size
- Consider caching completed assessment data
- Check network latency to servers

### Changelog

**v1.0 (2025-01-20)**
- Initial API release
- All core endpoints available
- Bulk export functionality
- OpenAPI 3.0 specification

---

## Appendix

### Field Reference

**Assessment Status Values:**
- `draft` - Created but not sent
- `sent` - Invitations sent to participants
- `completed` - All responses collected
- `scheduled` - Scheduled for future send

**Assessment Types:**
- `gruppe_friktion` - Standard team friction assessment
- `individuel_profil` - Individual B2C profile

**Respondent Types:**
- `employee` - Team member assessment
- `leader_assess` - Leader's assessment of team
- `leader_self` - Leader's self-assessment

### Database Schema

**Key Tables:**
- `assessments` - Assessment definitions
- `organizational_units` - Hierarchical organization structure
- `tokens` - Invitation tokens
- `responses` - Individual question responses
- `questions` - Question definitions
- `api_keys` - API authentication keys

### Rate Limit Details

Rate limiting uses a **token bucket algorithm**:
- Bucket size: 100 tokens
- Refill rate: 100 tokens per 60 seconds
- Each request consumes 1 token
- Bursts allowed up to bucket size

Headers in rate-limited response:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1642678900
```

---

**Last Updated:** 2025-01-20
**API Version:** 1.0
**Document Version:** 1.0
