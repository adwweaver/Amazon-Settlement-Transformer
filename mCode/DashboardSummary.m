let
    // Dashboard: per-settlement summary
    pSelectedSettlementID = "",

    // Helpers
    asText = (x) => if x = null then "" else Text.Trim(Text.From(x)),
    asNum = (x as any, field_name as text) as number =>
        let
            t = asText(x),
            cleaned = if t = "" then "0" else Text.Replace(Text.Replace(Text.Replace(t, ",", ""), "$", ""), " ", ""),
            normalized = if Text.StartsWith(cleaned, "(") and Text.EndsWith(cleaned, ")") then "-" & Text.Middle(cleaned, 1, Text.Length(cleaned) - 2) else cleaned,
            parseUS = try Number.FromText(normalized, "en-US") otherwise null,
            parseDE = if parseUS <> null then parseUS else try Number.FromText(normalized, "de-DE") otherwise null,
            parseGeneric = if parseDE <> null then parseDE else try Number.From(normalized) otherwise null
        in
            if parseGeneric = null then 0 else Number.From(parseGeneric),
    safeGet = (r as record, field as text, defaultValue) => if Record.HasFields(r, field) then (if Record.Field(r, field) = null then defaultValue else Record.Field(r, field)) else defaultValue,

    // Load & buffer sources
    SS_raw = Table.Buffer(SettlementSummary),
    JE_raw = Table.Buffer(JournalExport),
    PE_raw = Table.Buffer(PaymentExport),

    // Normalize PaymentExport key (Reference Number -> settlement_id) when present
    PE_norm = if Table.HasColumns(PE_raw, "Reference Number") then Table.RenameColumns(Table.TransformColumnTypes(PE_raw, {{"Reference Number", type text}}), {{"Reference Number", "settlement_id"}}) else PE_raw,

    // Optional filter by parameter (works for tables with settlement_id column)
    FilteredSS = if pSelectedSettlementID <> "" then Table.SelectRows(SS_raw, each asText(Record.FieldOrDefault(_, "settlement_id", "")) = pSelectedSettlementID) else SS_raw,
    FilteredJE = if pSelectedSettlementID <> "" then Table.SelectRows(JE_raw, each asText(Record.FieldOrDefault(_, "settlement_id", "")) = pSelectedSettlementID) else JE_raw,
    FilteredPE = if pSelectedSettlementID <> "" then Table.SelectRows(PE_norm, each asText(Record.FieldOrDefault(_, "settlement_id", "")) = pSelectedSettlementID) else PE_norm,

    // Deposit row: first (lowest row_id) per settlement
    DepositRowTable = Table.Group(FilteredSS, {"settlement_id"}, {{"DepositRow", each Table.FirstN(Table.Sort(_, {{"row_id", Order.Ascending}}), 1), type table}}),
    DepositExpanded = Table.ExpandTableColumn(DepositRowTable, "DepositRow", {"file_name","deposit_date","total_amount","row_id"}),

    // SettlementSummary aggregations (use direct List.Sum for transaction_amount)
    SS_Agg = Table.Group(FilteredSS, {"settlement_id"}, {
        {"Row Count", each Table.RowCount(_), Int64.Type},
        {"Cases Sold", each List.Sum(List.Transform([quantity_purchased], each asNum(_, "quantity_purchased"))), Int64.Type},
        {"Total Tax Amount", each List.Sum(List.Transform([tax_amount], each asNum(_, "tax_amount"))), Currency.Type},
        {"SS Transaction Amount Sum", each List.Sum([transaction_amount]), Currency.Type}
    }),

    // JournalExport aggregations
    JE_All = Table.Group(FilteredJE, {"settlement_id"}, {
        {"JE All Debits", each List.Sum(List.Transform([Debit], each asNum(_, "Debit"))), Currency.Type},
        {"JE All Credits", each List.Sum(List.Transform([Credit], each asNum(_, "Credit"))), Currency.Type}
    }),
    JE_Clearing = Table.Group(Table.SelectRows(FilteredJE, each Text.Trim(asText(Record.FieldOrDefault(_, "GL_Account", ""))) = "Amazon.ca Clearing"), {"settlement_id"}, {
        {"JE Clearing Debits", each List.Sum(List.Transform([Debit], each asNum(_, "Debit"))), Currency.Type}
    }),

    // PaymentExport aggregations: guard column access with Table.HasColumns (correct usage)
    PE_Agg = Table.Group(FilteredPE, {"settlement_id"}, {
        {"Total Payments", each if Table.HasColumns(_, "Payment Amount") then List.Sum(List.Transform([Payment Amount], each asNum(_, "Payment Amount"))) else 0, Currency.Type},
        {"Total Invoices", each if Table.HasColumns(_, "Invoice Amount") then List.Sum(List.Transform([Invoice Amount], each asNum(_, "Invoice Amount"))) else 0, Currency.Type}
    }),

    // Merge: start from deposit row to preserve file_name/deposit_date
    Merge1 = Table.NestedJoin(DepositExpanded, {"settlement_id"}, SS_Agg, {"settlement_id"}, "SS_Agg", JoinKind.LeftOuter),
    Merge2 = Table.ExpandTableColumn(Merge1, "SS_Agg", {"Row Count","Cases Sold","Total Tax Amount","SS Transaction Amount Sum"}),
    Merge3 = Table.NestedJoin(Merge2, {"settlement_id"}, JE_All, {"settlement_id"}, "JE_All", JoinKind.LeftOuter),
    Merge4 = Table.ExpandTableColumn(Merge3, "JE_All", {"JE All Debits","JE All Credits"}),
    Merge5 = Table.NestedJoin(Merge4, {"settlement_id"}, JE_Clearing, {"settlement_id"}, "JE_Clearing", JoinKind.LeftOuter),
    Merge6 = Table.ExpandTableColumn(Merge5, "JE_Clearing", {"JE Clearing Debits"}),
    Merge7 = Table.NestedJoin(Merge6, {"settlement_id"}, PE_Agg, {"settlement_id"}, "PE_Agg", JoinKind.LeftOuter),
    Merge8 = Table.ExpandTableColumn(Merge7, "PE_Agg", {"Total Payments","Total Invoices"}),

    // Calculations
    WithCalcs1 = Table.AddColumn(Merge8, "Invoice/Clearing Difference", each safeGet(_, "JE Clearing Debits", 0) - safeGet(_, "Total Invoices", 0), Currency.Type),
    WithCalcs2 = Table.AddColumn(WithCalcs1, "JE Balanced (All)", each safeGet(_, "JE All Debits", 0) - safeGet(_, "JE All Credits", 0), Currency.Type),
    // SS/Invoice Balance uses direct sum of SettlementSummary.transaction_amount (SS Transaction Amount Sum)
    WithCalcs3 = Table.AddColumn(WithCalcs2, "SS/Invoice Balance (Expect 0)", each safeGet(_, "SS Transaction Amount Sum", 0) - safeGet(_, "Total Invoices", 0), Currency.Type),

    // Finalize: types, rename, fill nulls, date extraction, sort
    Typed = Table.TransformColumnTypes(WithCalcs3, {
        {"total_amount", Currency.Type},
        {"JE Clearing Debits", Currency.Type},
        {"Total Invoices", Currency.Type},
        {"Invoice/Clearing Difference", Currency.Type},
        {"JE All Debits", Currency.Type},
        {"JE All Credits", Currency.Type},
        {"JE Balanced (All)", Currency.Type},
        {"Total Payments", Currency.Type},
        {"SS Transaction Amount Sum", Currency.Type},
        {"SS/Invoice Balance (Expect 0)", Currency.Type},
        {"Total Tax Amount", Currency.Type}
    }),
    Renamed = Table.RenameColumns(Typed, {
        {"file_name","File Name"},
        {"settlement_id","Settlement ID"},
        {"deposit_date","Deposit Date"},
        {"total_amount","Bank Deposit (Target)"},
        {"JE All Debits","JE: Sum of ALL Debits"},
        {"JE All Credits","JE: Sum of ALL Credits"},
        {"JE Balanced (All)","JE: Balanced (Should be 0)"},
        {"Total Invoices","Invoice Total (Payments/Invoices)"},
        {"Total Payments","Payment Total"},
        {"SS Transaction Amount Sum","SS: Transaction Amount Sum (Total Activity)"},
        {"SS/Invoice Balance (Expect 0)","SS/Invoice Balance (Expect 0)"}
    }),
    FilledNulls = Table.ReplaceValue(Renamed, null, 0, Replacer.ReplaceValue, List.RemoveItems(Table.ColumnNames(Renamed), {"File Name","Deposit Date","Settlement ID"})),
    ChangedType = Table.TransformColumnTypes(FilledNulls, {{"Deposit Date", type datetime}}),
    ExtractedDate = Table.TransformColumns(ChangedType, {{"Deposit Date", DateTime.Date, type date}}),
    Sorted = Table.Sort(ExtractedDate, {{"Deposit Date", Order.Descending}})
in
    Sorted