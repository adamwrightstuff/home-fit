# Individual API Requests for Safari/ReqBin

Since batch requests take too long and Safari/ReqBin times out, use individual `/score` requests instead.

## Request Format for Each Location

**Method:** GET  
**URL:** `https://home-fit-production.up.railway.app/score`  
**Headers:** None needed  
**Query Parameters:**
- `location` - URL encoded location string
- `enable_schools` - Set to `false`

## Individual Requests

### 1. Hudson OH
```
GET https://home-fit-production.up.railway.app/score?location=Hudson%20OH&enable_schools=false
```

### 2. Hyde Park Chicago IL
```
GET https://home-fit-production.up.railway.app/score?location=Hyde%20Park%20Chicago%20IL&enable_schools=false
```

### 3. Inner Harbor Baltimore MD
```
GET https://home-fit-production.up.railway.app/score?location=Inner%20Harbor%20Baltimore%20MD&enable_schools=false
```

### 4. Irvine CA
```
GET https://home-fit-production.up.railway.app/score?location=Irvine%20CA&enable_schools=false
```

### 5. Jackson WY
```
GET https://home-fit-production.up.railway.app/score?location=Jackson%20WY&enable_schools=false
```

### 6. Kiawah Island SC
```
GET https://home-fit-production.up.railway.app/score?location=Kiawah%20Island%20SC&enable_schools=false
```

### 7. Lake Placid NY
```
GET https://home-fit-production.up.railway.app/score?location=Lake%20Placid%20NY&enable_schools=false
```

## Why This Works Better

- Each request completes in ~30-60 seconds (vs 5-10 minutes for batch)
- No timeout issues
- Can see results immediately
- Can retry individual locations if one fails

## JavaScript for Safari Console (Alternative)

```javascript
const locations = [
  "Hudson OH",
  "Hyde Park Chicago IL",
  "Inner Harbor Baltimore MD",
  "Irvine CA",
  "Jackson WY",
  "Kiawah Island SC",
  "Lake Placid NY"
];

async function fetchAllLocations() {
  const results = [];
  
  for (const location of locations) {
    const encoded = encodeURIComponent(location);
    const url = `https://home-fit-production.up.railway.app/score?location=${encoded}&enable_schools=false`;
    
    console.log(`Fetching: ${location}...`);
    
    try {
      const response = await fetch(url);
      const data = await response.json();
      results.push({ location, success: true, data });
      console.log(`✓ ${location} completed`);
    } catch (error) {
      results.push({ location, success: false, error: error.message });
      console.error(`✗ ${location} failed:`, error);
    }
    
    // Small delay between requests
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  
  console.log('All results:', results);
  return results;
}

fetchAllLocations();
```
