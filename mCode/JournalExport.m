let
    // 1. Load SettlementSummary
    Source = Table.Buffer(SettlementSummary),

    // 2. Filter rows where transaction_amount <> 0
    FilteredJournalLines = Table.SelectRows(Source, each [transaction_amount] <> 0),

    // 3. Adjust transaction_amount for tax
    AdjustedNonTax = Table.AddColumn(FilteredJournalLines, "adjusted_amount", each 
        [transaction_amount] - [tax_amount], type number  // Changed from Currency.Type
    ),

    // 4. Debug shipment_fee_type values (temporary)
    DebugShipmentFeeType = Table.AddColumn(AdjustedNonTax, "raw_shipment_fee_type", each 
        Text.Lower(Text.From(Record.FieldOrDefault(_, "shipment_fee_type", ""))), type text),

    // 5. Add Description for non-tax entries, with fix for deposit row
    AddedDescription = Table.AddColumn(DebugShipmentFeeType, "Description", each
        let
            current_row = _,
            depositDateValue = Record.FieldOrDefault(current_row, "deposit_date", null),
            hasDepositDate = depositDateValue <> null and Text.Trim(Text.From(depositDateValue)) <> "",
            relevant_columns = List.Select(
                Table.ColumnNames(DebugShipmentFeeType),
                each Text.Contains(Text.Lower(_), "type") or Text.Contains(Text.Lower(_), "description")
            ),
            values = List.Select(
                List.Transform(
                    relevant_columns,
                    each Text.Lower(Text.Trim(Text.From(Record.FieldOrDefault(current_row, _, ""))))
                ),
                each _ <> ""
            ),
            dynamicDesc = Text.Combine(values, "/"),
            desc = 
                if hasDepositDate and List.IsEmpty(values) then
                    let
                        dt = try DateTimeZone.From(depositDateValue) otherwise try DateTime.From(depositDateValue) otherwise null
                    in
                        if dt <> null then "Bank Deposit on " & Text.From(DateTime.Date(dt)) else "Bank Deposit"
                else
                    dynamicDesc
        in
            desc,
        type text
    ),

    // 6. Add GL_Account
    AddedGLAccount = Table.AddColumn(AddedDescription, "GL_Account", each
        let
            total_amt = Record.FieldOrDefault(_, "total_amount", null),
            curr = Text.Lower(Text.From(Record.FieldOrDefault(_, "currency", ""))),
            txn_type = Text.Lower(Text.From(Record.FieldOrDefault(_, "transaction_type", ""))),
            price_type = Text.Lower(Text.From(Record.FieldOrDefault(_, "price_type", ""))),
            item_fee_type = Text.Lower(Text.From(Record.FieldOrDefault(_, "item_related_fee_type", ""))),
            fee_reason = Text.Lower(Text.From(Record.FieldOrDefault(_, "other_fee_reason_description", ""))),
            promo_type = Text.Lower(Text.From(Record.FieldOrDefault(_, "promotion_type", ""))),
            shpmnt_fee_type = Text.Lower(Text.From(Record.FieldOrDefault(_, "shipment_fee_type", ""))),
            gl_account = 
                if total_amt <> null and curr = "cad" then "Amazon.ca Clearing"
                else if txn_type = "order" and price_type = "principal" then "Amazon.ca Clearing"
                else if txn_type = "refund" and price_type = "principal" then "Amazon.ca Clearing"
                else if txn_type = "order" and promo_type = "shipping" then "Amazon.ca Revenue"
                else if txn_type = "refund" and promo_type = "shipping" then "Amazon.ca Revenue"
                else if txn_type = "order" and price_type = "shipping" then "Amazon.ca Revenue"
                else if txn_type = "refund" and price_type = "shipping" then "Amazon.ca Revenue"
                else if txn_type = "order" and shpmnt_fee_type = "fba transportation fee" then "Amazon FBA Fulfillment Fees"
                else if txn_type = "refund" and shpmnt_fee_type = "fba transportation fee" then "Amazon FBA Fulfillment Fees"
                else if txn_type = "order" and item_fee_type = "fbaperunitfulfillmentfee" then "Amazon FBA Fulfillment Fees"
                else if txn_type = "refund" and item_fee_type = "fbaperunitfulfillmentfee" then "Amazon FBA Fulfillment Fees"
                else if txn_type = "order" and (item_fee_type = "commission" or item_fee_type = "digitalservicesfee" or item_fee_type = "refundcommission") then "Amazon FBA Fulfillment Fees"
                else if txn_type = "refund" and (item_fee_type = "commission" or item_fee_type = "digitalservicesfee" or item_fee_type = "refundcommission") then "Amazon FBA Fulfillment Fees"
                else if txn_type = "inbound transportation fee" then "Amazon Inbound Freight Charges"
                else if txn_type = "subscription fee" then "Amazon Account Fees"
                else if txn_type = "payable to amazon" then "Amazon.ca Clearing"
                else if txn_type = "servicefee" and item_fee_type = "cost of advertising" then "Amazon Advertising Expense"
                else if txn_type = "storage fee" then "Amazon Storage Expense"
                else if List.Contains({"warehouse_damage", "micro deposit", "reversal_reimbursement", "successful charge"}, txn_type) then "Amazon.ca Clearing"
                else "9999 - Unclassified"
        in
            gl_account,
        type text
    ),

    // 7. Add Debit/Credit for non-tax entries (no deposit_date transformation)
    AddedDebitCredit = Table.AddColumn(AddedGLAccount, "Debit", each 
        if [adjusted_amount] >= 0 then [adjusted_amount] else 0, type number  // Changed from Currency.Type
    ),
    AddedCredit = Table.AddColumn(AddedDebitCredit, "Credit", each 
        if [adjusted_amount] < 0 then -[adjusted_amount] else 0, type number  // Changed from Currency.Type
    ),

    // 8. Create tax entries
    TaxEntries = Table.SelectRows(Source, each [tax_amount] <> 0),
    FormattedTaxEntries = Table.AddColumn(TaxEntries, "GL_Account", each "Amazon Combined Tax Charged", type text),
    AddedTaxDescription = Table.AddColumn(FormattedTaxEntries, "Description", each 
        "Combined GST and PST charged on line # " & Text.From([row_id]),
        type text
    ),
    AddedTaxDebitCredit = Table.AddColumn(AddedTaxDescription, "Debit", each 
        if [tax_amount] >= 0 then [tax_amount] else 0, type number  // Changed from Currency.Type
    ),
    AddedTaxCredit = Table.AddColumn(AddedTaxDebitCredit, "Credit", each 
        if [tax_amount] < 0 then -[tax_amount] else 0, type number  // Changed from Currency.Type
    ),

    // 9. Combine non-tax and tax entries
    CombinedEntries = Table.Combine({AddedCredit, AddedTaxCredit}),

    // 10. Final columns
    FinalJournal = Table.SelectColumns(CombinedEntries, {
        "settlement_id", "deposit_date", "GL_Account", "Description", "Debit", "Credit", "row_id", "item_price_lookup"
    }),

    // 11. Validate balance per settlement_id
    ValidateBalance = Table.Group(FinalJournal, {"settlement_id"}, {
        {"TotalDebit", each List.Sum([Debit]), type number},  // Changed from Currency.Type
        {"TotalCredit", each List.Sum([Credit]), type number},  // Changed from Currency.Type
        {"BalanceCheck", each List.Sum([Debit]) - List.Sum([Credit]), type number},  // Changed from Currency.Type
        {"AllRows", each _, type table}
    }),
    AddValidationFlag = Table.AddColumn(ValidateBalance, "Validation_Flag", each 
        if Number.Abs([BalanceCheck]) < 0.01 then "Balanced" else "Unbalanced: " & Text.From([BalanceCheck]), type text),
    FinalOutput = if Table.RowCount(Table.SelectRows(AddValidationFlag, each [Validation_Flag] <> "Balanced")) > 0
        then error "Unbalanced settlement(s) detected. Check Validation_Flag."
        else FinalJournal,
    #"Changed Type" = Table.TransformColumnTypes(FinalOutput,{{"deposit_date", type datetime}}),
    #"Extracted Date" = Table.TransformColumns(#"Changed Type",{{"deposit_date", DateTime.Date, type date}}),
    #"Filled Down" = Table.FillDown(#"Extracted Date",{"deposit_date"})
in
    #"Filled Down"