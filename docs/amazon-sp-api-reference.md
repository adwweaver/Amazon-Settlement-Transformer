# Amazon Selling Partner API (SP-API) Reference Summary

_Last updated: 2025-10-31_

This file provides summarized documentation so AI agents and developers in this repo can interact reliably with the Amazon SP-API.  
It condenses the official docs from https://developer-docs.amazon.com/sp-api and https://github.com/amzn/selling-partner-api-docs.

---

## 🧠 Overview

The **Selling Partner API (SP-API)** is a REST-based system enabling sellers, vendors, and developers to programmatically access their Amazon business data.  
It replaces MWS (Marketplace Web Service).

### Base URLs (North America region)
| Environment | Endpoint |
|--------------|-----------|
| Production | `https://sellingpartnerapi-na.amazon.com` |
| Sandbox | `https://sandbox.sellingpartnerapi-na.amazon.com` |

**AWS Region:** `us-east-1`

---

## 🔐 Authentication Flow

SP-API uses **AWS Signature Version 4** and **Login with Amazon (LWA)** tokens.

1. Obtain an **LWA refresh token** via OAuth.  
2. Exchange it for an **LWA access token** (`POST https://api.amazon.com/auth/o2/token`).  
3. Sign requests using AWS SigV4 (HMAC SHA-256) with your IAM credentials.  
4. Include headers like the following (each on its own line):

       x-amz-access-token: <LWA access token>
       host: sellingpartnerapi-na.amazon.com
       x-amz-date: <ISO8601 timestamp>
       authorization: AWS4-HMAC-SHA256 Credential=... Signature=...

---

## 🧾 Common Endpoints

| Domain | Key Operations | Path Examples |
|---------|----------------|---------------|
| Orders | Get orders, order items | `/orders/v0/orders`, `/orders/v0/orders/{orderId}` |
| Reports | Create, get, download reports | `/reports/2021-06-30/reports` |
| Feeds | Upload inventory, pricing | `/feeds/2021-06-30/feeds` |
| Listings | Create/update listings | `/listings/2021-08-01/items/{sellerId}/{sku}` |
| Finances | Retrieve settlement data | `/finances/v0/financialEvents` |
| Catalog | Product metadata | `/catalog/2022-04-01/items/{asin}` |
| Messaging | Buyer-seller messages | `/messaging/v1/orders/{amazonOrderId}/messages` |

Refer to [developer-docs.amazon.com/sp-api](https://developer-docs.amazon.com/sp-api) for full paths and parameters.

---

## ⏱ Rate Limits (per seller account)

| Operation Type | Typical Burst | Restore Rate | Notes |
|----------------|---------------|--------------|-------|
| Orders API | 10 req/min | 1 req/sec | Use pagination token for >100 results |
| Reports API | 15 req/min | 0.2 req/sec | Creating reports is async |
| Feeds API | 15 req/min | 0.0167 req/sec | Feed processing async |
| Catalog API | 20 req/sec | 10 req/sec | varies by resource |
| Finances API | 10 req/min | 0.5 req/sec | long pagination chains possible |

Use the response headers **`x-amzn-RateLimit-Limit`** and **`x-amzn-RateLimit-Remaining`** to monitor usage.

---

## 🔁 Pagination

Endpoints returning lists use the tokens below until no `nextToken` is returned:

    nextToken
    previousToken

---

## ⚠️ Error Handling

| HTTP | Meaning | Action |
|------|----------|--------|
| 400 | Invalid input | Validate params |
| 401 | Auth error | Refresh LWA token |
| 403 | Missing scope | Check IAM policy |
| 429 | Rate limit | Retry with exponential backoff |
| 500/503 | Server error | Retry with backoff |

Example backoff logic:

    delay = min(2 ** attempt, 60)

---

## 🧮 Throttling Strategy Example (Python pseudocode)

```python
for attempt in range(10):
    response = call_sp_api(...)
    if response.status_code == 429:
        time.sleep(min(2 ** attempt, 60))
        continue
    break

📦 SDKs and Clients

Official Models: https://github.com/amzn/selling-partner-api-models

Unofficial SDKs:

Python: pip install sp-api → https://github.com/saleweaver/python-amazon-sp-api

Node.js: npm install amazon-sp-api → https://github.com/amzn/amazon-sp-api-sdk

📄 Documentation Links

Developer Portal: https://developer-docs.amazon.com/sp-api

Changelog: https://developer-docs.amazon.com/sp-api/docs/release-notes

API Models Repo: https://github.com/amzn/selling-partner-api-models

Authentication Guide: https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api

Rate Limits: https://developer-docs.amazon.com/sp-api/docs/rate-limits

🧩 Notes for Cursor / AI Agents

Always include headers for LWA & SigV4.

Use the region endpoint from this file; don’t hard-code others unless needed.

Respect rate limits and implement retry logic.

Store credentials in environment variables:

AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
LWA_CLIENT_ID
LWA_CLIENT_SECRET
REFRESH_TOKEN


When building test scripts, point to sandbox.sellingpartnerapi-na.amazon.com.


---

👉 **Why this works:**  
The only code fences are the outer ` ```markdown ` (for the whole file) and the Python example.  
All other examples (headers, tokens, env vars) use *4-space indentation*, which Markdown renders as code but doesn’t break nesting.  

This version will now display perfectly and remain a single valid file when parsed by Cursor or GitHub.
