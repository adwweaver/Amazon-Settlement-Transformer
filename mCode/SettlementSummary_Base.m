let
    // 1) Load remittance files
    Source = Folder.Files(pInputFolder),
    TxtOnly = Table.SelectRows(Source, each Text.Lower([Extension]) = ".txt"),

    // 2) Read and minimally clean each file
    WithData = Table.AddColumn(
        TxtOnly, "Data",
        each let
            fn = [Name],
            raw = try Csv.Document([Content], [Delimiter="#(tab)", Encoding=65001, QuoteStyle=QuoteStyle.None]) otherwise null,
            promoted = try Table.PromoteHeaders(raw, [PromoteAllScalars=true]) otherwise raw,
            clean = Table.TransformColumnNames(promoted, each Text.Replace(Text.Lower(Text.Trim(_)), "-", "_")),
            lowercase_shipment_fee_type = Table.TransformColumns(clean, {
                {"shipment_fee_type", each if _ = null then "" else Text.Lower(Text.Trim(Text.From(_))), type text}
            }),
            filtered = Table.SelectRows(lowercase_shipment_fee_type, each not (
                Record.FieldOrDefault(_, "settlement_id", "") = null 
                or Text.Trim(Text.From(Record.FieldOrDefault(_, "settlement_id", ""))) = ""
            )),
            tagged = Table.AddColumn(filtered, "file_name", (r) => fn, type text)
        in tagged
    ),

    // 3) Debug column names
    DebugColumnNames = Table.AddColumn(
        WithData,
        "ColumnNames",
        each Text.Combine(Table.ColumnNames([Data]), ", "),
        type text
    ),

    // 4) Combine all data tables
    Combined = if Table.IsEmpty(WithData) then #table({}, {}) else Table.Combine(WithData[Data]),

    // 5) Add Row_ID index column
    WithRowID = Table.AddIndexColumn(Combined, "row_id", 1, 1, Int64.Type),

    // 6) Conditional item_price_lookup
    WithKey = Table.AddColumn(
        WithRowID, "item_price_lookup", 
        each
            let
                order_id = Text.Trim(Text.From(Record.FieldOrDefault(_, "order_id", ""))),
                sku = Text.Trim(Text.From(Record.FieldOrDefault(_, "sku", ""))),
                settlement_id = Text.Trim(Text.From(Record.FieldOrDefault(_, "settlement_id", ""))),
                posted_date_ddmmyyyy = Date.ToText(
                    Date.From(
                        try DateTimeZone.FromText(Record.FieldOrDefault(_, "posted_date", "1900-01-01T00:00:00+00:00")) 
                        otherwise #datetimezone(1900, 1, 1, 0, 0, 0, 0, 0)
                    ), 
                    "ddMMyyyy"
                ),
                transaction_type = Text.Lower(Text.Trim(Text.From(Record.FieldOrDefault(_, "transaction_type", ""))))
            in
                if order_id = "" then 
                    settlement_id & posted_date_ddmmyyyy & transaction_type
                else 
                    Text.End(order_id, 7) & sku,
            type text
    ),

    // ---------- helpers ----------
    fOrDefault = (rec as record, fld as text, def as any) as any =>
        try if Record.HasFields(rec, fld) then Record.Field(rec, fld) else def otherwise def,

    asNum = (x as any, field_name as text) as number =>
        let
            n0 =
                if x = null or x = "" or Text.Trim(Text.From(x)) = "" then 0
                else if Value.Is(x, type number) then Number.From(x)
                else
                    let
                        t = Text.Trim(Text.From(x)),
                        t1 = Text.Replace(t, ",", ""),
                        t2 = if Text.StartsWith(t1, "(") and Text.EndsWith(t1, ")")
                            then "-" & Text.Middle(t1, 1, Text.Length(t1) - 2)
                            else Text.Replace(t1, "$", ""),
                        nUS = try Number.FromText(t2, "en-US") otherwise null,
                        nDE = if nUS <> null then nUS else try Number.FromText(t2, "de-DE") otherwise null
                    in
                        if nDE = null then 0 else nDE
        in n0,

    // 7) Debug raw financial values
    DebugRawValues = Table.AddColumn(
        WithKey,
        "raw_financial_values",
        each Record.FromList(
            {
                fOrDefault(_, "total_amount", ""),
                fOrDefault(_, "quantity_purchased", ""),
                fOrDefault(_, "price_amount", ""),
                fOrDefault(_, "shipment_fee_amount", ""),
                fOrDefault(_, "order_fee_amount", ""),
                fOrDefault(_, "item_related_fee_amount", ""),
                fOrDefault(_, "misc_fee_amount", ""),
                fOrDefault(_, "other_fee_amount", ""),
                fOrDefault(_, "direct_payment_amount", ""),
                fOrDefault(_, "other_amount", ""),
                fOrDefault(_, "promotion_amount", "")
            },
            {
                "total_amount", "quantity_purchased", "price_amount", "shipment_fee_amount", 
                "order_fee_amount", "item_related_fee_amount", "misc_fee_amount", 
                "other_fee_amount", "direct_payment_amount", "other_amount", "promotion_amount"
            }
        ),
        type record
    ),

    // 8) Convert total_amount to number
    ConvertTotalAmount = Table.TransformColumns(
        DebugRawValues,
        {{"total_amount", each asNum(_, "total_amount"), Currency.Type}}
    ),

    // 9) Clean financial columns
    CleanFinancialColumns = Table.TransformColumns(
        ConvertTotalAmount, 
        {
            {"quantity_purchased", each asNum(_, "quantity_purchased"), Int64.Type},
            {"price_amount", each asNum(_, "price_amount"), Currency.Type},
            {"shipment_fee_amount", each asNum(_, "shipment_fee_amount"), Currency.Type},
            {"order_fee_amount", each asNum(_, "order_fee_amount"), Currency.Type},
            {"item_related_fee_amount", each asNum(_, "item_related_fee_amount"), Currency.Type},
            {"misc_fee_amount", each asNum(_, "misc_fee_amount"), Currency.Type},
            {"other_fee_amount", each asNum(_, "other_fee_amount"), Currency.Type},
            {"direct_payment_amount", each asNum(_, "direct_payment_amount"), Currency.Type},
            {"other_amount", each asNum(_, "other_amount"), Currency.Type},
            {"promotion_amount", each asNum(_, "promotion_amount"), Currency.Type}
        }
    ),

    // 10) Add error logging for financial columns
    WithFinancialErrors = Table.AddColumn(
        CleanFinancialColumns,
        "financial_errors",
        each let
            errors = List.Select(
                {
                    if asNum(fOrDefault(_, "total_amount", ""), "total_amount") = 0 and fOrDefault(_, "total_amount", "") <> "" then "Failed to parse total_amount: " & Text.From(fOrDefault(_, "total_amount", "")) else null,
                    if asNum(fOrDefault(_, "quantity_purchased", ""), "quantity_purchased") = 0 and fOrDefault(_, "quantity_purchased", "") <> "" then "Failed to parse quantity_purchased: " & Text.From(fOrDefault(_, "quantity_purchased", "")) else null,
                    if asNum(fOrDefault(_, "price_amount", ""), "price_amount") = 0 and fOrDefault(_, "price_amount", "") <> "" then "Failed to parse price_amount: " & Text.From(fOrDefault(_, "price_amount", "")) else null,
                    if asNum(fOrDefault(_, "shipment_fee_amount", ""), "shipment_fee_amount") = 0 and fOrDefault(_, "shipment_fee_amount", "") <> "" then "Failed to parse shipment_fee_amount: " & Text.From(fOrDefault(_, "shipment_fee_amount", "")) else null,
                    if asNum(fOrDefault(_, "order_fee_amount", ""), "order_fee_amount") = 0 and fOrDefault(_, "order_fee_amount", "") <> "" then "Failed to parse order_fee_amount: " & Text.From(fOrDefault(_, "order_fee_amount", "")) else null,
                    if asNum(fOrDefault(_, "item_related_fee_amount", ""), "item_related_fee_amount") = 0 and fOrDefault(_, "item_related_fee_amount", "") <> "" then "Failed to parse item_related_fee_amount: " & Text.From(fOrDefault(_, "item_related_fee_amount", "")) else null,
                    if asNum(fOrDefault(_, "misc_fee_amount", ""), "misc_fee_amount") = 0 and fOrDefault(_, "misc_fee_amount", "") <> "" then "Failed to parse misc_fee_amount: " & Text.From(fOrDefault(_, "misc_fee_amount", "")) else null,
                    if asNum(fOrDefault(_, "other_fee_amount", ""), "other_fee_amount") = 0 and fOrDefault(_, "other_fee_amount", "") <> "" then "Failed to parse other_fee_amount: " & Text.From(fOrDefault(_, "other_fee_amount", "")) else null,
                    if asNum(fOrDefault(_, "direct_payment_amount", ""), "direct_payment_amount") = 0 and fOrDefault(_, "direct_payment_amount", "") <> "" then "Failed to parse direct_payment_amount: " & Text.From(fOrDefault(_, "direct_payment_amount", "")) else null,
                    if asNum(fOrDefault(_, "other_amount", ""), "other_amount") = 0 and fOrDefault(_, "other_amount", "") <> "" then "Failed to parse other_amount: " & Text.From(fOrDefault(_, "other_amount", "")) else null,
                    if asNum(fOrDefault(_, "promotion_amount", ""), "promotion_amount") = 0 and fOrDefault(_, "promotion_amount", "") <> "" then "Failed to parse promotion_amount: " & Text.From(fOrDefault(_, "promotion_amount", "")) else null
                },
                each _ <> null
            )
        in
            if List.IsEmpty(errors) then null else Text.Combine(errors, "; "),
        type text
    ),

    // 11) Identify the minimum row_id for each settlement_id
    PrecalculateFirstRow = Table.Group(
        WithFinancialErrors, 
        {"settlement_id"}, 
        {{"MinRowID", each List.Min([row_id]), type number}}
    ),
    RenameMinRowIDKey = Table.RenameColumns(PrecalculateFirstRow, {{"settlement_id", "JoinKey_settlement_id"}}),

    // 12) Merge MinRowID back to the main table
    WithMinRowID = Table.Join(
        WithFinancialErrors, 
        "settlement_id", 
        RenameMinRowIDKey, 
        "JoinKey_settlement_id", 
        JoinKind.LeftOuter
    ),

    // 13) Remove temporary key column
    RemoveJoinKey = Table.RemoveColumns(WithMinRowID, {"JoinKey_settlement_id"}),

    // 14) Calculate transaction_amount
    WithTxnAmt = Table.AddColumn(
        RemoveJoinKey, "transaction_amount", 
        each
            let
                normal_sum = [price_amount] 
                           + [shipment_fee_amount] 
                           + [order_fee_amount] 
                           + [item_related_fee_amount] 
                           + [misc_fee_amount] 
                           + [other_fee_amount] 
                           + [direct_payment_amount] 
                           + [other_amount] 
                           + [promotion_amount],
                is_first_row = [row_id] = [MinRowID],
                total_amount_adj = if is_first_row then -[total_amount] else 0
            in
                normal_sum + total_amount_adj,
        Currency.Type
    ),

    // 15) Add tax_amount column
    WithTaxAmount = Table.AddColumn(
        WithTxnAmt, "tax_amount",
        each
            if Text.Lower(Text.Trim(fOrDefault(_, "other_fee_reason_description", ""))) = "taxamount"
            then asNum(fOrDefault(_, "other_fee_amount", ""), "other_fee_amount")
            else 0,
        Currency.Type
    ),

    // 16) Sort by row_id

   SortedRows = Table.Sort(WithTaxAmount, {{"row_id", Order.Ascending}})

in
    SortedRows