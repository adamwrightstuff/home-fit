export interface InfoCopy {
  title: string
  body: string
  detail: string
}

export const ARCHETYPE_COPY: Record<string, InfoCopy> = {
  Elite: {
    title: 'Elite',
    body: 'A neighborhood with unusually high levels of income, education, and economic resources. It signals the social and economic character of the area, not whether it is better or worse.',
    detail: 'Based on neighborhood income, educational attainment, and other Census measures of economic and social composition.',
  },
  Affluent: {
    title: 'Affluent',
    body: 'A neighborhood with strong household incomes and educational attainment, but a broader economic mix than an elite area. It offers useful context about who lives here and the resources around them.',
    detail: 'Based on neighborhood income, educational attainment, and other Census measures of economic and social composition.',
  },
  'Middle Class': {
    title: 'Middle Class',
    body: 'A neighborhood centered around broadly middle-income households with a relatively balanced economic profile. It signals a conventional economic character rather than a judgment about quality of life.',
    detail: 'Based on neighborhood income, educational attainment, and other Census measures of economic and social composition.',
  },
  'Working Class': {
    title: 'Working Class',
    body: 'A neighborhood where working- and lower-middle-income households make up a larger share of the community. It can describe places that are stable, improving, or changing quickly.',
    detail: 'Based on neighborhood income, educational attainment, and other Census measures of economic and social composition.',
  },
  Struggling: {
    title: 'Struggling',
    body: 'A neighborhood where household incomes and educational attainment are substantially lower than the surrounding region. The label describes economic conditions, not the people who live there or the neighborhood\'s potential.',
    detail: 'Based on neighborhood income, educational attainment, and other Census measures of economic and social composition.',
  },
}

export const TRAJECTORY_COPY: Record<string, InfoCopy> = {
  'Up-and-Coming': {
    title: 'Real Estate · Up-and-Coming',
    body: 'This neighborhood is gaining real estate momentum, with rising values and growing demand. The market is still moving toward it rather than having already peaked.',
    detail: 'Based on recent home-value growth, demand, investment, development activity, and other indicators of increasing market momentum.',
  },
  Declining: {
    title: 'Real Estate · Declining',
    body: 'This neighborhood is losing demand or real estate value relative to its recent position. It may still have strong qualities, but the market is currently moving away from it.',
    detail: 'Based on changes in home values, demand, investment, development, and other indicators of declining market momentum.',
  },
  Stable: {
    title: 'Real Estate · Stable',
    body: 'This neighborhood\'s real estate market is holding steady without a meaningful upward or downward trend. Values are relatively predictable, with neither rapid appreciation nor notable decline.',
    detail: 'Based on home-value trends, demand, investment, and other indicators of market movement over time.',
  },
}

export const SCENE_COPY: Record<string, InfoCopy> = {
  buzzing: {
    title: 'Buzzing',
    body: 'A lot is going on within a short walk, and a good share of it is places to linger: independent cafes, bars, galleries, bookstores and theaters, not just restaurants.',
    detail: 'Based on the independent (non-chain) cafes, bars, restaurants, galleries, bookstores, record stores and theaters near the place, from OpenStreetMap. Buzzing means a strong mix of cafes, bars and culture venues compared with places of similar density, and 71 or more independent venues within about 0.75 miles. The cut-offs are rough and not validated.',
  },
  lively: {
    title: 'Lively',
    body: 'A real local scene at town or main-street scale: a strong mix of independent places to linger, with fewer places overall than a big downtown.',
    detail: 'Based on the independent (non-chain) cafes, bars, restaurants, galleries, bookstores, record stores and theaters near the place, from OpenStreetMap. Lively means a strong mix of cafes, bars and culture venues compared with places of similar density, with fewer than 71 independent venues within about 0.75 miles. Towns are measured across the whole town. The cut-offs are rough and not validated.',
  },
  low_key: {
    title: 'Flat',
    body: 'There are places to go, but compared with similar places more of them are restaurants, with fewer cafes, bars and culture venues. It can be busy without having much of a scene.',
    detail: 'Based on the independent (non-chain) cafes, bars, restaurants, galleries, bookstores, record stores and theaters near the place, from OpenStreetMap. Flat means 15 or more venues but a mix of cafes, bars and culture venues below what similar places have. The cut-offs are rough and not validated.',
  },
  quiet: {
    title: 'Sleepy',
    body: 'This is mostly a place to live rather than a place people go out. There are few places to go nearby.',
    detail: 'Based on the named cafes, bars, restaurants, galleries, bookstores, record stores and theaters near the place, from OpenStreetMap. Sleepy means fewer than 15 within the measured area. Places with few mapped venues can read lower than they feel. The cut-offs are rough and not validated.',
  },
}

export const AURA_COPY: InfoCopy = {
  title: 'Aura',
  body: 'Aura marks a neighborhood with a big local scene, a strong mix of independent cafes, bars and culture, and an affluent or elite resident profile. It is rare.',
  detail: 'A place gets Aura only if its Local Scene is Buzzing (a strong mix of independent cafes, bars and culture venues compared with places of similar density, and 71 or more independent venues within about 0.75 miles) and its status class is Affluent or Elite. Job centers with more than five workers per resident are excluded. The cut-offs are rough judgments and not validated.',
}

export const INDEX_COPY: Record<string, InfoCopy> = {
  homefit: {
    title: 'HomeFit Score',
    body: 'The big picture: how well a neighborhood fits the things that matter most to everyday life. It brings 13 dimensions of livability into one score, from schools and safety to transit, nature, space, and local amenities.',
    detail: 'A weighted composite of 12 research-backed livability pillars using neighborhood-level data from sources including the Census, schools data, transit and mobility data, environmental datasets, and other public records.',
  },
  happiness: {
    title: 'Happiness',
    body: 'How likely the neighborhood is to make everyday life feel easier and more satisfying. It combines the practical things that shape daily experience, from commute and space to greenery, safety, and social connection.',
    detail: 'Based on commute burden, housing space, social fabric, access to green space, safety, and other neighborhood conditions associated with day-to-day wellbeing.',
  },
}
