#!/usr/bin/env python3
"""
MCP Server for Friktionskompasset
Giver Claude Code direkte adgang til at inspicere og manipulere data
"""

import json
import sys
import sqlite3
from typing import Any
import os

# Database path
DB_PATH = "friktionskompas_v3.db"

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def handle_request(request: dict) -> dict:
    """Handle incoming MCP request"""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "friktionskompas-mcp",
                    "version": "1.0.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "db_status",
                        "description": "Get database status: counts of units, assessments, responses, customers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "query_db",
                        "description": "Run a SELECT query on the database (read-only)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sql": {
                                    "type": "string",
                                    "description": "SQL SELECT query to run"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Max rows to return (default 50)"
                                }
                            },
                            "required": ["sql"]
                        }
                    },
                    {
                        "name": "list_tables",
                        "description": "List all tables in the database",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    },
                    {
                        "name": "table_schema",
                        "description": "Get schema for a specific table",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "table": {
                                    "type": "string",
                                    "description": "Table name"
                                }
                            },
                            "required": ["table"]
                        }
                    },
                    {
                        "name": "assessment_details",
                        "description": "Get details for a specific assessment including response counts",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "assessment_id": {
                                    "type": "string",
                                    "description": "Assessment ID"
                                }
                            },
                            "required": ["assessment_id"]
                        }
                    },
                    {
                        "name": "profil_questions",
                        "description": "List all profil questions grouped by type",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "question_type": {
                                    "type": "string",
                                    "description": "Filter by type: sensitivity, capacity, bandwidth, screening, baseline"
                                }
                            },
                            "required": []
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        try:
            result = call_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, ensure_ascii=False, default=str)
                        }
                    ]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {str(e)}"
                        }
                    ],
                    "isError": True
                }
            }

    elif method == "notifications/initialized":
        # No response needed for notifications
        return None

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


def call_tool(name: str, args: dict) -> Any:
    """Execute a tool and return result"""
    conn = get_db()

    try:
        if name == "db_status":
            result = {
                "database": DB_PATH,
                "exists": os.path.exists(DB_PATH),
                "size_bytes": os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
            }

            # Count tables
            for table in ["organizational_units", "assessments", "responses", "customers", "users", "profil_sessions", "profil_questions"]:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    result[table] = count
                except Exception:
                    result[table] = "table not found"

            # Check respondent_name
            try:
                with_name = conn.execute("SELECT COUNT(*) FROM responses WHERE respondent_name IS NOT NULL").fetchone()[0]
                result["responses_with_name"] = with_name
            except Exception:
                pass  # Column may not exist in older schema

            return result

        elif name == "query_db":
            sql = args.get("sql", "")
            limit = args.get("limit", 50)

            # Security: only allow SELECT
            if not sql.strip().upper().startswith("SELECT"):
                return {"error": "Only SELECT queries allowed"}

            # Add limit if not present
            if "LIMIT" not in sql.upper():
                sql = f"{sql} LIMIT {limit}"

            rows = conn.execute(sql).fetchall()
            return {
                "row_count": len(rows),
                "rows": [dict(row) for row in rows]
            }

        elif name == "list_tables":
            tables = conn.execute("""
                SELECT name, type FROM sqlite_master
                WHERE type IN ('table', 'index')
                ORDER BY type, name
            """).fetchall()
            return {"tables": [dict(t) for t in tables]}

        elif name == "table_schema":
            table = args.get("table", "")
            # SQL injection protection: Validér tabelnavn (tilføjet i go-live audit 2025-12-18)
            import re
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
                return {"error": "Invalid table name"}
            schema = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return {
                "table": table,
                "columns": [
                    {
                        "name": col[1],
                        "type": col[2],
                        "notnull": bool(col[3]),
                        "default": col[4],
                        "pk": bool(col[5])
                    }
                    for col in schema
                ]
            }

        elif name == "assessment_details":
            assessment_id = args.get("assessment_id", "")

            assessment = conn.execute("""
                SELECT c.*, ou.name as unit_name, ou.full_path
                FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE c.id = ?
            """, [assessment_id]).fetchone()

            if not assessment:
                return {"error": "Assessment not found"}

            # Response stats
            resp_stats = conn.execute("""
                SELECT
                    respondent_type,
                    COUNT(DISTINCT respondent_name) as unique_respondents,
                    COUNT(*) as total_responses
                FROM responses
                WHERE assessment_id = ?
                GROUP BY respondent_type
            """, [assessment_id]).fetchall()

            return {
                "assessment": dict(assessment),
                "response_stats": [dict(r) for r in resp_stats]
            }

        elif name == "profil_questions":
            question_type = args.get("question_type")

            if question_type:
                questions = conn.execute("""
                    SELECT field, layer, text_da, question_type, reverse_scored, sequence
                    FROM profil_questions
                    WHERE question_type = ?
                    ORDER BY sequence
                """, [question_type]).fetchall()
            else:
                questions = conn.execute("""
                    SELECT field, layer, text_da, question_type, reverse_scored, sequence
                    FROM profil_questions
                    ORDER BY question_type, sequence
                """).fetchall()

            return {
                "count": len(questions),
                "questions": [dict(q) for q in questions]
            }

        else:
            return {"error": f"Unknown tool: {name}"}

    finally:
        conn.close()


def main():
    """Main loop - read JSON-RPC requests from stdin, write responses to stdout"""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)
            response = handle_request(request)

            if response:  # Some notifications don't need responses
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
