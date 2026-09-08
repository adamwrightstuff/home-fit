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
  Arrived: {
    title: 'Arrived',
    body: 'Established at the top of its market, this neighborhood is already highly desirable. Appreciation has slowed, but demand remains strong and the neighborhood\'s appeal is well established.',
    detail: 'Based on historical and recent home-value trends, demand, investment, and indicators of established neighborhood desirability.',
  },
  'Up-and-Coming': {
    title: 'Up-and-Coming',
    body: 'This neighborhood is gaining momentum, with rising values and growing demand. It is the kind of place where the market is still moving toward it rather than having already arrived.',
    detail: 'Based on recent home-value growth, demand, investment, development activity, and other indicators of increasing market momentum.',
  },
  Cooling: {
    title: 'Cooling',
    body: 'This neighborhood has come off a recent peak and is no longer moving upward as quickly. It remains desirable, but demand and appreciation are beginning to ease.',
    detail: 'Based on recent changes in home values and demand compared with longer-term trends, along with investment and development activity.',
  },
  Declining: {
    title: 'Declining',
    body: 'This neighborhood is losing demand or value relative to its recent position. It may still have strong qualities, but the market is currently moving away from it.',
    detail: 'Based on changes in home values, demand, investment, development, and other indicators of declining market momentum.',
  },
  Stable: {
    title: 'Stable',
    body: 'This neighborhood is holding steady without a meaningful upward or downward trend. Its market is relatively predictable, with neither rapid appreciation nor notable decline.',
    detail: 'Based on home-value trends, demand, investment, and other indicators of market movement over time.',
  },
}

export const SCENE_COPY: Record<string, InfoCopy> = {
  High: {
    title: 'Vibrant Scene',
    body: 'Independent restaurants, cafes, shops, and cultural spots create a lively neighborhood with plenty to do close to home. Expect more walkable streets, spontaneous activity, and a stronger local identity.',
    detail: 'Based on the concentration and diversity of independent restaurants, cafes, boutiques, cultural venues, and other experience-oriented businesses.',
  },
  Some: {
    title: 'Some Scene',
    body: 'There is enough local activity to give the neighborhood character, but it is not buzzing from block to block. You\'ll find places to go without the constant energy of a major neighborhood destination.',
    detail: 'Based on the concentration and diversity of independent restaurants, cafes, boutiques, cultural venues, and other experience-oriented businesses.',
  },
  Low: {
    title: 'Residential',
    body: 'This is primarily a place to live rather than a place people go for the local scene. Streets tend to be quieter, with fewer independent businesses and less pedestrian activity.',
    detail: 'Based on the concentration of independent restaurants, cafes, boutiques, cultural venues, and other experience-oriented businesses relative to the surrounding area.',
  },
}

export const AURA_COPY: InfoCopy = {
  title: 'Aura',
  body: 'A rare combination of status, local energy, and everyday livability. Only neighborhoods that stand out across all three dimensions earn the Aura distinction.',
  detail: 'Awarded only when a neighborhood ranks highly across economic status, independent local scene, and overall livability.',
}

export const INDEX_COPY: Record<string, InfoCopy> = {
  homefit: {
    title: 'HomeFit Score',
    body: 'The big picture: how well a neighborhood fits the things that matter most to everyday life. It brings 13 dimensions of livability into one score, from schools and safety to transit, nature, space, and local amenities.',
    detail: 'A weighted composite of 13 research-backed livability pillars using neighborhood-level data from sources including the Census, schools data, transit and mobility data, environmental datasets, and other public records.',
  },
  longevity: {
    title: 'Longevity',
    body: 'How well the neighborhood\'s environment supports a long, healthy life. It looks beyond healthcare to the everyday conditions associated with long-term health, including movement, nature, social connection, safety, and the built environment.',
    detail: 'Based on neighborhood conditions associated with longevity research, including physical activity, green space, social connection, safety, environmental quality, and access to health resources.',
  },
  happiness: {
    title: 'Happiness',
    body: 'How likely the neighborhood is to make everyday life feel easier and more satisfying. It combines the practical things that shape daily experience, from commute and space to greenery, safety, and social connection.',
    detail: 'Based on commute burden, housing space, social fabric, access to green space, safety, and other neighborhood conditions associated with day-to-day wellbeing.',
  },
}
