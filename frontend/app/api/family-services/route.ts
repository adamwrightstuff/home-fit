import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 15;

const PLACES_URL = 'https://places.googleapis.com/v1/places:searchNearby';
const FIELD_MASK = 'places.displayName,places.rating,places.userRatingCount,places.googleMapsUri,places.types';

const CHILDCARE_TYPE_GROUPS = [
  ['child_care_agency'],
  ['preschool'],
  ['kindergarten'],
];

const ACTIVITY_TYPE_GROUPS = [
  ['ice_skating_rink'],
  ['dance_studio'],
  ['martial_arts_school'],
  ['sports_club'],
  ['gym'],
  ['swimming_pool'],
];

// Keywords that indicate adult-only facilities — filter these out from activities
const ADULT_KEYWORDS = [
  'pilates', 'soulcycle', 'barre', 'crossfit', 'orangetheory', 'equinox',
  'planet fitness', 'crunch', 'blink fitness', 'solidcore', 'hotworx', 'f45',
  'yoga', 'spin', 'cycling studio', 'row house', 'stretch lab',
];

// Keywords that indicate kid-friendly activities — boost these
const KIDS_KEYWORDS = [
  'kids', 'child', 'youth', 'junior', 'little', 'tiny', 'young', 'junior',
  'swim school', 'goldfish', 'gymnastics', 'ballet', 'soccer', 'hockey',
  'karate', 'judo', 'tae kwon', 'martial art', 'my gym', 'little gym',
  'dance school', 'music school', 'art class', 'science', 'coding',
  'recreation', 'rec center', 'ymca', 'jcc',
];

interface PlaceResult {
  name: string;
  rating: number | null;
  reviews: number;
  url: string;
  type: string;
  kidsScore: number;
}

async function searchNearby(
  apiKey: string,
  lat: number,
  lon: number,
  types: string[],
  radius: number,
): Promise<PlaceResult[]> {
  const body = {
    locationRestriction: {
      circle: { center: { latitude: lat, longitude: lon }, radius },
    },
    includedTypes: types,
    maxResultCount: 20,
    rankPreference: 'DISTANCE',
  };
  const res = await fetch(PLACES_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': apiKey,
      'X-Goog-FieldMask': FIELD_MASK,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error('[family-services] Places API error', res.status, err.slice(0, 300));
    return [];
  }
  const data = await res.json();
  const places = data.places ?? [];
  return places.map((p: Record<string, unknown>) => {
    const displayName = (p.displayName as Record<string, string> | undefined)?.text ?? '';
    const nameLower = displayName.toLowerCase();
    const kidsScore = KIDS_KEYWORDS.some((k) => nameLower.includes(k)) ? 1 : 0;
    return {
      name: displayName,
      rating: typeof p.rating === 'number' ? p.rating : null,
      reviews: typeof p.userRatingCount === 'number' ? p.userRatingCount : 0,
      url: typeof p.googleMapsUri === 'string' ? p.googleMapsUri : '',
      type: types[0],
      kidsScore,
    };
  });
}

async function collectCategory(
  apiKey: string,
  lat: number,
  lon: number,
  typeGroups: string[][],
  radius: number,
  filterAdult: boolean,
): Promise<PlaceResult[]> {
  const seen = new Set<string>();
  const results: PlaceResult[] = [];
  await Promise.all(
    typeGroups.map(async (types) => {
      const places = await searchNearby(apiKey, lat, lon, types, radius);
      for (const p of places) {
        if (!p.name || seen.has(p.name)) continue;
        if (filterAdult) {
          const lower = p.name.toLowerCase();
          if (ADULT_KEYWORDS.some((k) => lower.includes(k))) continue;
        }
        seen.add(p.name);
        results.push(p);
      }
    }),
  );
  return results;
}

function rankResults(results: PlaceResult[], maxItems: number): PlaceResult[] {
  return results
    .sort((a, b) => {
      // Prefer kids-specific first
      if (b.kidsScore !== a.kidsScore) return b.kidsScore - a.kidsScore;
      // Then by review-weighted rating (ignore ratings with < 5 reviews)
      const ra = (a.reviews >= 5 && a.rating != null) ? a.rating : 0;
      const rb = (b.reviews >= 5 && b.rating != null) ? b.rating : 0;
      if (rb !== ra) return rb - ra;
      return b.reviews - a.reviews;
    })
    .slice(0, maxItems);
}

export async function GET(req: NextRequest) {
  const apiKey = process.env.GOOGLE_PLACES_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'Places API not configured' }, { status: 503 });
  }

  const lat = parseFloat(req.nextUrl.searchParams.get('lat') ?? '');
  const lon = parseFloat(req.nextUrl.searchParams.get('lon') ?? '');
  if (!isFinite(lat) || !isFinite(lon)) {
    return NextResponse.json({ error: 'Missing lat/lon' }, { status: 400 });
  }

  const radius = 3000;

  const [childcare, activities] = await Promise.all([
    collectCategory(apiKey, lat, lon, CHILDCARE_TYPE_GROUPS, radius, false),
    collectCategory(apiKey, lat, lon, ACTIVITY_TYPE_GROUPS, radius, true),
  ]);

  return NextResponse.json({
    childcare: rankResults(childcare, 5),
    activities: rankResults(activities, 5),
  });
}
