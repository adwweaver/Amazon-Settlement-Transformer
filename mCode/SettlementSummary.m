let
    Source = SettlementSummary_Base,
    Filtered = Table.SelectRows(Source, each pSelectedSettlementID = "" or [settlement_id] = pSelectedSettlementID)
in
    Filtered