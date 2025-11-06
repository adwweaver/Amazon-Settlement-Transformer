let
    // Base fact table from helper
    F = Table.Buffer(Dashboard_Source),

    // Ensure we don't add duplicate calc columns if they already exist
    Cleanup = Table.RemoveColumns(F, List.Intersect({Table.ColumnNames(F), {"Invoice/Clearing Difference","JE Balanced (All)","SS/Invoice Balance (Expect 0)"}})),

    // Calculations
    WithCalcs1 = Table.AddColumn(Cleanup, "Invoice/Clearing Difference", each
        (try Number.From([JE Clearing Debits]) otherwise 0) - (try Number.From([Invoice Total]) otherwise 0), type number),
    WithCalcs2 = Table.AddColumn(WithCalcs1, "JE Balanced (All)", each
        (try Number.From([JE All Debits]) otherwise 0) - (try Number.From([JE All Credits]) otherwise 0), type number),

    // Tax line count: count SS rows with tax_amount <> 0 for the IDs present in F
    IDs = if List.Contains(Table.ColumnNames(Cleanup), "settlement_id")
          then List.Buffer(List.Distinct(Cleanup[settlement_id])) else {},
    SS_forTax = SettlementSummary,
    SS_taxRows = if List.Count(IDs) = 0 then #table(type table [settlement_id=text, tax_amount=number], {})
                 else Table.SelectRows(SS_forTax, each List.Contains(IDs, [settlement_id]) and ((try Number.From([tax_amount]) otherwise 0) <> 0)),
    TaxCountBySettle = if Table.RowCount(SS_taxRows) = 0
        then #table(type table [settlement_id=text, #"tax line count"=Int64.Type], {})
        else Table.Group(SS_taxRows, {"settlement_id"}, {{"tax line count", each Table.RowCount(_), Int64.Type}}),
    M_Tax = if List.Contains(Table.ColumnNames(WithCalcs2), "settlement_id")
        then Table.NestedJoin(WithCalcs2, {"settlement_id"}, TaxCountBySettle, {"settlement_id"}, "TaxAgg", JoinKind.LeftOuter)
        else WithCalcs2,
    E_Tax = if List.Contains(Table.ColumnNames(M_Tax), "TaxAgg")
        then Table.ExpandTableColumn(M_Tax, "TaxAgg", {"tax line count"})
        else M_Tax,

    // Presentation renames (keep numeric raw names in source)
    Renamed = Table.RenameColumns(E_Tax, {
        {"file_name","File Name"},
        {"settlement_id","Settlement ID"},
        {"deposit_date","Deposit Date"},
        {"total_amount","Bank Deposit"},
        {"SS Transaction Amount Sum","SUM of Settlement = 0"},
        {"Total Tax Amount","total tax"},
        {"JE All Debits","Total Debits"},
        {"JE All Credits","Total Credits"}
    }, MissingField.Ignore),

    // Date handling (no culture arg on TransformColumnTypes)
    DepositTyped =
        if List.Contains(Table.ColumnNames(Renamed), "Deposit Date")
        then Table.TransformColumnTypes(Renamed, {{"Deposit Date", type datetime}})
        else Renamed,
    DepositDateOnly = Table.TransformColumns(DepositTyped, {{"Deposit Date", DateTime.Date, type date}}, null, MissingField.Ignore),

    // Reorder columns per your requested order; keep any others after
    DesiredOrder = {
        "File Name",
        "Deposit Date",
        "Settlement ID",
        "Bank Deposit",
        "Cases Sold",
        "Invoice Total",
        "JE Clearing Debits",
        "Invoice/Clearing Difference",
        "Total Debits",
        "Total Credits",
        "JE Balanced (All)",
        "SUM of Settlement = 0",
        "deposit_row_id",
        "Row Count",
        "total tax",
        "tax line count"
    },
    PresentDesired = List.Select(DesiredOrder, each List.Contains(Table.ColumnNames(DepositDateOnly), _)),
    Reordered = Table.ReorderColumns(DepositDateOnly, PresentDesired, MissingField.Ignore)
in
    Reordered