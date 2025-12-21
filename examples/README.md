# Friktionskompasset API - Integration Examples

This directory contains working examples for integrating with the Friktionskompasset API in various programming languages and platforms.

## Available Examples

### 1. Python Integration (`python_example.py`)

Comprehensive Python example using the `requests` library.

**Requirements:**
```bash
pip install requests pandas
```

**Usage:**
```bash
export FRIKTIONSKOMPASSET_API_KEY="fk_xxx_xxxx"
python python_example.py
```

**Features:**
- Full client implementation with error handling
- List and filter assessments
- Get friction scores and analysis results
- Explore organizational structure
- Create new assessments (requires write permission)
- Export bulk data
- Pandas integration for data analysis
- Monitor response rates

**Best For:**
- Data science and analytics
- Automated reporting
- ETL pipelines
- Custom integrations

---

### 2. JavaScript/Node.js Integration (`javascript_example.js`)

Modern JavaScript example using native fetch API (Node.js 18+).

**Requirements:**
- Node.js 18 or higher

**Usage:**
```bash
export FRIKTIONSKOMPASSET_API_KEY="fk_xxx_xxxx"
node javascript_example.js
```

**Features:**
- ES6+ async/await patterns
- Reusable client class
- Rate limiting handling
- Error handling with detailed messages
- All CRUD operations
- Export data with configurable options

**Best For:**
- Web applications
- Serverless functions
- Node.js backends
- Real-time monitoring

---

### 3. Power BI Integration (`powerbi_query.m`)

Power Query (M language) examples for Power BI Desktop.

**Setup:**
1. Open Power BI Desktop
2. **Get Data** → **Blank Query**
3. **Advanced Editor** → Paste desired query
4. Replace `ApiKey` with your actual API key
5. Click **Done** → **Close & Apply**

**Examples Included:**

| Example | Description | Use Case |
|---------|-------------|----------|
| 1. List Assessments | Get all assessments with metadata | Dashboard overview |
| 2. Assessment Scores | Friction scores for specific assessment | Detailed analysis |
| 3. All Scores | Scores for all completed assessments | Trend analysis |
| 4. Organizational Structure | Hierarchical org chart data | Org visualization |
| 5. Bulk Export | Complete data export for warehouse | Data lake ETL |
| 6. Aggregated Scores | Pre-aggregated scores only | Performance dashboard |
| 7. Parameterized Query | Dynamic assessment selection | Interactive reports |

**Best For:**
- Executive dashboards
- Business intelligence
- Trend analysis
- Compliance reporting

---

## General Setup

### 1. Get Your API Key

1. Log in to Friktionskompasset admin panel
2. Navigate to **Settings → API Keys**
3. Click **Create New API Key**
4. Set permissions (read-only or read/write)
5. Copy the generated key (shown only once!)

**Important:** Store your API key securely. Never commit it to version control.

### 2. Set Environment Variable

**Linux/macOS:**
```bash
export FRIKTIONSKOMPASSET_API_KEY="fk_xxx_xxxx"
```

**Windows (PowerShell):**
```powershell
$env:FRIKTIONSKOMPASSET_API_KEY="fk_xxx_xxxx"
```

**Windows (CMD):**
```cmd
set FRIKTIONSKOMPASSET_API_KEY=fk_xxx_xxxx
```

### 3. Test Your Connection

**Using curl:**
```bash
curl https://friktionskompasset.dk/api/v1/assessments \
     -H "X-API-Key: $FRIKTIONSKOMPASSET_API_KEY"
```

If successful, you should see a JSON response with assessment data.

---

## Common Use Cases

### Data Warehouse Integration

Use the **Python example** with the export endpoint to populate a data warehouse:

```python
# Export all data to JSON
client = FriktionskompassetClient(API_KEY)
export = client.export_data(
    format="json",
    anonymization="pseudonymized",
    include_responses=True,
    include_scores=True,
    include_units=True
)

# Load into your data warehouse
import pandas as pd
df_responses = pd.DataFrame(export['responses'])
df_scores = pd.DataFrame(export['aggregated_scores'])

# Save to database
df_responses.to_sql('friktionskompasset_responses', engine, if_exists='replace')
df_scores.to_sql('friktionskompasset_scores', engine, if_exists='replace')
```

---

### Executive Dashboard in Power BI

1. Use **Example 3** (All Scores) to get comprehensive score data
2. Create relationships between tables:
   - `AssessmentId` → connects scores to assessments
   - `Field` → dimension for slicing
3. Build visualizations:
   - Line chart: Scores over time by Period
   - Bar chart: Current scores by Field
   - Table: Unit-level breakdown
   - Card: Average response rate

---

### Automated Monitoring

Use the **JavaScript example** with a scheduled job:

```javascript
// monitor.js - Run every hour via cron
const client = new FriktionskompassetClient(API_KEY);

async function checkResponseRates() {
  const { data } = await client.listAssessments({ status: 'sent' });

  const lowResponse = data.filter(a => a.response_rate < 50);

  if (lowResponse.length > 0) {
    // Send alert email or Slack notification
    await sendAlert(`${lowResponse.length} assessments have low response rates`);
  }
}

checkResponseRates();
```

**Cron schedule (hourly):**
```
0 * * * * node /path/to/monitor.js
```

---

### Compliance Reporting

Export anonymized data for GDPR compliance:

```python
# Full anonymization for external audit
export = client.export_data(
    format="csv",
    anonymization="full",
    include_responses=True,
    include_scores=True
)

# CSV is automatically downloaded
# Share with auditors without exposing PII
```

---

## Security Best Practices

### 1. Protect API Keys

**DON'T:**
```python
# ❌ Never hardcode API keys
API_KEY = "fk_abc123_real_key"
```

**DO:**
```python
# ✅ Use environment variables
API_KEY = os.getenv("FRIKTIONSKOMPASSET_API_KEY")

# ✅ Use secret management
from azure.keyvault import SecretClient
API_KEY = secret_client.get_secret("friktionskompasset-api-key").value
```

### 2. Use Least Privilege

- Use **read-only** keys for dashboards and reporting
- Only use **write** keys for automation that creates assessments
- Rotate keys quarterly
- Revoke unused keys immediately

### 3. Secure Storage

**Power BI:**
- Use parameters instead of hardcoding
- Enable workspace security
- Use Power BI Gateway for on-premises data

**Web Applications:**
- Store keys in environment variables
- Never expose keys in client-side code
- Use backend proxies for API calls

---

## Rate Limiting

All examples include rate limiting handling. The API allows:

- **100 requests per minute** per API key
- Automatic retry with exponential backoff
- `Retry-After` header indicates wait time

**Tips:**
- Batch operations when possible
- Cache completed assessment results (they don't change)
- Use bulk export for large datasets
- Contact support for higher limits if needed

---

## Error Handling

All examples demonstrate proper error handling:

### Python
```python
try:
    results = client.get_results(assessment_id)
except Exception as e:
    if "NOT_FOUND" in str(e):
        print("Assessment not found")
    elif "FORBIDDEN" in str(e):
        print("Write permission required")
    else:
        print(f"Error: {e}")
```

### JavaScript
```javascript
try {
  const results = await client.getResults(assessmentId);
} catch (error) {
  if (error.message.includes('NOT_FOUND')) {
    console.error('Assessment not found');
  } else {
    console.error('Error:', error.message);
  }
}
```

### Power BI
```m
Source = try Json.Document(
    Web.Contents(BaseUrl & "/assessments", [Headers = [#"X-API-Key" = ApiKey]])
) otherwise [
    data = {},
    error = "API call failed"
]
```

---

## Troubleshooting

### Problem: 401 Unauthorized

**Solution:**
- Verify API key is correct
- Check key is active in admin panel
- Ensure `X-API-Key` header is set correctly

### Problem: 429 Rate Limited

**Solution:**
- Reduce request frequency
- Implement exponential backoff (examples include this)
- Use bulk export instead of many individual requests

### Problem: Empty Results

**Solution:**
- Verify assessment status is "completed"
- Check minimum response threshold is met
- Ensure assessment belongs to your customer

### Problem: Slow Response Times

**Solution:**
- Use pagination (`limit` and `offset`)
- Cache completed assessment data locally
- Use bulk export for large datasets

---

## Additional Resources

- **Full API Documentation:** [../API_DOCUMENTATION.md](../API_DOCUMENTATION.md)
- **Interactive API Docs:** https://friktionskompasset.dk/api/docs
- **OpenAPI Spec:** https://friktionskompasset.dk/static/openapi.yaml
- **Support:** support@friktionskompasset.dk

---

## Contributing

If you've created additional integration examples, please contribute them back:

1. Follow the existing code style
2. Include comprehensive error handling
3. Add usage instructions
4. Document prerequisites
5. Submit via GitHub or email to support

---

## License

These examples are provided as-is for integration purposes. Modify them freely to fit your needs.

---

**Last Updated:** 2025-01-20
**Examples Version:** 1.0
