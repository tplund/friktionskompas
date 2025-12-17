"""
Refactor: Replace 'campaign' with 'assessment' in all Python and HTML files

This script does intelligent replacement:
- campaign -> assessment
- Campaign -> Assessment
- campaigns -> assessments
- Campaigns -> Assessments
- campaign_id -> assessment_id
- camp- (ID prefix) -> assess-

It preserves:
- UI text that should remain as "maling" (handled by translations)
- Comments explaining the change
"""
import os
import re
from pathlib import Path

# Files to process
PYTHON_FILES = [
    'db_hierarchical.py',
    'admin_app.py',
    'analysis.py',
    'survey_app.py',
    'scheduler.py',
    'mailjet_integration.py',
    'cache.py',
    'seed_herning_testdata.py',
    'seed_testdata.py',
    'generate_test_responses.py',
    'generate_varied_test_data.py',
    'demo_data_hierarchical.py',
    'setup_municipal_data.py',
    'translations.py',
    'mcp_server.py',
    'export_local_data.py',
    'import_local_data.py',
    'check_campaign_stats.py',
    'check_data.py',
    'create_test_campaign.py',
    'test_phase1.py',
    'run_migration.py',
    'tests/conftest.py',
    'tests/test_routes.py',
    'tests/test_database.py',
    'tests/test_role_data_visibility.py',
    'tests/test_scheduler.py',
    'tests/test_integration.py',
    'tests/test_ui.py',
    'tests/test_integration_data.py',
]

HTML_FILES = [
    'templates/manager_dashboard.html',
    'templates/admin/analyser.html',
    'templates/admin/base.html',
    'templates/admin/backup.html',
    'templates/admin/campaigns_overview.html',
    'templates/admin/campaign_pdf.html',
    'templates/admin/dev_tools.html',
    'templates/admin/campaign_detailed.html',
    'templates/admin/email_templates.html',
    'templates/admin/home.html',
    'templates/admin/layout.html',
    'templates/admin/new_campaign.html',
    'templates/admin/noegletal.html',
    'templates/admin/org_dashboard.html',
    'templates/admin/scheduled_campaigns.html',
    'templates/admin/trend.html',
    'templates/admin/view_campaign.html',
    'templates/admin/view_org.html',
    'templates/admin/view_unit.html',
]

def replace_in_file(filepath, dry_run=False):
    """Replace campaign with assessment in a file"""
    if not os.path.exists(filepath):
        print(f"  SKIP: {filepath} (not found)")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Replacements (order matters - more specific first)
    replacements = [
        # ID prefixes
        (r'"camp-', '"assess-'),
        (r"'camp-", "'assess-"),
        (r'f"camp-', 'f"assess-'),
        (r"f'camp-", "f'assess-"),

        # Table/column names (SQL)
        ('campaigns', 'assessments'),
        ('campaign_id', 'assessment_id'),
        ('campaign_modes', 'assessment_modes'),

        # Variable names
        ('campaign_stats', 'assessment_stats'),
        ('campaign_info', 'assessment_info'),
        ('campaign_data', 'assessment_data'),
        ('campaign_name', 'assessment_name'),
        ('campaign_period', 'assessment_period'),
        ('campaign_overview', 'assessment_overview'),
        ('campaign_list', 'assessment_list'),
        ('for_campaign', 'for_assessment'),
        ('get_campaign', 'get_assessment'),
        ('create_campaign', 'create_assessment'),
        ('new_campaign', 'new_assessment'),
        ('view_campaign', 'view_assessment'),
        ('send_campaign', 'send_assessment'),
        ('scheduled_campaign', 'scheduled_assessment'),
        ('active_campaign', 'active_assessment'),
        ('direct_campaign', 'direct_assessment'),
        ('campaign_count', 'assessment_count'),
        ('with_campaign', 'with_assessment'),
        ('campaign_detailed', 'assessment_detailed'),

        # Function names
        ('generate_tokens_for_campaign', 'generate_tokens_for_assessment'),
        ('tokens_for_campaign', 'tokens_for_assessment'),
        ('campaign_with_modes', 'assessment_with_modes'),

        # Route names
        ('/campaign/', '/assessment/'),
        ('/campaigns', '/assessments'),

        # Generic (catch remaining)
        ('campaign', 'assessment'),
        ('Campaign', 'Assessment'),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    # Count changes
    changes = sum(1 for a, b in zip(original, content) if a != b)

    if content != original:
        if dry_run:
            print(f"  WOULD CHANGE: {filepath}")
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  CHANGED: {filepath}")
        return 1
    else:
        print(f"  NO CHANGE: {filepath}")
        return 0


def rename_files():
    """Rename files that have 'campaign' in the name"""
    renames = [
        ('templates/admin/campaigns_overview.html', 'templates/admin/assessments_overview.html'),
        ('templates/admin/campaign_pdf.html', 'templates/admin/assessment_pdf.html'),
        ('templates/admin/campaign_detailed.html', 'templates/admin/assessment_detailed.html'),
        ('templates/admin/new_campaign.html', 'templates/admin/new_assessment.html'),
        ('templates/admin/scheduled_campaigns.html', 'templates/admin/scheduled_assessments.html'),
        ('templates/admin/view_campaign.html', 'templates/admin/view_assessment.html'),
    ]

    print("\nRenaming files:")
    for old_name, new_name in renames:
        if os.path.exists(old_name):
            os.rename(old_name, new_name)
            print(f"  {old_name} -> {new_name}")
        else:
            print(f"  SKIP: {old_name} (not found)")


def main():
    import sys

    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("DRY RUN - no files will be modified\n")

    print("=" * 60)
    print("Refactoring: campaign -> assessment")
    print("=" * 60)

    # Process Python files
    print("\nProcessing Python files:")
    py_changed = 0
    for filepath in PYTHON_FILES:
        py_changed += replace_in_file(filepath, dry_run)

    # Process HTML files
    print("\nProcessing HTML files:")
    html_changed = 0
    for filepath in HTML_FILES:
        html_changed += replace_in_file(filepath, dry_run)

    # Rename files
    if not dry_run:
        rename_files()

    print(f"\nSummary:")
    print(f"  Python files changed: {py_changed}")
    print(f"  HTML files changed: {html_changed}")

    if dry_run:
        print("\nRun without --dry-run to apply changes")


if __name__ == "__main__":
    main()
