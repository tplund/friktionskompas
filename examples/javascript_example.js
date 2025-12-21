/**
 * Friktionskompasset API - JavaScript/Node.js Integration Example
 *
 * This example demonstrates how to integrate with the Friktionskompasset API
 * using Node.js and the built-in fetch API.
 *
 * Requirements:
 *   Node.js 18+ (for native fetch support)
 *
 * Usage:
 *   export FRIKTIONSKOMPASSET_API_KEY="fk_xxx_xxxx"
 *   node javascript_example.js
 */

const API_KEY = process.env.FRIKTIONSKOMPASSET_API_KEY;
const BASE_URL = 'https://friktionskompasset.dk/api/v1';

if (!API_KEY) {
  console.error('Error: Set FRIKTIONSKOMPASSET_API_KEY environment variable');
  process.exit(1);
}

/**
 * Friktionskompasset API Client
 */
class FriktionskompassetClient {
  constructor(apiKey, baseUrl = BASE_URL) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
  }

  /**
   * Make HTTP request with error handling and retry logic
   */
  async request(method, endpoint, options = {}) {
    const url = new URL(endpoint, this.baseUrl);

    if (options.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    const fetchOptions = {
      method,
      headers: {
        'X-API-Key': this.apiKey,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    if (options.body) {
      fetchOptions.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, fetchOptions);

      // Handle rate limiting with retry
      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('Retry-After') || '60', 10);
        console.log(`Rate limited. Waiting ${retryAfter} seconds...`);
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        return this.request(method, endpoint, options);
      }

      // Parse error response
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(
          `API Error [${error.code || 'UNKNOWN'}]: ${error.error || response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      if (error.message.startsWith('API Error')) {
        throw error;
      }
      throw new Error(`Request failed: ${error.message}`);
    }
  }

  /**
   * List assessments with optional filtering
   */
  async listAssessments({ status, limit = 50, offset = 0 } = {}) {
    const params = { limit, offset };
    if (status) params.status = status;

    const result = await this.request('GET', '/assessments', { params });
    return { data: result.data, meta: result.meta };
  }

  /**
   * Get detailed information about an assessment
   */
  async getAssessment(assessmentId) {
    const result = await this.request('GET', `/assessments/${assessmentId}`);
    return result.data;
  }

  /**
   * Get friction scores for an assessment
   */
  async getResults(assessmentId, includeUnits = false) {
    const params = { include_units: includeUnits };
    const result = await this.request('GET', `/assessments/${assessmentId}/results`, { params });
    return result.data;
  }

  /**
   * Create a new assessment (requires write permission)
   */
  async createAssessment(data) {
    const result = await this.request('POST', '/assessments', { body: data });
    return result.data;
  }

  /**
   * Get organizational structure
   */
  async getUnits({ flat = false, parentId } = {}) {
    const params = {};
    if (flat) params.flat = 'true';
    if (parentId) params.parent_id = parentId;

    const result = await this.request('GET', '/units', { params });
    return { data: result.data, meta: result.meta };
  }

  /**
   * Export bulk data
   */
  async exportData(options = {}) {
    const {
      format = 'json',
      anonymization = 'pseudonymized',
      assessmentId,
      includeResponses = true,
      includeScores = true,
      includeQuestions = true,
      includeUnits = false,
    } = options;

    const params = {
      format,
      anonymization,
      include_responses: includeResponses,
      include_scores: includeScores,
      include_questions: includeQuestions,
      include_units: includeUnits,
    };

    if (assessmentId) params.assessment_id = assessmentId;

    const result = await this.request('GET', '/export', { params });
    return result.data;
  }
}

/**
 * Example 1: List all completed assessments
 */
async function example1ListAssessments() {
  console.log('\n=== Example 1: List Completed Assessments ===');

  const client = new FriktionskompassetClient(API_KEY);
  const { data: assessments, meta } = await client.listAssessments({
    status: 'completed',
    limit: 10,
  });

  console.log(`Found ${meta.total} completed assessments (showing ${assessments.length})`);
  console.log();

  assessments.forEach(assessment => {
    console.log(`ID: ${assessment.id}`);
    console.log(`Name: ${assessment.name}`);
    console.log(`Period: ${assessment.period}`);
    console.log(`Unit: ${assessment.unit.name}`);
    console.log(`Response Rate: ${assessment.response_rate}%`);
    console.log('-'.repeat(60));
  });
}

/**
 * Example 2: Get friction scores for an assessment
 */
async function example2GetScores() {
  console.log('\n=== Example 2: Get Friction Scores ===');

  const client = new FriktionskompassetClient(API_KEY);

  // Get first completed assessment
  const { data: assessments } = await client.listAssessments({
    status: 'completed',
    limit: 1,
  });

  if (assessments.length === 0) {
    console.log('No completed assessments found');
    return;
  }

  const assessmentId = assessments[0].id;
  const results = await client.getResults(assessmentId, true);

  console.log(`Assessment: ${results.assessment.name}`);
  console.log(`Unit: ${results.assessment.unit_name}`);
  console.log(`Responses: ${results.response_count}`);
  console.log();

  // Display friction scores
  console.log('Friction Scores:');
  console.log('-'.repeat(60));

  const fields = ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'];
  fields.forEach(field => {
    const scoreData = results.scores[field];
    if (scoreData.score !== null) {
      console.log(
        `${field.padEnd(10)} | Score: ${scoreData.score.toFixed(2)} | ` +
        `Percent: ${scoreData.percent.toFixed(1)}% | ` +
        `Severity: ${scoreData.severity}`
      );
    } else {
      console.log(`${field.padEnd(10)} | No data`);
    }
  });

  // Show unit breakdown if available
  if (results.unit_breakdown && results.unit_breakdown.length > 0) {
    console.log('\nUnit Breakdown:');
    results.unit_breakdown.forEach(unit => {
      console.log(
        `  - ${unit.name}: BESVÆR ${unit.besvær_score?.toFixed(2) || 'N/A'} ` +
        `(${unit.tokens_used}/${unit.tokens_sent} responses)`
      );
    });
  }
}

/**
 * Example 3: Explore organizational structure
 */
async function example3OrganizationalStructure() {
  console.log('\n=== Example 3: Organizational Structure ===');

  const client = new FriktionskompassetClient(API_KEY);
  const { data: units, meta } = await client.getUnits({ flat: false });

  function printUnit(unit, indent = 0) {
    const prefix = '  '.repeat(indent);
    const leader = unit.leader ? ` (Leader: ${unit.leader.name})` : '';
    console.log(`${prefix}- ${unit.name}${leader}`);
    console.log(`${prefix}  Employees: ${unit.employee_count}, Children: ${unit.child_count}`);

    if (unit.children) {
      unit.children.forEach(child => printUnit(child, indent + 1));
    }
  }

  console.log(`Total units: ${meta.total}`);
  console.log(`Mode: ${meta.mode}`);
  console.log();

  units.forEach(unit => printUnit(unit));
}

/**
 * Example 4: Create a new assessment (requires write permission)
 */
async function example4CreateAssessment() {
  console.log('\n=== Example 4: Create Assessment ===');

  const client = new FriktionskompassetClient(API_KEY);

  // Get first unit to use as target
  const { data: units } = await client.getUnits({ flat: true });

  if (units.length === 0) {
    console.log('No organizational units found');
    return;
  }

  const targetUnit = units[0];

  try {
    const assessment = await client.createAssessment({
      name: `API Test Assessment ${new Date().toISOString()}`,
      period: `${new Date().getFullYear()} Q1`,
      target_unit_id: targetUnit.id,
      include_leader_assessment: true,
      min_responses: 5,
    });

    console.log('Assessment created successfully!');
    console.log(`ID: ${assessment.id}`);
    console.log(`Name: ${assessment.name}`);
    console.log(`Status: ${assessment.status}`);
  } catch (error) {
    if (error.message.includes('FORBIDDEN')) {
      console.log('Error: This API key does not have write permission');
    } else {
      console.log(`Error: ${error.message}`);
    }
  }
}

/**
 * Example 5: Export data for analytics
 */
async function example5ExportData() {
  console.log('\n=== Example 5: Export Data ===');

  const client = new FriktionskompassetClient(API_KEY);

  // Export all data with pseudonymization
  const exportData = await client.exportData({
    format: 'json',
    anonymization: 'pseudonymized',
    includeResponses: true,
    includeScores: true,
    includeQuestions: true,
    includeUnits: true,
  });

  console.log(`Export Date: ${exportData.export_date}`);
  console.log(`Anonymization: ${exportData.anonymization_level}`);
  console.log();

  if (exportData.responses) {
    console.log(`Total Responses: ${exportData.responses.length}`);
  }

  if (exportData.aggregated_scores) {
    console.log(`Aggregated Scores: ${exportData.aggregated_scores.length}`);
  }

  if (exportData.questions) {
    console.log(`Questions: ${exportData.questions.length}`);
  }

  if (exportData.units) {
    console.log(`Organizational Units: ${exportData.units.length}`);
  }

  // Optional: Save to file
  const fs = await import('fs/promises');
  await fs.writeFile('export_data.json', JSON.stringify(exportData, null, 2));
  console.log('\nExport saved to: export_data.json');
}

/**
 * Example 6: Aggregate statistics across all assessments
 */
async function example6AggregateStatistics() {
  console.log('\n=== Example 6: Aggregate Statistics ===');

  const client = new FriktionskompassetClient(API_KEY);

  const { data: assessments } = await client.listAssessments({
    status: 'completed',
    limit: 100,
  });

  if (assessments.length === 0) {
    console.log('No completed assessments found');
    return;
  }

  // Calculate average response rate
  const totalResponseRate = assessments.reduce((sum, a) => sum + a.response_rate, 0);
  const avgResponseRate = totalResponseRate / assessments.length;

  console.log(`Total Assessments: ${assessments.length}`);
  console.log(`Average Response Rate: ${avgResponseRate.toFixed(1)}%`);
  console.log();

  // Count by status
  const statusCounts = {};
  assessments.forEach(a => {
    statusCounts[a.status] = (statusCounts[a.status] || 0) + 1;
  });

  console.log('Assessments by Status:');
  Object.entries(statusCounts).forEach(([status, count]) => {
    console.log(`  ${status}: ${count}`);
  });

  // Top 5 assessments by response rate
  const topAssessments = [...assessments]
    .sort((a, b) => b.response_rate - a.response_rate)
    .slice(0, 5);

  console.log('\nTop 5 Assessments by Response Rate:');
  topAssessments.forEach((a, i) => {
    console.log(`  ${i + 1}. ${a.name} - ${a.response_rate}%`);
  });
}

/**
 * Example 7: Monitor response rates for active assessments
 */
async function example7Monitoring() {
  console.log('\n=== Example 7: Monitor Response Rates ===');

  const client = new FriktionskompassetClient(API_KEY);
  const { data: assessments } = await client.listAssessments({
    status: 'sent',
    limit: 100,
  });

  if (assessments.length === 0) {
    console.log('No active assessments found');
    return;
  }

  console.log(`Monitoring ${assessments.length} active assessments`);
  console.log();

  // Sort by response rate
  const sortedAssessments = [...assessments].sort((a, b) => a.response_rate - b.response_rate);

  console.log(
    'Name'.padEnd(40) +
    'Unit'.padEnd(30) +
    'Response Rate'.padStart(15)
  );
  console.log('-'.repeat(90));

  sortedAssessments.forEach(assessment => {
    const name = assessment.name.substring(0, 38);
    const unit = assessment.unit.name.substring(0, 28);
    const rate = assessment.response_rate;
    const tokens = `${assessment.tokens_used}/${assessment.tokens_sent}`;

    // Color code by rate
    let indicator;
    if (rate < 50) {
      indicator = '⚠️ LOW';
    } else if (rate < 80) {
      indicator = '⚡ MEDIUM';
    } else {
      indicator = '✓ GOOD';
    }

    console.log(
      name.padEnd(40) +
      unit.padEnd(30) +
      `${rate.toFixed(1)}%`.padStart(7) +
      ` (${tokens.padStart(7)}) ${indicator}`
    );
  });
}

/**
 * Run all examples
 */
async function main() {
  console.log('='.repeat(80));
  console.log('Friktionskompasset API - JavaScript Examples');
  console.log('='.repeat(80));

  const examples = [
    { name: 'List Assessments', fn: example1ListAssessments },
    { name: 'Get Scores', fn: example2GetScores },
    { name: 'Organizational Structure', fn: example3OrganizationalStructure },
    { name: 'Create Assessment', fn: example4CreateAssessment },
    { name: 'Export Data', fn: example5ExportData },
    { name: 'Aggregate Statistics', fn: example6AggregateStatistics },
    { name: 'Monitor Response Rates', fn: example7Monitoring },
  ];

  console.log('\nAvailable examples:');
  examples.forEach((example, i) => {
    console.log(`  ${i + 1}. ${example.name}`);
  });

  console.log('\nRunning all examples...');

  for (const example of examples) {
    try {
      await example.fn();
    } catch (error) {
      console.log(`\nError in ${example.name}: ${error.message}`);
    }

    // Rate limiting courtesy
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  console.log('\n' + '='.repeat(80));
  console.log('Examples completed!');
  console.log('='.repeat(80));
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { FriktionskompassetClient };
