"""
Friktionskompasset API - Python Integration Example

This example demonstrates how to integrate with the Friktionskompasset API
using Python and the requests library.

Installation:
    pip install requests pandas

Usage:
    export FRIKTIONSKOMPASSET_API_KEY="fk_xxx_xxxx"
    python python_example.py
"""

import os
import sys
import time
from datetime import datetime
import requests
import json

# Configuration
API_KEY = os.getenv("FRIKTIONSKOMPASSET_API_KEY")
BASE_URL = "https://friktionskompasset.dk/api/v1"

if not API_KEY:
    print("Error: Set FRIKTIONSKOMPASSET_API_KEY environment variable")
    sys.exit(1)

# HTTP headers for all requests
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}


class FriktionskompassetClient:
    """Client for Friktionskompasset API."""

    def __init__(self, api_key, base_url=BASE_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    def _request(self, method, endpoint, params=None, json_data=None):
        """Make HTTP request with error handling."""
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=30
            )

            # Handle rate limiting with retry
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self._request(method, endpoint, params, json_data)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_data = e.response.json() if e.response.content else {}
            error_msg = error_data.get('error', str(e))
            error_code = error_data.get('code', 'UNKNOWN')
            raise Exception(f"API Error [{error_code}]: {error_msg}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")

    def list_assessments(self, status=None, limit=50, offset=0):
        """List assessments with optional filtering."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        result = self._request("GET", "/assessments", params=params)
        return result['data'], result['meta']

    def get_assessment(self, assessment_id):
        """Get detailed information about an assessment."""
        result = self._request("GET", f"/assessments/{assessment_id}")
        return result['data']

    def get_results(self, assessment_id, include_units=False):
        """Get friction scores for an assessment."""
        params = {"include_units": "true" if include_units else "false"}
        result = self._request("GET", f"/assessments/{assessment_id}/results", params=params)
        return result['data']

    def create_assessment(self, name, period, target_unit_id, **kwargs):
        """Create a new assessment (requires write permission)."""
        data = {
            "name": name,
            "period": period,
            "target_unit_id": target_unit_id,
            **kwargs
        }
        result = self._request("POST", "/assessments", json_data=data)
        return result['data']

    def get_units(self, flat=False, parent_id=None):
        """Get organizational structure."""
        params = {}
        if flat:
            params["flat"] = "true"
        if parent_id:
            params["parent_id"] = parent_id

        result = self._request("GET", "/units", params=params)
        return result['data'], result['meta']

    def export_data(self, format="json", anonymization="pseudonymized", **kwargs):
        """Export bulk data."""
        params = {
            "format": format,
            "anonymization": anonymization,
            **{k: str(v).lower() for k, v in kwargs.items()}
        }
        result = self._request("GET", "/export", params=params)
        return result['data']


def example_1_list_assessments():
    """Example 1: List all completed assessments."""
    print("\n=== Example 1: List Completed Assessments ===")

    client = FriktionskompassetClient(API_KEY)
    assessments, meta = client.list_assessments(status="completed", limit=10)

    print(f"Found {meta['total']} completed assessments (showing {len(assessments)})")
    print()

    for assessment in assessments:
        print(f"ID: {assessment['id']}")
        print(f"Name: {assessment['name']}")
        print(f"Period: {assessment['period']}")
        print(f"Unit: {assessment['unit']['name']}")
        print(f"Response Rate: {assessment['response_rate']}%")
        print("-" * 60)


def example_2_get_scores():
    """Example 2: Get friction scores for an assessment."""
    print("\n=== Example 2: Get Friction Scores ===")

    client = FriktionskompassetClient(API_KEY)

    # Get first completed assessment
    assessments, _ = client.list_assessments(status="completed", limit=1)
    if not assessments:
        print("No completed assessments found")
        return

    assessment_id = assessments[0]['id']
    results = client.get_results(assessment_id, include_units=True)

    print(f"Assessment: {results['assessment']['name']}")
    print(f"Unit: {results['assessment']['unit_name']}")
    print(f"Responses: {results['response_count']}")
    print()

    # Display friction scores
    print("Friction Scores:")
    print("-" * 60)
    for field in ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']:
        score_data = results['scores'][field]
        if score_data['score']:
            print(f"{field:10} | Score: {score_data['score']:.2f} | "
                  f"Percent: {score_data['percent']:5.1f}% | "
                  f"Severity: {score_data['severity']}")
        else:
            print(f"{field:10} | No data")


def example_3_organizational_structure():
    """Example 3: Explore organizational structure."""
    print("\n=== Example 3: Organizational Structure ===")

    client = FriktionskompassetClient(API_KEY)
    units, meta = client.get_units(flat=False)

    def print_unit(unit, indent=0):
        """Recursively print unit hierarchy."""
        prefix = "  " * indent
        leader = f" (Leader: {unit['leader']['name']})" if unit['leader'] else ""
        print(f"{prefix}- {unit['name']}{leader}")
        print(f"{prefix}  Employees: {unit['employee_count']}, Children: {unit['child_count']}")

        for child in unit.get('children', []):
            print_unit(child, indent + 1)

    print(f"Total units: {meta['total']}")
    print(f"Mode: {meta['mode']}")
    print()

    for unit in units:
        print_unit(unit)


def example_4_create_assessment():
    """Example 4: Create a new assessment (requires write permission)."""
    print("\n=== Example 4: Create Assessment ===")

    client = FriktionskompassetClient(API_KEY)

    # Get first unit to use as target
    units, _ = client.get_units(flat=True)
    if not units:
        print("No organizational units found")
        return

    target_unit = units[0]

    try:
        assessment = client.create_assessment(
            name=f"API Test Assessment {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            period=f"{datetime.now().year} Q1",
            target_unit_id=target_unit['id'],
            include_leader_assessment=True,
            min_responses=5
        )

        print("Assessment created successfully!")
        print(f"ID: {assessment['id']}")
        print(f"Name: {assessment['name']}")
        print(f"Status: {assessment['status']}")

    except Exception as e:
        if "FORBIDDEN" in str(e):
            print("Error: This API key does not have write permission")
        else:
            print(f"Error: {e}")


def example_5_export_data():
    """Example 5: Export data for analytics."""
    print("\n=== Example 5: Export Data ===")

    client = FriktionskompassetClient(API_KEY)

    # Export all data with pseudonymization
    export = client.export_data(
        format="json",
        anonymization="pseudonymized",
        include_responses=True,
        include_scores=True,
        include_questions=True,
        include_units=True
    )

    print(f"Export Date: {export['export_date']}")
    print(f"Anonymization: {export['anonymization_level']}")
    print()

    if 'responses' in export:
        print(f"Total Responses: {len(export['responses'])}")

    if 'aggregated_scores' in export:
        print(f"Aggregated Scores: {len(export['aggregated_scores'])}")

    if 'questions' in export:
        print(f"Questions: {len(export['questions'])}")

    if 'units' in export:
        print(f"Organizational Units: {len(export['units'])}")

    # Optional: Save to file
    with open('export_data.json', 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    print("\nExport saved to: export_data.json")


def example_6_pandas_integration():
    """Example 6: Convert to pandas DataFrames for analysis."""
    print("\n=== Example 6: Pandas Integration ===")

    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas not installed. Run: pip install pandas")
        return

    client = FriktionskompassetClient(API_KEY)

    # Export data
    export = client.export_data(
        format="json",
        include_responses=True,
        include_scores=True
    )

    # Convert to DataFrames
    if 'responses' in export:
        df_responses = pd.DataFrame(export['responses'])
        print("Responses DataFrame:")
        print(df_responses.head())
        print()

        # Analyze response distribution by field
        if 'question_id' in df_responses.columns:
            print("Responses by Question:")
            print(df_responses['question_id'].value_counts().sort_index())
            print()

    if 'aggregated_scores' in export:
        df_scores = pd.DataFrame(export['aggregated_scores'])
        print("Scores DataFrame:")
        print(df_scores.head())
        print()

        # Average scores by field
        if 'field' in df_scores.columns:
            print("Average Scores by Field:")
            print(df_scores.groupby('field')['score'].mean().sort_values(ascending=False))


def example_7_monitoring():
    """Example 7: Monitor response rates."""
    print("\n=== Example 7: Monitor Response Rates ===")

    client = FriktionskompassetClient(API_KEY)
    assessments, _ = client.list_assessments(status="sent", limit=100)

    if not assessments:
        print("No active assessments found")
        return

    print(f"Monitoring {len(assessments)} active assessments")
    print()

    # Sort by response rate
    sorted_assessments = sorted(assessments, key=lambda x: x['response_rate'])

    print(f"{'Name':<40} {'Unit':<30} {'Response Rate':>15}")
    print("-" * 90)

    for assessment in sorted_assessments:
        name = assessment['name'][:38]
        unit = assessment['unit']['name'][:28]
        rate = assessment['response_rate']
        tokens = f"{assessment['tokens_used']}/{assessment['tokens_sent']}"

        # Color code by rate
        if rate < 50:
            indicator = "⚠️ LOW"
        elif rate < 80:
            indicator = "⚡ MEDIUM"
        else:
            indicator = "✓ GOOD"

        print(f"{name:<40} {unit:<30} {rate:>6.1f}% ({tokens:>7}) {indicator}")


def main():
    """Run all examples."""
    print("=" * 80)
    print("Friktionskompasset API - Python Examples")
    print("=" * 80)

    examples = [
        ("List Assessments", example_1_list_assessments),
        ("Get Scores", example_2_get_scores),
        ("Organizational Structure", example_3_organizational_structure),
        ("Create Assessment", example_4_create_assessment),
        ("Export Data", example_5_export_data),
        ("Pandas Integration", example_6_pandas_integration),
        ("Monitor Response Rates", example_7_monitoring),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")

    print("\nRunning all examples...")

    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\nError in {name}: {str(e)}")

        time.sleep(0.5)  # Rate limiting courtesy

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
