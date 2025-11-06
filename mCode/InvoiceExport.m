let
    // 1. Reference SettlementSummary
    Source = SettlementSummary,

    // 2. Filter for quantity_purchased <> 0 or not null
    FilterPurchasedItems = Table.SelectRows(Source, each 
        Record.FieldOrDefault(_, "quantity_purchased", null) <> null and 
        Record.FieldOrDefault(_, "quantity_purchased", 0) <> 0
    ),

    // 3. Merge with PriceLookup_CasePrice
    MergeCasePrice = Table.NestedJoin(
        FilterPurchasedItems, 
        {"item_price_lookup"}, 
        PriceLookup_CasePrice, 
        {"item_price_lookup"}, 
        "CasePriceData", 
        JoinKind.LeftOuter
    ),

    // 4. Expand case_price_amount, use transaction_amount as fallback
    ExpandCasePrice = Table.AddColumn(
        MergeCasePrice, "Item Price", 
        each
            let
                case_price_table = [CasePriceData],
                case_price_record = if Table.IsEmpty(case_price_table) then null else Table.First(case_price_table),
                case_price = if case_price_record = null then null else Record.FieldOrDefault(case_price_record, "case_price_amount", null),
                trans_amount = [transaction_amount]
            in
                if case_price = null or case_price = 0 then trans_amount else case_price,
        type number  // Changed from Currency.Type
    ),

    // 5. Select relevant columns
    SelectColumns = Table.SelectColumns(ExpandCasePrice, {
        "posted_date", "order_id", "marketplace_name", "transaction_type", 
        "sku", "quantity_purchased", "Item Price", "row_id", "settlement_id", "tax_amount"
    }),

    // 6. Parse posted_date robustly
    ParseDate = Table.AddColumn(SelectColumns, "ParsedPostedDate", each 
        let
            raw_date = Text.Trim(Text.From(Record.FieldOrDefault(_, "posted_date", ""))),
            parsed = try DateTimeZone.FromText(raw_date) otherwise #datetimezone(1900, 1, 1, 0, 0, 0, 0, 0)
        in
            parsed,
        type datetimezone
    ),

    // 7. Transform to date-only for Invoice Date
    TransformDate = Table.AddColumn(ParseDate, "InvoiceDateTemp", each 
        Date.From([ParsedPostedDate]), 
        type date
    ),
    ReplacePostedDate = Table.RemoveColumns(TransformDate, {"posted_date"}),
    RenameInvoiceDate = Table.RenameColumns(ReplacePostedDate, {
        {"InvoiceDateTemp", "posted_date"}
    }),

    // 8. Generate Invoice Number
    WithInvoiceNumber = Table.AddColumn(RenameInvoiceDate, "Invoice Number", each
        let
            order_id = Text.Trim(Text.From(Record.FieldOrDefault(_, "order_id", ""))),
            is_order = Text.Length(order_id) > 0,
            suffix = 
                if is_order 
                then Text.End(order_id, 7)
                else 
                    let
                        year_last_digit = Text.End(Text.From(Date.Year([ParsedPostedDate])), 1),
                        time_component = DateTime.ToText(DateTime.From([ParsedPostedDate]), "hhmmss")
                    in
                        year_last_digit & time_component
        in
            "AMZN" & suffix,
        type text
    ),

    // 9. Add Notes and Customer Name
    AddNotesAndCustomer = Table.AddColumn(WithInvoiceNumber, "Notes", each 
        Text.Combine({
            [transaction_type],
            if [transaction_type] = "Order" then " " & [order_id] else "",
            if [tax_amount] <> 0 then " Tax: " & Text.From([tax_amount]) else ""
        }, ""),
        type text
    ),
    FixedCustomerName = Table.TransformColumns(AddNotesAndCustomer, {
        {"marketplace_name", each if Text.Trim(_) = "" or _ = null then "Amazon.ca" else _, type text}
    }),

    // 10. Rename columns for Zoho Books
    RenamedColumns = Table.RenameColumns(FixedCustomerName, {
        {"posted_date", "Invoice Date"},
        {"marketplace_name", "Customer Name"},
        {"quantity_purchased", "Quantity"},
        {"sku", "SKU"},
        {"settlement_id", "Reference Number"}
    }),

    // 11. Add Invoice Status and calculate Invoice Line Amount
    AddFixedColumns = Table.AddColumn(RenamedColumns, "Invoice Status", each "Draft", type text),
    WithInvoiceAmount = Table.AddColumn(AddFixedColumns, "Invoice Line Amount", each 
        [Item Price] * [Quantity], type number  // Changed from Currency.Type
    ),

    // 12. Validate non-zero Invoice Line Amount
    ValidateInvoiceAmount = Table.AddColumn(WithInvoiceAmount, "Validation_Flag", each 
        if [Invoice Line Amount] = 0 then "Zero Invoice Amount: Review" else "Valid", type text
    ),

    // 13. Final column selection
    FinalOutput = Table.SelectColumns(ValidateInvoiceAmount, {
        "Invoice Date", "Invoice Number", "Invoice Status", "Customer Name", 
        "SKU", "Quantity", "Item Price", "Invoice Line Amount", "Notes", 
        "Reference Number", "row_id", "Validation_Flag"
    }),

    // 14. Filter out invalid rows
    FilteredRows = Table.SelectRows(FinalOutput, each [Validation_Flag] = "Valid")
in
    FilteredRows