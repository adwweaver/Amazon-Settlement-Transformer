let
    // SettlementSummary already filtered by pSelectedSettlementID in SettlementSummary.m
    SS0 = Table.SelectColumns(
        SettlementSummary,
        {"settlement_id","row_id","file_name","deposit_date","total_amount","quantity_purchased","tax_amount","transaction_amount"}
    ),
    SS = Table.Buffer(SS0),

    // JournalExport: keep only the needed cols and coerce numerics
    JE0 = if Value.Is(JournalExport, type table) then JournalExport else #table({},{}),
    JE1 = Table.SelectColumns(JE0, List.Intersect({{"settlement_id","GL_Account","Debit","Credit"}, Table.ColumnNames(JE0)})),
    JE2 = Table.TransformColumns(JE1, {
        {"Debit", each try Number.From(_) otherwise 0, type number},
        {"Credit", each try Number.From(_) otherwise 0, type number}
    }),
    JE = Table.Buffer(JE2),

    // InvoiceExport: map Reference Number -> settlement_id and coerce numerics
    IE0 = if Value.Is(InvoiceExport, type table) then InvoiceExport else #table({},{}),
    IE1 = if Table.HasColumns(IE0, "Reference Number") then Table.RenameColumns(IE0, {{"Reference Number","settlement_id"}}) else IE0,
    IE2 = Table.SelectColumns(IE1, List.Intersect({{"settlement_id","Invoice Line Amount"}, Table.ColumnNames(IE1)})),
    IE = Table.TransformColumns(IE2, {{"Invoice Line Amount", each try Number.From(_) otherwise 0, type number}}),

    // Settlement aggregates (single pass) + tax line count
    SS_Agg = Table.Group(SS, {"settlement_id"}, {
        {"Row Count", each Table.RowCount(_), Int64.Type},
        {"Cases Sold", each List.Sum(List.Transform([quantity_purchased], each try Number.From(_) otherwise 0)), Int64.Type},
        {"Total Tax Amount", each List.Sum(List.Transform([tax_amount], each try Number.From(_) otherwise 0)), type number},
        {"SS Transaction Amount Sum", each List.Sum(List.Transform([transaction_amount], each try Number.From(_) otherwise 0)), type number},
        {"tax line count", each List.Count(List.Select([tax_amount], each (try Number.From(_) otherwise 0) <> 0)), Int64.Type},
        {"DepositRow", each 
            let m = List.Min([row_id]),
                row = try Table.First(Table.SelectRows(_, each [row_id] = m)) otherwise null
            in row, type nullable record}
    }),
    SS_Expanded = Table.ExpandRecordColumn(
        SS_Agg, "DepositRow",
        {"file_name","deposit_date","total_amount","row_id"},
        {"file_name","deposit_date","total_amount","deposit_row_id"}
    ),
    SS_Typed = Table.TransformColumnTypes(SS_Expanded, {
        {"total_amount", type number},
        {"deposit_date", type datetime}
    }),
    #"Extracted Date" = Table.TransformColumns(SS_Typed,{{"deposit_date", DateTime.Date, type date}}),
    #"Changed Type" = Table.TransformColumnTypes(#"Extracted Date",{{"SS Transaction Amount Sum", Int64.Type}}),

    // Journal aggregates (includes clearing)
    JE_Agg = if Table.RowCount(JE) = 0 then
        #table(type table [settlement_id=text, #"JE All Debits"=number, #"JE All Credits"=number, #"JE Clearing Debits"=number], {})
    else
        Table.Group(JE, {"settlement_id"}, {
            {"JE All Debits", each List.Sum([Debit]), type number},
            {"JE All Credits", each List.Sum([Credit]), type number},
            {"JE Clearing Debits", each 
                let t = Table.SelectRows(_, each Text.Trim(Text.From([GL_Account])) = "Amazon.ca Clearing")
                in if Table.HasColumns(t, "Debit") then List.Sum(t[Debit]) else 0, type number}
        }),

    // Invoice aggregates
    IE_Agg = if Table.RowCount(IE) = 0 or not Table.HasColumns(IE, "Invoice Line Amount") then
        #table(type table [settlement_id=text, #"Invoice Total"=number], {})
    else
        Table.Group(IE, {"settlement_id"}, {
            {"Invoice Total", each List.Sum([Invoice Line Amount]), type number}
        }),

    // Merge small aggregates into one fact per settlement
    M1 = Table.NestedJoin(#"Changed Type", {"settlement_id"}, JE_Agg, {"settlement_id"}, "JE", JoinKind.LeftOuter),
    E1 = Table.ExpandTableColumn(M1, "JE", {"JE All Debits","JE All Credits","JE Clearing Debits"}),
    M2 = Table.NestedJoin(E1, {"settlement_id"}, IE_Agg, {"settlement_id"}, "IE", JoinKind.LeftOuter),
    E2 = Table.ExpandTableColumn(M2, "IE", {"Invoice Total"}),

    // Calculations
    WithCalcs1 = Table.AddColumn(E2, "Invoice/Clearing Difference", each
        (try Number.From([JE Clearing Debits]) otherwise 0) - (try Number.From([Invoice Total]) otherwise 0), type number),
    WithCalcs2 = Table.AddColumn(WithCalcs1, "JE Balanced (All)", each
        (try Number.From([JE All Debits]) otherwise 0) - (try Number.From([JE All Credits]) otherwise 0), type number),

    // Final coercions
    Typed = Table.TransformColumnTypes(WithCalcs2, {
        {"total_amount", type number},
        {"JE All Debits", type number},
        {"JE All Credits", type number},
        {"JE Clearing Debits", type number},
        {"Invoice Total", type number},
        {"SS Transaction Amount Sum", type number},
        {"Total Tax Amount", type number},
        {"deposit_date", type datetime},
        {"Invoice/Clearing Difference", type number},
        {"JE Balanced (All)", type number},
        {"tax line count", Int64.Type}
    }),

    // Rename for presentation
    Renamed = Table.RenameColumns(Typed, {
        {"file_name","File Name"},
        {"settlement_id","Settlement ID"},
        {"deposit_date","Deposit Date"},
        {"total_amount","Bank Deposit"},
        {"SS Transaction Amount Sum","SUM of Settlement = 0"},
        {"Total Tax Amount","total tax"},
        {"JE All Debits","Total Debits"},
        {"JE All Credits","Total Credits"}
    }, MissingField.Ignore),

    // Remove if present (requested)
    RemovedUnneeded = if List.Contains(Table.ColumnNames(Renamed), "SS/Invoice Balance (Expect 0)")
                      then Table.RemoveColumns(Renamed, {"SS/Invoice Balance (Expect 0)"})
                      else Renamed,

    // Deposit Date -> date only
    DepositTyped = if List.Contains(Table.ColumnNames(RemovedUnneeded), "Deposit Date")
                   then Table.TransformColumnTypes(RemovedUnneeded, {{"Deposit Date", type datetime}})
                   else RemovedUnneeded,
    DepositDateOnly = Table.TransformColumns(DepositTyped, {{"Deposit Date", DateTime.Date, type date}}, null, MissingField.Ignore),

    // Reorder columns exactly as requested; keep others after
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