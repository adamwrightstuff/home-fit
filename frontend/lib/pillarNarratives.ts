import type { PillarKey } from './pillars'
import { getPillarValue, getPillarString } from './pillarDetailsSpec'

const DIVISION_LABELS: Record<string, string> = {
  east_north_central: 'East North Central U.S.',
  east_south_central: 'East South Central U.S.',
  middle_atlantic: 'Middle Atlantic U.S.',
  mountain: 'Mountain West U.S.',
  new_england: 'New England U.S.',
  pacific: 'Pacific U.S.',
  south_atlantic: 'South Atlantic U.S.',
  west_north_central: 'West North Central U.S.',
  west_south_central: 'West South Central U.S.',
}

export function getNaturalBeautyNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const treeScore = getPillarValue(pillar, 'summary.tree_score')
  const localCanopy = getPillarValue(pillar, 'summary.local_canopy_pct')
  const neighborhoodCanopy = getPillarValue(pillar, 'summary.neighborhood_canopy_pct')

  let greeneryPhrase = 'a mix of greenery and harder surfaces'
  if (typeof treeScore === 'number') {
    if (treeScore >= 70) greeneryPhrase = 'strong tree cover and natural greenery'
    else if (treeScore <= 30) greeneryPhrase = 'limited tree cover and greenery'
  } else if (typeof neighborhoodCanopy === 'number') {
    if (neighborhoodCanopy >= 50) greeneryPhrase = 'many trees in the surrounding neighborhood'
    else if (neighborhoodCanopy <= 20) greeneryPhrase = 'very few trees in the surrounding neighborhood'
  }

  let blockPhrase = ''
  if (typeof localCanopy === 'number') {
    if (localCanopy >= 40) blockPhrase = ' right around your block'
    else if (localCanopy <= 15) blockPhrase = ' even right around your block'
  }

  const locationSentence = `${placeLabel} has ${greeneryPhrase}${blockPhrase}.`
  const genericSentence =
    'Nearby trees, water, and natural views are linked to lower stress, better mental health, and more time spent walking outside.'

  return `${locationSentence} ${genericSentence}`
}

export function getBuiltBeautyNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const diversity = getPillarValue(pillar, 'summary.diversity_score')
  const heightDiversity = getPillarValue(pillar, 'summary.height_diversity')

  let characterPhrase = 'a fairly plain built environment'
  if (typeof diversity === 'number') {
    if (diversity >= 70) characterPhrase = 'a lot of visual variety and character in its buildings and streets'
    else if (diversity <= 30) characterPhrase = 'more uniform, cookie-cutter buildings and streets'
  }

  let scalePhrase = ''
  if (typeof heightDiversity === 'number') {
    if (heightDiversity >= 60) scalePhrase = ' with a mix of building heights that can feel more interesting on foot'
    else if (heightDiversity <= 20) scalePhrase = ' with more uniform building heights that can feel less varied'
  }

  const locationSentence = `${placeLabel} has ${characterPhrase}${scalePhrase}.`
  const genericSentence =
    'Thoughtful architecture and human-scale streets help places feel welcoming and walkable, which supports comfort and social connection over time.'

  return `${locationSentence} ${genericSentence}`
}

export function getNeighborhoodAmenitiesNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const walkScore = getPillarValue(pillar, 'breakdown.home_walkability.score')
  const bizCount = getPillarValue(pillar, 'breakdown.home_walkability.businesses_within_1km')
  const townScore = getPillarValue(pillar, 'breakdown.location_quality')

  let dailyPhrase = 'only a few daily needs within walking distance'
  if (typeof walkScore === 'number') {
    if (walkScore >= 70) dailyPhrase = 'many daily needs within a comfortable walk'
    else if (walkScore <= 30) dailyPhrase = 'very limited daily needs within walking distance'
  } else if (typeof bizCount === 'number') {
    if (bizCount >= 30) dailyPhrase = 'a strong cluster of shops and services within walking distance'
    else if (bizCount === 0) dailyPhrase = 'no shops or services within walking distance'
  }

  let centerPhrase = ''
  if (typeof townScore === 'number') {
    if (townScore >= 60) centerPhrase = ' and a lively nearby main street or town center'
    else if (townScore <= 30) centerPhrase = ' and no strong nearby main street or town center'
  }

  const locationSentence = `${placeLabel} offers ${dailyPhrase}${centerPhrase}.`
  const genericSentence =
    'Being able to walk to groceries, coffee, and everyday errands can cut down on driving, support routine movement, and help you feel more connected to your neighborhood.'

  return `${locationSentence} ${genericSentence}`
}

export function getActiveOutdoorsNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const daily = getPillarValue(pillar, 'breakdown.daily_urban_outdoors')
  const wild = getPillarValue(pillar, 'breakdown.wild_adventure')
  const water = getPillarValue(pillar, 'breakdown.waterfront_lifestyle')

  let dailyPhrase = 'some basic parks and green spaces for everyday use'
  if (typeof daily === 'number') {
    if (daily >= 70) dailyPhrase = 'strong access to parks and green spaces for daily walks and play'
    else if (daily <= 30) dailyPhrase = 'limited everyday parks and green spaces nearby'
  }

  let wildPhrase = ''
  if (typeof wild === 'number') {
    if (wild >= 70) wildPhrase = ' plus good options for trails and wilder areas on weekends'
    else if (wild <= 30) wildPhrase = ', but fewer options for bigger hikes or wild areas'
  }

  let waterPhrase = ''
  if (typeof water === 'number' && water >= 50) {
    waterPhrase = ' and easy access to water you can enjoy.'
  } else {
    waterPhrase = '.'
  }

  const locationSentence = `${placeLabel} has ${dailyPhrase}${wildPhrase}${waterPhrase}`
  const genericSentence =
    'Regular access to parks, trails, and water makes it easier to stay active and spend time in nature, which supports long-term physical and mental health.'

  return `${locationSentence} ${genericSentence}`
}

export function getHealthcareAccessNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const hospitalScore = getPillarValue(pillar, 'breakdown.breakdown.hospital_access')
  const hospitalCount = getPillarValue(pillar, 'summary.hospital_count')
  const primary = getPillarValue(pillar, 'breakdown.breakdown.primary_care')

  let accessPhrase = 'basic access to hospitals and clinics'
  if (typeof hospitalScore === 'number') {
    if (hospitalScore >= 70) accessPhrase = 'strong access to hospitals nearby'
    else if (hospitalScore <= 30) accessPhrase = 'more limited hospital access nearby'
  }

  let countPhrase = ''
  if (typeof hospitalCount === 'number') {
    if (hospitalCount >= 5) countPhrase = ', with several hospitals in reach'
    else if (hospitalCount <= 1) countPhrase = ', with few hospitals in reach'
  }

  let primaryPhrase = ''
  if (typeof primary === 'number') {
    if (primary >= 70) primaryPhrase = ' and many primary care options.'
    else if (primary <= 30) primaryPhrase = ' and fewer everyday doctors than expected.'
    else primaryPhrase = '.'
  } else {
    primaryPhrase = '.'
  }

  const locationSentence = `${placeLabel} has ${accessPhrase}${countPhrase}${primaryPhrase}`
  const genericSentence =
    'Living close to hospitals, clinics, and pharmacies makes it easier to handle emergencies, stay on top of checkups, and manage long-term conditions.'

  return `${locationSentence} ${genericSentence}`
}

export function getPublicTransitNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const heavy = getPillarValue(pillar, 'breakdown.breakdown.heavy_rail')
  const light = getPillarValue(pillar, 'breakdown.breakdown.light_rail')
  const bus = getPillarValue(pillar, 'breakdown.breakdown.bus')
  const nearestRailKm = getPillarValue(pillar, 'summary.nearest_heavy_rail_distance_km')

  let modePhrase = 'few useful transit options nearby'
  const scores = [heavy, light, bus].filter((n): n is number => typeof n === 'number')
  if (scores.length) {
    const avg = scores.reduce((a, b) => a + b, 0) / scores.length
    if (avg >= 70) modePhrase = 'strong rail or bus options within reach'
    else if (avg <= 30) modePhrase = 'very limited rail or bus options nearby'
  }

  let distancePhrase = ''
  if (typeof nearestRailKm === 'number') {
    if (nearestRailKm <= 1) distancePhrase = ', with a major rail stop within about a 10–15 minute walk.'
    else if (nearestRailKm <= 5) distancePhrase = ', with a major rail stop a short drive or longer walk away.'
    else distancePhrase = ', and major rail stations are farther away.'
  } else {
    distancePhrase = '.'
  }

  const locationSentence = `${placeLabel} has ${modePhrase}${distancePhrase}`
  const genericSentence =
    'Reliable transit can reduce the need for a car, cut commute stress, and expand your options for work, school, and social life.'

  return `${locationSentence} ${genericSentence}`
}

export function getAirTravelNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const airportName = getPillarString(pillar, 'primary_airport.name')
  const distanceKm = getPillarValue(pillar, 'summary.nearest_airport_km')
  const airportCount = getPillarValue(pillar, 'summary.airport_count')

  let accessPhrase = 'basic access to air travel'
  if (typeof distanceKm === 'number') {
    if (distanceKm <= 25) accessPhrase = 'very convenient access to a major airport'
    else if (distanceKm <= 60) accessPhrase = 'reasonable access to a major airport'
    else accessPhrase = 'a longer trip to reach a major airport'
  }

  let namePhrase = ''
  if (airportName) {
    namePhrase = ` via ${airportName}`
  }

  let countPhrase = ''
  if (typeof airportCount === 'number') {
    if (airportCount >= 2) countPhrase = ' and more than one airport within range.'
    else countPhrase = '.'
  } else {
    countPhrase = '.'
  }

  const locationSentence = `${placeLabel} offers ${accessPhrase}${namePhrase}${countPhrase}`
  const genericSentence =
    'Good airport access makes it easier to see family and friends, travel for work, and take trips without long drives on either end.'

  return `${locationSentence} ${genericSentence}`
}

export function getEconomicOpportunityNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const jobScore = getPillarValue(pillar, 'breakdown.base_score')
  const divisionRaw = getPillarString(pillar, 'summary.division')
  const divisionLabel = divisionRaw ? DIVISION_LABELS[divisionRaw] ?? divisionRaw : null

  let jobPhrase = 'a mixed local job market'
  if (typeof jobScore === 'number') {
    if (jobScore >= 70) jobPhrase = 'a strong local job market'
    else if (jobScore <= 30) jobPhrase = 'a weaker local job market'
  }

  let regionPhrase = ''
  if (divisionLabel) {
    regionPhrase = ` compared with other places in the ${divisionLabel}`
  }

  const locationSentence = `${placeLabel} has ${jobPhrase}${regionPhrase}.`
  const genericSentence =
    'A stronger local job market can make it easier to change roles, handle surprises, and stay rooted in one place if your work changes.'

  return `${locationSentence} ${genericSentence}`
}

export function getQualityEducationNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const avgRating = getPillarValue(pillar, 'summary.base_avg_rating')
  const totalSchools = getPillarValue(pillar, 'summary.total_schools_rated')
  const excellentCount = getPillarValue(pillar, 'summary.excellent_schools_count')

  let qualityPhrase = 'a mix of school options nearby'
  if (typeof avgRating === 'number') {
    if (avgRating >= 8) qualityPhrase = 'strong school options nearby overall'
    else if (avgRating <= 5) qualityPhrase = 'weaker school options nearby overall'
  }

  let countPhrase = ''
  if (typeof totalSchools === 'number') {
    if (totalSchools >= 10) countPhrase = `, with many schools in the area`
    else if (totalSchools <= 3) countPhrase = ', with fewer schools in the area'
  }

  let excellentPhrase = ''
  if (typeof excellentCount === 'number') {
    if (excellentCount >= 2) excellentPhrase = ' and several top-rated schools to choose from.'
    else if (excellentCount === 0) excellentPhrase = ' and no top-rated schools nearby.'
    else excellentPhrase = '.'
  } else {
    excellentPhrase = '.'
  }

  const locationSentence = `${placeLabel} has ${qualityPhrase}${countPhrase}${excellentPhrase}`
  const genericSentence =
    'Stronger nearby schools can support children’s learning, daily routines, and long-term opportunities, and often shape how families feel about a neighborhood.'

  return `${locationSentence} ${genericSentence}`
}

export function getHousingValueNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const affordability = getPillarValue(pillar, 'breakdown.breakdown.local_affordability')
  const space = getPillarValue(pillar, 'breakdown.breakdown.space')
  const medianValueRaw = getPillarValue(pillar, 'summary.median_home_value')

  let costPhrase = 'typical housing costs for the area'
  if (typeof affordability === 'number') {
    if (affordability >= 70) costPhrase = 'more manageable housing costs for the area'
    else if (affordability <= 30) costPhrase = 'higher housing costs relative to local incomes'
  }

  let spacePhrase = ''
  if (typeof space === 'number') {
    if (space >= 70) spacePhrase = ', with more space for the price than many places'
    else if (space <= 30) spacePhrase = ', with less space for the price than many places'
  }

  let pricePhrase = ''
  if (typeof medianValueRaw === 'number') {
    const medianValue = Math.round(medianValueRaw)
    pricePhrase = ` (typical home value around $${medianValue.toLocaleString()}).`
  } else {
    pricePhrase = '.'
  }

  const locationSentence = `${placeLabel} offers ${costPhrase}${spacePhrase}${pricePhrase}`
  const genericSentence =
    'Getting more space and quality for your housing budget can reduce financial stress and make it easier to stay put over the long run.'

  return `${locationSentence} ${genericSentence}`
}

export function getClimateRiskNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const floodTier = getPillarString(pillar, 'summary.flood_risk_tier')
  const heatScore = getPillarValue(pillar, 'breakdown.lst_score')
  const airScore = getPillarValue(pillar, 'breakdown.aqi_score')
  const trendScore = getPillarValue(pillar, 'breakdown.climate_trend_score_0_100')

  let floodPhrase = 'mixed flood risk'
  if (floodTier === 'minimal') floodPhrase = 'low flood risk'
  else if (floodTier === 'x_500yr' || floodTier === 'd') floodPhrase = 'moderate flood risk'
  else if (floodTier === 'sfha' || floodTier === 'floodway') floodPhrase = 'higher flood risk'

  let heatPhrase = 'moderate heat exposure'
  if (typeof heatScore === 'number') {
    if (heatScore <= 30) heatPhrase = 'relatively low heat exposure'
    else if (heatScore >= 70) heatPhrase = 'high heat exposure'
  }

  let airPhrase = 'mixed air quality'
  if (typeof airScore === 'number') {
    if (airScore >= 80) airPhrase = 'generally clean air'
    else if (airScore <= 40) airPhrase = 'frequent air-quality concerns'
  }

  let trendPhrase = 'projected to stay relatively stable over time'
  if (typeof trendScore === 'number') {
    if (trendScore >= 70) trendPhrase = 'projected to become more challenging over time'
    else if (trendScore >= 40) trendPhrase = 'projected to see some climate-related pressures over time'
  }

  const locationSentence = `${placeLabel} has ${floodPhrase}, ${airPhrase}, and ${heatPhrase}, and is ${trendPhrase}.`
  const genericSentence =
    'Lower exposure to flooding, extreme heat, and poor air quality reduces health risks, insurance costs, and disruption over time, which supports long-term livability and peace of mind.'

  return `${locationSentence} ${genericSentence}`
}

export function getSocialFabricNarrative(
  placeLabel: string,
  pillar: Record<string, unknown>
): string {
  const stabilityPct =
    getPillarValue(pillar, 'summary.stability_blend_pct') ?? getPillarValue(pillar, 'summary.same_house_pct')
  const civicCount =
    getPillarValue(pillar, 'summary.civic_node_count') ?? getPillarValue(pillar, 'summary.civic_node_count_800m') ?? 0
  const voterRate =
    getPillarValue(pillar, 'summary.voter_turnout_rate') ??
    getPillarValue(pillar, 'summary.voter_registration_rate')

  let stabilityPhrase = 'a mix of long-term and newer residents'
  if (typeof stabilityPct === 'number') {
    if (stabilityPct >= 70) stabilityPhrase = 'many long-term residents'
    else if (stabilityPct <= 40) stabilityPhrase = 'more frequent moves and shorter stays'
  }

  let engagementPhrase = 'some signs of civic engagement'
  if (typeof voterRate === 'number') {
    if (voterRate >= 0.8) engagementPhrase = 'strong civic engagement'
    else if (voterRate <= 0.4) engagementPhrase = 'lower civic engagement'
  }

  let civicPhrase =
    'even though we don’t detect formal civic places like libraries or community centers nearby.'
  if (typeof civicCount === 'number' && civicCount > 0) {
    civicPhrase = 'with civic places like libraries or community centers in the search area.'
  }

  const locationSentence = `In ${placeLabel}, there are ${stabilityPhrase} and ${engagementPhrase}, ${civicPhrase}`
  const genericSentence =
    'Stable neighbors, civic gathering spots, and engaged residents help build informal support, trust, and a stronger sense of belonging over time.'

  return `${locationSentence} ${genericSentence}`
}

export function getDiversityNarrative(placeLabel: string, pillar: Record<string, unknown>): string {
  const score = getPillarValue(pillar, 'summary.diversity_entropy_score')
  let mixPhrase = 'a moderate mix of households'
  if (typeof score === 'number') {
    if (score >= 70) mixPhrase = 'a wide mix of households across race, income, and age'
    else if (score <= 35) mixPhrase = 'a more uniform community profile'
  }
  const locationSentence = `${placeLabel} shows ${mixPhrase} in Census tract-level distributions.`
  const genericSentence =
    'Exposure to varied neighbors and life stages is one lens on everyday community texture—distinct from architecture or building style.'
  return `${locationSentence} ${genericSentence}`
}

export function getPillarNarrative(
  key: PillarKey,
  placeLabel: string,
  pillar: Record<string, unknown>
): string | null {
  switch (key) {
    case 'natural_beauty':
      return getNaturalBeautyNarrative(placeLabel, pillar)
    case 'built_beauty':
      return getBuiltBeautyNarrative(placeLabel, pillar)
    case 'neighborhood_amenities':
      return getNeighborhoodAmenitiesNarrative(placeLabel, pillar)
    case 'active_outdoors':
      return getActiveOutdoorsNarrative(placeLabel, pillar)
    case 'healthcare_access':
      return getHealthcareAccessNarrative(placeLabel, pillar)
    case 'public_transit_access':
      return getPublicTransitNarrative(placeLabel, pillar)
    case 'air_travel_access':
      return getAirTravelNarrative(placeLabel, pillar)
    case 'economic_security':
      return getEconomicOpportunityNarrative(placeLabel, pillar)
    case 'quality_education':
      return getQualityEducationNarrative(placeLabel, pillar)
    case 'housing_value':
      return getHousingValueNarrative(placeLabel, pillar)
    case 'climate_risk':
      return getClimateRiskNarrative(placeLabel, pillar)
    case 'social_fabric':
      return getSocialFabricNarrative(placeLabel, pillar)
    case 'diversity':
      return getDiversityNarrative(placeLabel, pillar)
    default:
      return null
  }
}

