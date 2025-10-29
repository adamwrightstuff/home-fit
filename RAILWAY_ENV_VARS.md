# Railway Environment Variables

This document lists the environment variables that need to be configured in Railway's dashboard for the HomeFit API to function properly.

## Essential Variables

These are required for full functionality:

| Variable | Purpose | Where to Get |
|----------|---------|--------------|
| `CENSUS_API_KEY` | Access Census Bureau data for housing values, demographics | [Census API](https://api.census.gov/data/key_signup.html) |
| `SCHOOLDIGGER_APPID` | SchoolDigger API application ID | [SchoolDigger API](https://www.schooldigger.com/api) |
| `SCHOOLDIGGER_APPKEY` | SchoolDigger API application key | [SchoolDigger API](https://www.schooldigger.com/api) |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Google Earth Engine service account credentials (full JSON string) | Google Cloud Console - Service Account |

## Optional Variables

These enhance functionality but aren't critical:

| Variable | Purpose | Fallback |
|----------|---------|----------|
| `REDIS_URL` | Redis cache connection string | Uses in-memory cache |
| `TRANSITLAND_API_KEY` | Transitland API for transit data | May work without it (some features limited) |

## How to Set in Railway

1. Go to your Railway project dashboard
2. Click on your service
3. Go to the **Variables** tab
4. Click **+ New Variable**
5. Add each variable name and value
6. Save and redeploy

## Verification

After setting variables, you can verify they're working by:

1. Checking Railway logs for credential status messages
2. Calling the `/health` endpoint which reports credential availability
3. Testing an endpoint that requires credentials (e.g., school scoring)

## Notes

- **Never commit `.env` files** - They contain secrets and are blocked by GitHub push protection
- Railway reads environment variables from the dashboard, not from `.env` files in the repo
- If variables aren't set, the API will still run but certain features will use fallback scores or return limited data

