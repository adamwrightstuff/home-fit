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
  High: {
    title: 'Vibrant Scene',
    body: 'A lot is going on within a short walk: many independent cafes, bars, restaurants, galleries, bookstores and theaters. Expect plenty to do close to home and busy streets.',
    detail: 'Based on the number of independent (non-chain) cafes, bars, restaurants, galleries, bookstores, record stores and theaters within about 0.75 miles, from OpenStreetMap. Vibrant is 71 or more, roughly the top 15% of places we score. It measures how much is going on, not what kind of places they are. The cut-offs are rough and not validated.',
  },
  Some: {
    title: 'Some Scene',
    body: 'There is enough local activity to give the area character, but it is not buzzing from block to block. You will find places to go without the constant energy of a major destination.',
    detail: 'Based on the number of independent (non-chain) cafes, bars, restaurants, galleries, bookstores, record stores and theaters within about 0.75 miles, from OpenStreetMap. Some is 13 to 70. The cut-offs are rough and not validated; places with few mapped venues can read lower than they feel.',
  },
  Low: {
    title: 'Quiet Area',
    body: 'This is mostly a place to live rather than a place people go out. Streets tend to be quieter, with few independent places to go nearby.',
    detail: 'Based on the number of independent (non-chain) cafes, bars, restaurants, galleries, bookstores, record stores and theaters within about 0.75 miles, from OpenStreetMap. Quiet is under 13. Places with few mapped venues can read lower than they feel.',
  },
}

export const AURA_COPY: InfoCopy = {
  title: 'Aura',
  body: 'Aura marks a neighborhood with a lot going on, a strong mix of independent cafes, bars and culture, and an affluent or elite resident profile. It is rare.',
  detail: 'A place gets Aura only if it has a Vibrant local scene (71 or more independent venues within about 0.75 miles), a high mix of independent culture and hangout venues compared with places of similar density, and a status class of Affluent or Elite. Job centers with more than five workers per resident are excluded. The cut-offs are rough judgments and not validated.',
}

export const INDEX_COPY: Record<string, InfoCopy> = {
  homefit: {
    title: 'HomeFit Score',
    body: 'The big picture: how well a neighborhood fits the things that matter most to everyday life. It brings 13 dimensions of livability into one score, from schools and safety to transit, nature, space, and local amenities.',
    detail: 'A weighted composite of 12 research-backed livability pillars using neighborhood-level data from sources including the Census, schools data, transit and mobility data, environmental datasets, and other public records.',
  },
  longevity: {
    title: 'Longevity',
    body: 'How many of the everyday conditions that health research links to longer lives this place has: social connection, outdoor activity, walkable amenities, clean air and moderate heat, safety, nature, and schools.',
    detail: 'A fixed-weight score inspired by Blue Zone research: social connection (largest weight), outdoor activity and green space, walkable amenities, air quality and heat exposure, community safety, natural beauty, and education. It describes the neighborhood, not a forecast of how long you will live. Healthcare access is not included.',
  },
  happiness: {
    title: 'Happiness',
    body: 'How likely the neighborhood is to make everyday life feel easier and more satisfying. It combines the practical things that shape daily experience, from commute and space to greenery, safety, and social connection.',
    detail: 'Based on commute burden, housing space, social fabric, access to green space, safety, and other neighborhood conditions associated with day-to-day wellbeing.',
  },
}
