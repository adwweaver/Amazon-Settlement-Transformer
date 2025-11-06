let
    // 1. Reference the core Settlement Summary data
    Source = SettlementSummary,

    // 2. CRITICAL FIX: Ensure all relevant columns are numeric
    ChangedType = Table.TransformColumnTypes(Source, {
        {"price_amount", type number}, 
        {"other_amount", type number},
        {"quantity_purchased", Int64.Type} // Ensure quantity is treated as a number
    }),
    
    // 3. Define the Price Line Amount (price_amount_line) based on new conditional logic
    WithPriceLine = Table.AddColumn(ChangedType, "price_amount_line", each
        let
            priceType = Text.Trim(Text.Lower(Record.FieldOrDefault(_, "price_type", ""))),
            txnType = Text.Trim(Text.Upper(Record.FieldOrDefault(_, "transaction_type", ""))),
            // Safely default null/blank quantity to 0 for the check
            original_qty = Record.FieldOrDefault(_, "quantity_purchased", 0) 
        in
            // SCENARIO 1: Damages/Reversals where quantity is present
            if (txnType = "WAREHOUSE DAMAGE" or txnType = "REVERSAL_REIMBURSEMENT") 
               and original_qty > 0 then
                // If quantity is NOT null/0, use other_amount
                Record.FieldOrDefault(_, "other_amount", 0)
            
            // SCENARIO 2: Principal sale price
            else if priceType = "principal" then
                // Otherwise, use price_amount (for later aggregation/lookup)
                Record.FieldOrDefault(_, "price_amount", 0)
            
            // SCENARIO 3: None of the above (returns 0, ignored by later filter)
            else
                0
    , type number),
    
    // 4. Filter to only rows that have a valid lookup key AND a calculated price or quantity
    FilteredRows = Table.SelectRows(WithPriceLine, each 
        [item_price_lookup] <> "" 
        and ( [price_amount_line] <> 0 or ([quantity_purchased] <> null and [quantity_purchased] <> 0) )
    ),

    // 5. Group by item_price_lookup, taking MAX(Price Line) and MAX(Quantity)
    // The MAX of price_amount_line effectively becomes your aggregated lookup price.
    GroupedLookup = Table.Group(FilteredRows, {"item_price_lookup"}, {
        {"total_price_amount", each List.Max(Table.Column(_, "price_amount_line")), type number}, // Renamed to total_price_amount
        {"quantity_purchased", each List.Max(Table.Column(_, "quantity_purchased")), Int64.Type} 
    }),
    
    // 6. Final filter: Ensures we don't try to calculate a unit price where price or quantity is zero
    CleanedLookup = Table.SelectRows(GroupedLookup, each 
        [total_price_amount] <> 0 
        and [quantity_purchased] <> null 
        and [quantity_purchased] <> 0
    ),
    
    // 7. Calculate case_price_amount (Unit Price)
    WithCasePriceAmount = Table.AddColumn(CleanedLookup, "case_price_amount", each 
        [total_price_amount] / [quantity_purchased], 
        Currency.Type
    ),
    
    // 8. FINAL STEP: Select final columns
    Final = Table.SelectColumns(WithCasePriceAmount, {
        "item_price_lookup", 
        "total_price_amount", 
        "quantity_purchased", 
        "case_price_amount"
    })

in
    Final