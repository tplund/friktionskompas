/**
 * Friktionskompasset API - Power BI Integration Examples
 *
 * This file contains Power Query (M) examples for connecting Power BI
 * to the Friktionskompasset API.
 *
 * Setup Instructions:
 * 1. Open Power BI Desktop
 * 2. Get Data → Blank Query
 * 3. Advanced Editor → Paste one of the queries below
 * 4. Replace API_KEY with your actual API key
 * 5. Click Done → Close & Apply
 *
 * Note: Store your API key securely using Power BI parameters or
 * environment variables in production deployments.
 */

// =============================================================================
// EXAMPLE 1: List All Assessments
// =============================================================================
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    // Fetch assessments
    Source = Json.Document(
        Web.Contents(
            BaseUrl & "/assessments",
            [
                Headers = [
                    #"X-API-Key" = ApiKey,
                    #"Content-Type" = "application/json"
                ],
                Query = [
                    limit = "100",
                    offset = "0"
                ]
            ]
        )
    ),

    // Extract data array
    Data = Source[data],

    // Convert to table
    ToTable = Table.FromList(Data, Splitter.SplitByNothing(), null, null, ExtraValues.Error),

    // Expand all columns
    ExpandedColumns = Table.ExpandRecordColumn(
        ToTable,
        "Column1",
        {
            "id", "name", "period", "status", "type",
            "tokens_sent", "tokens_used", "response_rate",
            "include_leader", "created_at", "sent_at", "scheduled_at",
            "unit"
        }
    ),

    // Expand unit nested object
    ExpandedUnit = Table.ExpandRecordColumn(
        ExpandedColumns,
        "unit",
        {"id", "name", "path"},
        {"unit_id", "unit_name", "unit_path"}
    ),

    // Type conversions for optimal performance
    TypedTable = Table.TransformColumnTypes(
        ExpandedUnit,
        {
            {"id", type text},
            {"name", type text},
            {"period", type text},
            {"status", type text},
            {"type", type text},
            {"tokens_sent", Int64.Type},
            {"tokens_used", Int64.Type},
            {"response_rate", type number},
            {"include_leader", type logical},
            {"created_at", type datetime},
            {"sent_at", type datetime},
            {"scheduled_at", type datetime},
            {"unit_id", type text},
            {"unit_name", type text},
            {"unit_path", type text}
        }
    )
in
    TypedTable


// =============================================================================
// EXAMPLE 2: Get Friction Scores for a Specific Assessment
// =============================================================================
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
    BaseUrl = "https://friktionskompasset.dk/api/v1",
    AssessmentId = "assess-abc123",  // Replace with actual assessment ID

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

    // Convert scores to table with proper structure
    ScoresList = {
        [Field = "TRYGHED", Score = Scores[TRYGHED][score], Percent = Scores[TRYGHED][percent], Severity = Scores[TRYGHED][severity], Responses = Scores[TRYGHED][response_count]],
        [Field = "MENING", Score = Scores[MENING][score], Percent = Scores[MENING][percent], Severity = Scores[MENING][severity], Responses = Scores[MENING][response_count]],
        [Field = "KAN", Score = Scores[KAN][score], Percent = Scores[KAN][percent], Severity = Scores[KAN][severity], Responses = Scores[KAN][response_count]],
        [Field = "BESVÆR", Score = Scores[BESVÆR][score], Percent = Scores[BESVÆR][percent], Severity = Scores[BESVÆR][severity], Responses = Scores[BESVÆR][response_count]]
    },

    ToTable = Table.FromRecords(ScoresList),

    // Add assessment metadata
    AddAssessmentId = Table.AddColumn(ToTable, "AssessmentId", each Data[assessment][id]),
    AddAssessmentName = Table.AddColumn(AddAssessmentId, "AssessmentName", each Data[assessment][name]),
    AddPeriod = Table.AddColumn(AddAssessmentName, "Period", each Data[assessment][period]),
    AddUnitName = Table.AddColumn(AddPeriod, "UnitName", each Data[assessment][unit_name]),

    // Type conversions
    TypedTable = Table.TransformColumnTypes(
        AddUnitName,
        {
            {"Field", type text},
            {"Score", type number},
            {"Percent", type number},
            {"Severity", type text},
            {"Responses", Int64.Type},
            {"AssessmentId", type text},
            {"AssessmentName", type text},
            {"Period", type text},
            {"UnitName", type text}
        }
    )
in
    TypedTable


// =============================================================================
// EXAMPLE 3: Get All Scores for All Completed Assessments (Advanced)
// =============================================================================
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    // Function to get scores for a single assessment
    GetAssessmentScores = (assessmentId as text) =>
        let
            Source = Json.Document(
                Web.Contents(
                    BaseUrl & "/assessments/" & assessmentId & "/results",
                    [Headers = [#"X-API-Key" = ApiKey]]
                )
            ),
            Data = Source[data],
            Scores = Data[scores],

            ScoresList = {
                [Field = "TRYGHED", Score = Scores[TRYGHED][score], Percent = Scores[TRYGHED][percent], Severity = Scores[TRYGHED][severity]],
                [Field = "MENING", Score = Scores[MENING][score], Percent = Scores[MENING][percent], Severity = Scores[MENING][severity]],
                [Field = "KAN", Score = Scores[KAN][score], Percent = Scores[KAN][percent], Severity = Scores[KAN][severity]],
                [Field = "BESVÆR", Score = Scores[BESVÆR][score], Percent = Scores[BESVÆR][percent], Severity = Scores[BESVÆR][severity]]
            },

            ToTable = Table.FromRecords(ScoresList),
            AddMetadata = Table.AddColumn(
                Table.AddColumn(
                    Table.AddColumn(ToTable, "AssessmentId", each Data[assessment][id]),
                    "AssessmentName", each Data[assessment][name]
                ),
                "Period", each Data[assessment][period]
            )
        in
            AddMetadata,

    // Get list of completed assessments
    AssessmentsList = Json.Document(
        Web.Contents(
            BaseUrl & "/assessments",
            [
                Headers = [#"X-API-Key" = ApiKey],
                Query = [status = "completed", limit = "100"]
            ]
        )
    )[data],

    AssessmentsTable = Table.FromList(AssessmentsList, Splitter.SplitByNothing()),
    ExpandAssessments = Table.ExpandRecordColumn(AssessmentsTable, "Column1", {"id"}),

    // Get scores for each assessment
    AddScores = Table.AddColumn(
        ExpandAssessments,
        "Scores",
        each GetAssessmentScores([id])
    ),

    // Expand scores
    ExpandScores = Table.ExpandTableColumn(
        AddScores,
        "Scores",
        {"Field", "Score", "Percent", "Severity", "AssessmentId", "AssessmentName", "Period"}
    ),

    // Remove temporary id column
    RemoveIdColumn = Table.RemoveColumns(ExpandScores, {"id"}),

    // Type conversions
    TypedTable = Table.TransformColumnTypes(
        RemoveIdColumn,
        {
            {"Field", type text},
            {"Score", type number},
            {"Percent", type number},
            {"Severity", type text},
            {"AssessmentId", type text},
            {"AssessmentName", type text},
            {"Period", type text}
        }
    )
in
    TypedTable


// =============================================================================
// EXAMPLE 4: Get Organizational Structure (Flat)
// =============================================================================
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    // Fetch organizational units
    Source = Json.Document(
        Web.Contents(
            BaseUrl & "/units",
            [
                Headers = [#"X-API-Key" = ApiKey],
                Query = [flat = "true"]
            ]
        )
    ),

    Data = Source[data],
    ToTable = Table.FromList(Data, Splitter.SplitByNothing()),

    // Expand columns
    ExpandedColumns = Table.ExpandRecordColumn(
        ToTable,
        "Column1",
        {
            "id", "name", "path", "level", "parent_id",
            "employee_count", "sick_leave_percent", "child_count", "created_at",
            "leader"
        }
    ),

    // Expand leader nested object (can be null)
    ExpandedLeader = Table.ExpandRecordColumn(
        ExpandedColumns,
        "leader",
        {"name", "email"},
        {"leader_name", "leader_email"}
    ),

    // Type conversions
    TypedTable = Table.TransformColumnTypes(
        ExpandedLeader,
        {
            {"id", type text},
            {"name", type text},
            {"path", type text},
            {"level", Int64.Type},
            {"parent_id", type text},
            {"employee_count", Int64.Type},
            {"sick_leave_percent", type number},
            {"child_count", Int64.Type},
            {"created_at", type datetime},
            {"leader_name", type text},
            {"leader_email", type text}
        }
    )
in
    TypedTable


// =============================================================================
// EXAMPLE 5: Bulk Data Export for Data Warehouse
// =============================================================================
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
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
                    include_questions = "false",
                    include_units = "false"
                ]
            ]
        )
    ),

    Data = Source[data],

    // Extract individual responses
    Responses = Data[responses],
    ResponsesTable = Table.FromList(Responses, Splitter.SplitByNothing()),

    ExpandResponses = Table.ExpandRecordColumn(
        ResponsesTable,
        "Column1",
        {
            "response_id", "question_id", "score", "response_date",
            "respondent_id", "is_leader", "assessment_id", "unit_id", "unit_name"
        }
    ),

    // Type conversions
    TypedResponses = Table.TransformColumnTypes(
        ExpandResponses,
        {
            {"response_id", type text},
            {"question_id", Int64.Type},
            {"score", Int64.Type},
            {"response_date", type datetime},
            {"respondent_id", type text},
            {"is_leader", type logical},
            {"assessment_id", type text},
            {"unit_id", type text},
            {"unit_name", type text}
        }
    )
in
    TypedResponses


// =============================================================================
// EXAMPLE 6: Aggregated Scores Export
// =============================================================================
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    // Export aggregated scores
    Source = Json.Document(
        Web.Contents(
            BaseUrl & "/export",
            [
                Headers = [#"X-API-Key" = ApiKey],
                Query = [
                    format = "json",
                    anonymization = "pseudonymized",
                    include_responses = "false",
                    include_scores = "true",
                    include_questions = "false",
                    include_units = "false"
                ]
            ]
        )
    ),

    Data = Source[data],
    Scores = Data[aggregated_scores],

    ScoresTable = Table.FromList(Scores, Splitter.SplitByNothing()),

    ExpandScores = Table.ExpandRecordColumn(
        ScoresTable,
        "Column1",
        {
            "assessment_id", "unit_id", "unit_name",
            "field", "score", "percent", "response_count"
        }
    ),

    // Type conversions
    TypedScores = Table.TransformColumnTypes(
        ExpandScores,
        {
            {"assessment_id", type text},
            {"unit_id", type text},
            {"unit_name", type text},
            {"field", type text},
            {"score", type number},
            {"percent", type number},
            {"response_count", Int64.Type}
        }
    )
in
    TypedScores


// =============================================================================
// EXAMPLE 7: Parameterized Query (using Power BI Parameters)
// =============================================================================
/*
First, create a parameter in Power BI:
1. Home → Manage Parameters → New Parameter
2. Name: "AssessmentIdParameter"
3. Type: Text
4. Current Value: "assess-abc123"

Then use this query:
*/
let
    // Configuration
    ApiKey = "fk_xxx_xxxx_your_api_key_here",
    BaseUrl = "https://friktionskompasset.dk/api/v1",
    AssessmentId = AssessmentIdParameter,  // Reference to Power BI parameter

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

    // Convert to table
    ScoresList = {
        [Field = "TRYGHED", Score = Scores[TRYGHED][score], Percent = Scores[TRYGHED][percent], Severity = Scores[TRYGHED][severity]],
        [Field = "MENING", Score = Scores[MENING][score], Percent = Scores[MENING][percent], Severity = Scores[MENING][severity]],
        [Field = "KAN", Score = Scores[KAN][score], Percent = Scores[KAN][percent], Severity = Scores[KAN][severity]],
        [Field = "BESVÆR", Score = Scores[BESVÆR][score], Percent = Scores[BESVÆR][percent], Severity = Scores[BESVÆR][severity]]
    },

    ToTable = Table.FromRecords(ScoresList),
    TypedTable = Table.TransformColumnTypes(
        ToTable,
        {
            {"Field", type text},
            {"Score", type number},
            {"Percent", type number},
            {"Severity", type text}
        }
    )
in
    TypedTable


// =============================================================================
// TIPS AND BEST PRACTICES
// =============================================================================

/*
1. API KEY SECURITY:
   - Never hardcode API keys in shared .pbix files
   - Use Power BI parameters for API keys
   - Store keys in Azure Key Vault for enterprise deployments
   - Use Row-Level Security (RLS) to restrict data access

2. REFRESH PERFORMANCE:
   - Use scheduled refresh instead of DirectQuery
   - Cache completed assessments (they don't change)
   - Use incremental refresh for large datasets
   - Implement pagination for very large exports

3. ERROR HANDLING:
   - Add try...otherwise for API calls
   - Log errors to a separate table
   - Implement retry logic for rate limiting

4. DATA MODELING:
   - Create separate queries for Assessments, Scores, Units
   - Establish relationships using IDs
   - Create calculated measures for KPIs
   - Use hierarchies for organizational structure

5. REFRESH STRATEGY:
   - Assessments: Refresh daily
   - Organizational Structure: Refresh weekly
   - Completed Assessment Results: Cache (no refresh needed)
   - Active Assessment Monitoring: Refresh hourly

Example Error Handling:
*/
let
    ApiKey = "fk_xxx_xxxx",
    BaseUrl = "https://friktionskompasset.dk/api/v1",

    Source = try Json.Document(
        Web.Contents(BaseUrl & "/assessments", [Headers = [#"X-API-Key" = ApiKey]])
    ) otherwise [
        data = {},
        error = "API call failed"
    ],

    Data = if Record.HasFields(Source, "data") then Source[data] else {}
in
    Data
