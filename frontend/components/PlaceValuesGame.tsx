'use client'

import React, { useState } from 'react'
import { ChevronRight, MapPin, Home, Sparkles, RefreshCcw, Check } from 'lucide-react'
import type { PillarPriorities, PriorityLevel } from './SearchOptions'

const pillar_names = {
  active_outdoors: "Active Outdoors",
  built_beauty: "Built Beauty",
  natural_beauty: "Natural Beauty",
  neighborhood_amenities: "Neighborhood Amenities",
  air_travel_access: "Air Travel Access",
  public_transit_access: "Public Transit Access",
  healthcare_access: "Healthcare Access",
  quality_education: "Quality Education",
  housing_value: "Housing Value"
}

const pillar_descriptions = {
  active_outdoors: "You crave adventure and outdoor recreation—parks, trails, and water activities fuel your lifestyle.",
  built_beauty: "You appreciate architectural character and urban design—beautiful buildings and streetscapes matter to you.",
  natural_beauty: "You're drawn to natural landscapes—tree canopy, scenic views, and green spaces bring you joy.",
  neighborhood_amenities: "You value walkability and local vibrancy—coffee shops, restaurants, and daily conveniences nearby.",
  air_travel_access: "You need easy access to airports—whether for work or wanderlust, connectivity matters.",
  public_transit_access: "You prefer transit options—trains, buses, and rail make your life easier and more flexible.",
  healthcare_access: "You prioritize health access—hospitals, clinics, and medical facilities bring peace of mind.",
  quality_education: "You value strong schools and educational opportunities—for family or community quality.",
  housing_value: "You want space and value—affordability and getting more for your money are key priorities."
}

// Maximum possible points per pillar (audited across all 20 questions)
const max_possible_scores: Record<keyof PillarPriorities, number> = {
  active_outdoors: 43,
  built_beauty: 41,
  natural_beauty: 39,
  neighborhood_amenities: 60,
  air_travel_access: 22,
  public_transit_access: 20,
  healthcare_access: 23,
  quality_education: 32,
  housing_value: 45
}

const questions = [
  {
    id: 1,
    text: "It's Saturday morning. What sounds most appealing?",
    options: [
      { text: "Hiking a mountain trail with epic views", pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: "Wandering through a historic district with unique architecture", pillars: { built_beauty: 4 } },
      { text: "Browsing the farmers market and grabbing brunch at a local café", pillars: { neighborhood_amenities: 4 } },
      { text: "Staying in and enjoying a spacious, comfortable home", pillars: { housing_value: 4 } }
    ]
  },
  {
    id: 2,
    text: "Your ideal evening walk takes you past...",
    options: [
      { text: "Tree-lined streets with mature canopy and gardens", pillars: { natural_beauty: 4 } },
      { text: "Charming rowhouses with character and front porches", pillars: { built_beauty: 4 } },
      { text: "Bustling sidewalks with shops, restaurants, and street performers", pillars: { neighborhood_amenities: 4 } },
      { text: "A waterfront path with sunset views", pillars: { active_outdoors: 2, natural_beauty: 2 } }
    ]
  },
  {
    id: 3,
    text: "You're considering two neighborhoods. What's most reassuring?",
    options: [
      { text: "Top-rated hospital within 10 minutes", pillars: { healthcare_access: 5 } },
      { text: "Highly-rated schools and educational programs", pillars: { quality_education: 5 } },
      { text: "Beautiful tree-covered streets and nearby parks", pillars: { natural_beauty: 3, active_outdoors: 2 } },
      { text: "More space and lower cost per square foot", pillars: { housing_value: 5 } }
    ]
  },
  {
    id: 4,
    text: "You're offered two jobs with identical pay. One major difference:",
    options: [
      { text: "Job A: 15-min subway ride downtown", pillars: { public_transit_access: 4 } },
      { text: "Job B: 30-min scenic drive through nature", pillars: { natural_beauty: 2, active_outdoors: 2 } },
      { text: "Job C: 5-min walk from your front door", pillars: { neighborhood_amenities: 4 } },
      { text: "Job D: Remote, but near a major airport for frequent travel", pillars: { air_travel_access: 4 } }
    ]
  },
  {
    id: 5,
    text: "If you had kids (or have kids now), what matters most about where you live?",
    options: [
      { text: "Top-rated schools with excellent academics", pillars: { quality_education: 5 } },
      { text: "Safe streets where they can walk to friends' houses", pillars: { neighborhood_amenities: 5 } },
      { text: "Nearby parks, trails, and outdoor play spaces", pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: "A bigger, more affordable home with space to grow", pillars: { housing_value: 5 } }
    ]
  },
  {
    id: 6,
    text: "What's the biggest dealbreaker for a potential home?",
    options: [
      { text: "Poor school ratings in the district", pillars: { quality_education: 5 } },
      { text: "Far from hospitals and urgent care", pillars: { healthcare_access: 5 } },
      { text: "Cookie-cutter development with zero character", pillars: { built_beauty: 4, natural_beauty: 1 } },
      { text: "Nothing walkable—you'd need to drive everywhere", pillars: { neighborhood_amenities: 5 } }
    ]
  },
  {
    id: 7,
    text: "You've saved up for something special. What excites you most?",
    options: [
      { text: "A beautifully designed home with architectural details", pillars: { built_beauty: 4 } },
      { text: "A bigger place where everyone has their own space", pillars: { housing_value: 5 } },
      { text: "A home in a top school district", pillars: { quality_education: 5 } },
      { text: "A property backing onto nature trails or a park", pillars: { active_outdoors: 2, natural_beauty: 2 } }
    ]
  },
  {
    id: 8,
    text: "How do you feel about the cost of living where you want to be?",
    options: [
      { text: "I want maximum space and value for my budget", pillars: { housing_value: 5 } },
      { text: "I'll pay more for beautiful architecture and character", pillars: { built_beauty: 4 } },
      { text: "Affordability matters, but so does access to good schools", pillars: { housing_value: 3, quality_education: 2 } },
      { text: "I'll prioritize location over square footage", pillars: { neighborhood_amenities: 4 } }
    ]
  },
  {
    id: 9,
    text: "Your perfect weekend getaway is...",
    options: [
      { text: "A 2-hour drive to a national park", pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: "A quick flight to a new city to explore", pillars: { air_travel_access: 5 } },
      { text: "A train ride to a charming historic town", pillars: { public_transit_access: 3, built_beauty: 1 } },
      { text: "Actually, I love staying home—my neighborhood has everything", pillars: { neighborhood_amenities: 4 } }
    ]
  },
  {
    id: 10,
    text: "When you think about getting around and traveling, what's most important?",
    options: [
      { text: "Being near a major international airport", pillars: { air_travel_access: 5 } },
      { text: "Having comprehensive public transit (buses, trains, rail)", pillars: { public_transit_access: 5 } },
      { text: "Living close enough to walk to most places", pillars: { neighborhood_amenities: 4 } },
      { text: "Having scenic routes for driving and road trips", pillars: { natural_beauty: 3, active_outdoors: 1 } }
    ]
  },
  {
    id: 11,
    text: "What would make you feel instantly at home in a new place?",
    options: [
      { text: "Discovering a network of biking and hiking trails", pillars: { active_outdoors: 5 } },
      { text: "Finding excellent doctors and healthcare nearby", pillars: { healthcare_access: 5 } },
      { text: "A welcoming neighborhood with friendly local shops and cafes", pillars: { neighborhood_amenities: 5 } },
      { text: "Noticing tree-lined streets and parks everywhere", pillars: { natural_beauty: 5 } }
    ]
  },
  {
    id: 12,
    text: "Imagine your daily commute. What's ideal?",
    options: [
      { text: "A quick train or subway ride", pillars: { public_transit_access: 5 } },
      { text: "A 10-minute walk through my neighborhood", pillars: { neighborhood_amenities: 4 } },
      { text: "A scenic drive with nature views", pillars: { natural_beauty: 2, active_outdoors: 2 } },
      { text: "Working from home with occasional airport trips", pillars: { air_travel_access: 3 } }
    ]
  },
  {
    id: 13,
    text: "When you imagine your ideal view from your window...",
    options: [
      { text: "Mountains, hills, or dramatic natural landscapes", pillars: { natural_beauty: 3, active_outdoors: 1 } },
      { text: "A vibrant street scene with people and activity", pillars: { neighborhood_amenities: 4 } },
      { text: "Water—ocean, lake, or river", pillars: { active_outdoors: 2, natural_beauty: 2 } },
      { text: "Beautiful buildings and interesting architecture", pillars: { built_beauty: 4 } }
    ]
  },
  {
    id: 14,
    text: "A family member needs regular medical appointments. What setup works best?",
    options: [
      { text: "Multiple specialists and a major hospital nearby", pillars: { healthcare_access: 5 } },
      { text: "A reliable clinic within walking distance", pillars: { healthcare_access: 3, neighborhood_amenities: 2 } },
      { text: "Good transit connections to medical facilities", pillars: { healthcare_access: 3, public_transit_access: 2 } },
      { text: "Honestly, we'd drive wherever needed—proximity isn't critical", pillars: { housing_value: 3 } }
    ]
  },
  {
    id: 15,
    text: "How do you envision spending time with your family or future family?",
    options: [
      { text: "At great local schools and educational activities", pillars: { quality_education: 5 } },
      { text: "Exploring hiking trails and outdoor adventures", pillars: { active_outdoors: 3, natural_beauty: 1 } },
      { text: "In a spacious, affordable home with room to grow", pillars: { housing_value: 4 } },
      { text: "Walking to parks, cafes, and neighborhood events", pillars: { neighborhood_amenities: 4 } }
    ]
  },
  {
    id: 16,
    text: "What kind of recreational opportunities do you want nearby?",
    options: [
      { text: "Serious hiking, climbing, or mountain sports", pillars: { active_outdoors: 5 } },
      { text: "Cultural venues—theaters, museums, galleries", pillars: { neighborhood_amenities: 3, built_beauty: 2 } },
      { text: "Casual urban parks for walking and relaxation", pillars: { active_outdoors: 2, natural_beauty: 2 } },
      { text: "Historic sites and architecturally significant areas", pillars: { built_beauty: 4 } }
    ]
  },
  {
    id: 17,
    text: "You're house hunting. Which feature makes you say 'this is it'?",
    options: [
      { text: "It's near top-rated schools", pillars: { quality_education: 5 } },
      { text: "It's spacious and affordable with room to grow", pillars: { housing_value: 5 } },
      { text: "It backs onto a forest, park, or greenbelt", pillars: { natural_beauty: 3, active_outdoors: 1 } },
      { text: "It's in a neighborhood with stunning homes and streetscapes", pillars: { built_beauty: 4 } }
    ]
  },
  {
    id: 18,
    text: "When considering a place's connectivity, what matters most?",
    options: [
      { text: "Major airport within an hour—I travel frequently", pillars: { air_travel_access: 5 } },
      { text: "Excellent public transit network throughout the region", pillars: { public_transit_access: 5 } },
      { text: "Everything I need within a short drive—not necessarily walkable", pillars: { neighborhood_amenities: 4 } },
      { text: "Highway access for weekend trips to nature", pillars: { active_outdoors: 2, natural_beauty: 2 } }
    ]
  },
  {
    id: 19,
    text: "What aspect of a neighborhood's character speaks to you most?",
    options: [
      { text: "Architectural diversity and historic buildings", pillars: { built_beauty: 5 } },
      { text: "Tree canopy and natural green spaces", pillars: { natural_beauty: 5 } },
      { text: "Strong sense of community and local culture", pillars: { neighborhood_amenities: 4 } },
      { text: "Access to trails and outdoor recreation", pillars: { active_outdoors: 5 } }
    ]
  },
  {
    id: 20,
    text: "What's your non-negotiable when choosing where to live?",
    options: [
      { text: "Access to nature and outdoor activities", pillars: { active_outdoors: 3, natural_beauty: 2 } },
      { text: "Top-tier schools and educational opportunities", pillars: { quality_education: 5 } },
      { text: "Excellent healthcare facilities and medical access", pillars: { healthcare_access: 5 } },
      { text: "Excellent value and space for the price", pillars: { housing_value: 5 } }
    ]
  }
]

interface PlaceValuesGameProps {
  onApplyPriorities?: (priorities: PillarPriorities) => void
}

export default function PlaceValuesGame({ onApplyPriorities }: PlaceValuesGameProps) {
  const [game_state, set_game_state] = useState<'intro' | 'playing' | 'results'>('intro')
  const [current_question, set_current_question] = useState(0)
  const [scores, set_scores] = useState<Record<keyof PillarPriorities, number>>({
    active_outdoors: 0,
    built_beauty: 0,
    natural_beauty: 0,
    neighborhood_amenities: 0,
    air_travel_access: 0,
    public_transit_access: 0,
    healthcare_access: 0,
    quality_education: 0,
    housing_value: 0
  })

  const start_game = () => {
    set_game_state('playing')
    set_current_question(0)
    set_scores({
      active_outdoors: 0,
      built_beauty: 0,
      natural_beauty: 0,
      neighborhood_amenities: 0,
      air_travel_access: 0,
      public_transit_access: 0,
      healthcare_access: 0,
      quality_education: 0,
      housing_value: 0
    })
  }

  const handle_answer = (pillars: Partial<Record<keyof PillarPriorities, number>>) => {
    const new_scores = { ...scores }
    Object.keys(pillars).forEach(pillar => {
      const key = pillar as keyof PillarPriorities
      new_scores[key] = (new_scores[key] || 0) + (pillars[key] || 0)
    })
    set_scores(new_scores)
    if (current_question < questions.length - 1) {
      set_current_question(current_question + 1)
    } else {
      set_game_state('results')
    }
  }

  /**
   * Convert quiz scores to HomeFit priority levels.
   * Uses a combination of relative ranking and absolute percentage to ensure
   * good distribution that works with the HomeFit weight system.
   * 
   * HomeFit weight system:
   * - None = 0 weight (0% of tokens)
   * - Low = 1 weight
   * - Medium = 2 weight  
   * - High = 3 weight
   * 
   * Strategy:
   * 1. Calculate relative ranking (percentile) of scores
   * 2. Calculate absolute percentage of max possible score
   * 3. Combine both to assign priorities, ensuring top priorities get High/Medium
   */
  const convert_scores_to_priorities = (): PillarPriorities => {
    // Calculate score data for all pillars
    const pillar_data: Array<{ pillar: keyof PillarPriorities; score: number; percentage: number }> = []
    
    Object.keys(scores).forEach(pillar_key => {
      const pillar = pillar_key as keyof PillarPriorities
      const score = scores[pillar]
      const max_possible = max_possible_scores[pillar]
      const percentage = max_possible > 0 ? (score / max_possible) * 100 : 0
      pillar_data.push({ pillar, score, percentage })
    })

    // Sort by score (descending) for percentile calculation
    pillar_data.sort((a, b) => b.score - a.score)
    
    // Get non-zero scores
    const non_zero_pillars = pillar_data.filter(p => p.score > 0)
    
    // If all are zero, return all Medium (default balanced state)
    if (non_zero_pillars.length === 0) {
      const all_medium: PillarPriorities = {} as PillarPriorities
      Object.keys(pillar_names).forEach(key => {
        all_medium[key as keyof PillarPriorities] = 'Medium'
      })
      return all_medium
    }

    const priorities: PillarPriorities = {} as PillarPriorities
    
    // Assign priorities using combined percentile and percentage approach
    non_zero_pillars.forEach((item, index) => {
      const percentile_rank = (index + 1) / non_zero_pillars.length
      
      let priority: PriorityLevel
      
      // High: Top 33% by rank AND scored at least 25% of max possible
      // This ensures only pillars that scored reasonably well AND rank high get High
      if (percentile_rank <= 0.33 && item.percentage >= 25) {
        priority = 'High'
      }
      // Medium: Top 70% by rank OR scored 15-25% of max possible
      // Captures moderately important pillars
      else if (percentile_rank <= 0.70 || (item.percentage >= 15 && item.percentage < 25)) {
        priority = 'Medium'
      }
      // Low: Scored 5-15% of max possible, or in bottom 30% but still has some score
      else if (item.percentage >= 5 || item.score > 0) {
        priority = 'Low'
      }
      // None: Very low scores
      else {
        priority = 'None'
      }
      
      priorities[item.pillar] = priority
    })

    // Set zero-score pillars to None
    pillar_data.forEach(item => {
      if (item.score === 0) {
        priorities[item.pillar] = 'None'
      }
    })

    // Safety check: ensure all pillars have a priority
    Object.keys(pillar_names).forEach(key => {
      const pillar_key = key as keyof PillarPriorities
      if (!priorities[pillar_key]) {
        priorities[pillar_key] = 'None'
      }
    })

    // Ensure we have at least one High and one Medium for meaningful weighting
    // If no High, promote top scorer to High
    const has_high = Object.values(priorities).some(p => p === 'High')
    if (!has_high && non_zero_pillars.length > 0) {
      priorities[non_zero_pillars[0].pillar] = 'High'
    }

    return priorities
  }

  const get_importance_level = (pillar: keyof PillarPriorities, score: number): PriorityLevel => {
    if (score === 0) return 'None'
    const max = max_possible_scores[pillar] || 50
    const percentage = (score / max) * 100
    if (percentage <= 25) return 'Low'
    if (percentage <= 60) return 'Medium'
    return 'High'
  }

  const get_importance_color = (level: PriorityLevel) => {
    const colors = {
      'None': 'bg-gray-100 text-gray-500',
      'Low': 'bg-blue-100 text-blue-600',
      'Medium': 'bg-purple-100 text-purple-600',
      'High': 'bg-pink-100 text-pink-700 border border-pink-200'
    }
    return colors[level]
  }

  const get_all_pillars_with_levels = () => {
    const priorities = convert_scores_to_priorities()
    return Object.entries(scores)
      .map(([pillar, score]) => ({
        pillar: pillar as keyof PillarPriorities,
        score,
        priority: priorities[pillar as keyof PillarPriorities],
        display_level: get_importance_level(pillar as keyof PillarPriorities, score)
      }))
      .sort((a, b) => b.score - a.score)
  }

  const get_profile_summary = (sorted_pillars: ReturnType<typeof get_all_pillars_with_levels>) => {
    const top_pillars = sorted_pillars.filter(p => p.priority === 'High' || p.priority === 'Medium').slice(0, 3)
    if (top_pillars.length === 0) return "You're still exploring what matters most in a home."
    
    const names = top_pillars.map(p => pillar_names[p.pillar])
    const main_pillar = top_pillars[0]
    
    return `You prioritize **${names[0]}** above all else. Your ideal location isn't just a place to live, but a lifestyle choice where ${pillar_descriptions[main_pillar.pillar].toLowerCase().replace('you ', '')} 
    Furthermore, having strong access to **${names[1]}** ${top_pillars[2] ? `and **${names[2]}**` : ''} would make a neighborhood feel like a perfect match for your needs.`
  }

  const handle_apply_priorities = () => {
    const priorities = convert_scores_to_priorities()
    if (onApplyPriorities) {
      onApplyPriorities(priorities)
    }
  }

  if (game_state === 'intro') {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="max-w-xl w-full bg-white rounded-3xl shadow-sm border border-slate-200 p-10 text-center">
          <div className="w-16 h-16 bg-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-6 rotate-3">
            <MapPin className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-slate-900 mb-4 tracking-tight">Where You Belong</h1>
          <p className="text-slate-600 text-lg mb-8">Discover your unique "Place Values" profile through 20 quick scenarios.</p>
          <button onClick={start_game} className="w-full py-4 bg-slate-900 text-white rounded-xl font-bold text-lg hover:bg-slate-800 transition-all flex items-center justify-center gap-2">
            Start the Journey <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    )
  }

  if (game_state === 'playing') {
    const question = questions[current_question]
    const progress = ((current_question + 1) / questions.length) * 100
    return (
      <div className="min-h-screen bg-slate-50 p-6 flex flex-col items-center">
        <div className="max-w-2xl w-full">
          <div className="mb-8">
            <div className="flex justify-between text-sm font-bold text-slate-400 mb-2 uppercase tracking-widest">
              <span>Question {current_question + 1}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 w-full bg-slate-200 rounded-full">
              <div className="h-full bg-purple-600 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
          <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-8 md:p-12">
            <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-10 leading-snug">{question.text}</h2>
            <div className="space-y-3">
              {question.options.map((option, idx) => (
                <button
                  key={idx}
                  onClick={() => handle_answer(option.pillars)}
                  className="w-full text-left p-5 rounded-2xl border-2 border-slate-100 hover:border-purple-500 hover:bg-purple-50 transition-all group flex items-center gap-4"
                >
                  <span className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-500 group-hover:bg-purple-500 group-hover:text-white transition-colors">
                    {idx + 1}
                  </span>
                  <span className="text-slate-700 font-medium text-lg">{option.text}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (game_state === 'results') {
    const all_pillars = get_all_pillars_with_levels()
    const priorities = convert_scores_to_priorities()
    
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-8 md:p-12 mb-6">
            <div className="flex items-center gap-3 mb-6">
              <Sparkles className="w-8 h-8 text-purple-600" />
              <h1 className="text-3xl font-bold text-slate-900">Your Place Values</h1>
            </div>
            
            <div className="bg-purple-50 border border-purple-100 rounded-2xl p-6 mb-10">
              <p className="text-purple-900 leading-relaxed text-lg" dangerouslySetInnerHTML={{ __html: get_profile_summary(all_pillars).replace(/\*\*(.*?)\*\*/g, '<strong class="text-purple-700">$1</strong>') }} />
            </div>

            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-6">Detailed Breakdown</h3>
            <div className="grid md:grid-cols-2 gap-4 mb-8">
              {all_pillars.map(({ pillar, score, priority, display_level }) => (
                <div key={pillar} className="p-5 rounded-2xl border border-slate-100 bg-slate-50/50">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-slate-900">{pillar_names[pillar]}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-black px-2.5 py-1 rounded-lg uppercase tracking-wider ${get_importance_color(display_level)}`}>
                        {display_level}
                      </span>
                      <span className="text-xs text-slate-500">→ {priority}</span>
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 leading-relaxed mb-1">{pillar_descriptions[pillar]}</p>
                  <p className="text-xs text-slate-400">Score: {score}/{max_possible_scores[pillar]} → Priority: {priority}</p>
                </div>
              ))}
            </div>

            {onApplyPriorities && (
              <button 
                onClick={handle_apply_priorities}
                className="w-full py-4 bg-purple-600 text-white rounded-xl font-bold text-lg hover:bg-purple-700 transition-all flex items-center justify-center gap-2 mb-4"
              >
                <Check className="w-5 h-5" /> Apply These Priorities to Search
              </button>
            )}

            <button onClick={start_game} className="w-full py-4 border-2 border-slate-200 rounded-xl font-bold text-slate-600 hover:bg-slate-50 transition-all flex items-center justify-center gap-2">
              <RefreshCcw className="w-4 h-4" /> Reset Assessment
            </button>
          </div>
        </div>
      </div>
    )
  }
  
  return null
}

