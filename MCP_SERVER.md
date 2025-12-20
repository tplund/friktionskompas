# MCP Server - Friktionskompasset

**Version:** 1.0.0
**Fil:** `mcp_server.py`
**Protokol:** JSON-RPC 2.0 over stdin/stdout

---

## Oversigt

MCP (Model Context Protocol) serveren giver Claude Code direkte adgang til at inspicere Friktionskompasset's SQLite database. Den kører som en lokal server og kommunikerer via JSON-RPC.

**Sikkerhed:**
- Kun SELECT queries tilladt (read-only)
- SQL injection beskyttelse på tabelnavne
- Lokal server (ingen netværkseksponering)

---

## Konfiguration

### .mcp.json

```json
{
  "mcpServers": {
    "friktionskompas": {
      "command": "python",
      "args": ["C:\\_proj\\Friktionskompasset\\mcp_server.py"]
    }
  }
}
```

### Aktivering

MCP serveren startes automatisk af Claude Code når den er konfigureret i `.mcp.json`.

---

## Tilgængelige Tools

### 1. `db_status`

Hent database status med tællinger for alle hovedtabeller.

**Input:** Ingen parametre

**Output:**
```json
{
  "database": "friktionskompas_v3.db",
  "exists": true,
  "size_bytes": 1234567,
  "organizational_units": 45,
  "assessments": 12,
  "responses": 1500,
  "customers": 3,
  "users": 10,
  "profil_sessions": 50,
  "profil_questions": 48,
  "responses_with_name": 800
}
```

---

### 2. `query_db`

Kør en SELECT query mod databasen.

**Input:**
| Parameter | Type | Krævet | Beskrivelse |
|-----------|------|--------|-------------|
| `sql` | string | Ja | SQL SELECT query |
| `limit` | integer | Nej | Max rækker (default: 50) |

**Eksempel:**
```json
{
  "sql": "SELECT name, email FROM users WHERE role = 'admin'",
  "limit": 10
}
```

**Output:**
```json
{
  "row_count": 2,
  "rows": [
    {"name": "Admin", "email": "admin@example.com"},
    {"name": "Super", "email": "super@example.com"}
  ]
}
```

**Begrænsninger:**
- Kun SELECT queries (INSERT/UPDATE/DELETE afvises)
- Automatisk LIMIT tilføjes hvis ikke angivet

---

### 3. `list_tables`

List alle tabeller og indexes i databasen.

**Input:** Ingen parametre

**Output:**
```json
{
  "tables": [
    {"name": "assessments", "type": "table"},
    {"name": "customers", "type": "table"},
    {"name": "idx_responses_assessment", "type": "index"}
  ]
}
```

---

### 4. `table_schema`

Hent schema for en specifik tabel.

**Input:**
| Parameter | Type | Krævet | Beskrivelse |
|-----------|------|--------|-------------|
| `table` | string | Ja | Tabelnavn |

**Eksempel:**
```json
{
  "table": "users"
}
```

**Output:**
```json
{
  "table": "users",
  "columns": [
    {"name": "id", "type": "TEXT", "notnull": true, "default": null, "pk": true},
    {"name": "email", "type": "TEXT", "notnull": true, "default": null, "pk": false},
    {"name": "role", "type": "TEXT", "notnull": false, "default": "'manager'", "pk": false}
  ]
}
```

---

### 5. `assessment_details`

Hent detaljer for en specifik måling inkl. response statistik.

**Input:**
| Parameter | Type | Krævet | Beskrivelse |
|-----------|------|--------|-------------|
| `assessment_id` | string | Ja | Assessment ID |

**Output:**
```json
{
  "assessment": {
    "id": "camp-abc123",
    "name": "Q4 2025 Måling",
    "unit_name": "IT Afdelingen",
    "full_path": "Herning Kommune//Teknik//IT"
  },
  "response_stats": [
    {"respondent_type": "employee", "unique_respondents": 15, "total_responses": 360},
    {"respondent_type": "leader", "unique_respondents": 1, "total_responses": 24}
  ]
}
```

---

### 6. `profil_questions`

List alle profil-spørgsmål, eventuelt filtreret på type.

**Input:**
| Parameter | Type | Krævet | Beskrivelse |
|-----------|------|--------|-------------|
| `question_type` | string | Nej | Filter: sensitivity, capacity, bandwidth, screening, baseline |

**Output:**
```json
{
  "count": 6,
  "questions": [
    {
      "field": "TRYGHED",
      "layer": "ydre",
      "text_da": "Jeg føler mig tryg ved at...",
      "question_type": "screening",
      "reverse_scored": 0,
      "sequence": 1
    }
  ]
}
```

---

## Brug i Claude Code

Når MCP serveren er aktiv, kan Claude Code kalde tools direkte:

```
mcp__friktionskompas__db_status
mcp__friktionskompas__query_db { "sql": "SELECT * FROM customers" }
mcp__friktionskompas__table_schema { "table": "responses" }
```

---

## Fejlfinding

### Server starter ikke
1. Tjek at Python er installeret og i PATH
2. Tjek at `friktionskompas_v3.db` eksisterer
3. Tjek `.mcp.json` syntax

### "Only SELECT queries allowed"
MCP serveren tillader kun læsning. Brug admin routes eller direkte Python til skrivning.

### Timeout
Komplekse queries kan tage lang tid. Tilføj LIMIT eller optimer query.

---

## Sikkerhedsopdateringer

**2025-12-18 (Go-live audit):**
- Tilføjet SQL injection beskyttelse på `table_schema` tool
- Validering af tabelnavne med regex

---

*Dokumentation oprettet 2025-12-20*
