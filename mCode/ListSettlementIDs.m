let
    // ListSettlementIDs with deposit metadata (first record per settlement)
    Source = SettlementSummary_Base,

    // Ensure a row identifier exists so "first record" is deterministic
    SourceWithRowId = if Table.HasColumns(Source, "row_id") 
        then Source 
        else Table.AddIndexColumn(Source, "row_id", 0, 1, Int64.Type),

    // Group by settlement_id and pick the first (lowest row_id) row for metadata
    DepositRows = Table.Group(SourceWithRowId, {"settlement_id"}, {
        {"DepositRow", each Table.FirstN(Table.Sort(_, {{"row_id", Order.Ascending}}), 1), type table}
    }),

    // Expand the fields we need from that first row
    Expanded = Table.ExpandTableColumn(DepositRows, "DepositRow", {"file_name", "deposit_date", "total_amount"}, {"File Name", "Deposit Date", "Bank Deposit (Target)"}),

    // Type the columns and sort (optional)
    Typed = Table.TransformColumnTypes(Expanded, {
        {"Deposit Date", type datetime},
        {"Bank Deposit (Target)", Currency.Type},
        {"settlement_id", type text}
    }),

    Sorted = Table.Sort(Typed, {{"Deposit Date", Order.Descending}}),
    #"Extracted Date" = Table.TransformColumns(Sorted,{{"Deposit Date", DateTime.Date, type date}})
in
    #"Extracted Date"