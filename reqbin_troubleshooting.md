# ReqBin Batch API Troubleshooting

## Common Issues and Solutions

### 1. Timeout Errors
**Problem:** Request times out before completion
**Solution:** Batch requests can take 30-60+ seconds. Wait patiently or increase timeout settings.

### 2. Invalid JSON Format
**Problem:** 400 Bad Request errors
**Solution:** Ensure JSON is properly formatted with no trailing commas

### 3. CORS Issues (if using browser)
**Problem:** CORS errors in browser console
**Solution:** CORS is enabled for all origins, but try:
- Use ReqBin's web interface (not browser console)
- Or use curl/terminal instead

### 4. Server Errors (500/502/503)
**Problem:** Server is down or overloaded
**Solution:** 
- Check if single location works: `GET https://home-fit-production.up.railway.app/score?location=Hudson%20OH&enable_schools=false`
- Try again after a few minutes
- Reduce batch size (try 1-2 locations first)

## Working Request Format

**Method:** POST
**URL:** `https://home-fit-production.up.railway.app/batch`
**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "locations": [
    "Hudson OH"
  ],
  "enable_schools": false,
  "include_chains": true,
  "adaptive_delays": true
}
```

## Test with Single Location First

Start with one location to verify the endpoint works:

```json
{
  "locations": ["Hudson OH"],
  "enable_schools": false
}
```

If this works, gradually add more locations.

## Alternative: Use Individual /score Endpoints

If batch continues to fail, use individual requests:

```
GET https://home-fit-production.up.railway.app/score?location=Hudson%20OH&enable_schools=false
GET https://home-fit-production.up.railway.app/score?location=Hyde%20Park%20Chicago%20IL&enable_schools=false
... (repeat for each location)
```
