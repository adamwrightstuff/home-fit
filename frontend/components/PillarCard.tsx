'use client'

import { useState } from 'react'
import { LivabilityPillar } from '@/types/api'

interface PillarCardProps {
  name: string
  description: string
  pillar: LivabilityPillar
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-homefit-score-high bg-homefit-score-high/10'
  if (score >= 60) return 'text-homefit-score-mid bg-homefit-score-mid/10'
  return 'text-homefit-score-low bg-homefit-score-low/10'
}

export default function PillarCard({ name, description, pillar }: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <h3 className="font-semibold text-homefit-text-primary text-lg">{name}</h3>
          <p className="text-sm text-homefit-text-secondary mt-1">{description}</p>
        </div>
        <div className={`ml-4 px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(pillar.score)}`}>
          {pillar.score.toFixed(1)}
        </div>
      </div>

      <div className="mt-3 text-xs text-homefit-text-secondary opacity-75 space-y-1">
        <div className="flex justify-between">
          <span>Weight:</span>
          <span className="font-medium">{pillar.weight.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span>Contribution:</span>
          <span className="font-medium">{pillar.contribution.toFixed(1)}</span>
        </div>
        <div className="flex justify-between">
          <span>Confidence:</span>
          <span className="font-medium">{pillar.confidence.toFixed(0)}%</span>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-3 text-sm text-homefit-accent-primary hover:opacity-80 font-medium"
      >
        {expanded ? 'Hide' : 'Show'} Details
      </button>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-200 space-y-2 text-xs">
          {pillar.summary && Object.keys(pillar.summary).length > 0 && (
            <div>
              <p className="font-semibold text-homefit-text-primary mb-1">Summary:</p>
              <div className="text-homefit-text-secondary space-y-2">
                {Object.entries(pillar.summary).map(([key, value]) => {
                  // Handle nested objects (like Active Outdoors summary)
                  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    return (
                      <div key={key} className="space-y-0.5">
                        <span className="font-medium capitalize text-homefit-text-primary">
                          {key.replace(/_/g, ' ')}:
                        </span>
                        <div className="ml-2 space-y-0.5">
                          {Object.entries(value).map(([subKey, subValue]) => (
                            <div key={subKey} className="flex justify-between text-homefit-text-secondary">
                              <span className="capitalize">{subKey.replace(/_/g, ' ')}:</span>
                              <span className="font-medium">
                                {typeof subValue === 'number'
                                  ? subValue % 1 === 0
                                    ? subValue.toString()
                                    : subValue.toFixed(2)
                                  : subValue === null || subValue === undefined
                                  ? 'N/A'
                                  : String(subValue)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  }
                  // Handle simple values (numbers, strings)
                  return (
                    <div key={key} className="flex justify-between">
                      <span className="capitalize">{key.replace(/_/g, ' ')}:</span>
                      <span className="font-medium">
                        {typeof value === 'number'
                          ? value % 1 === 0
                            ? value.toString()
                            : value.toFixed(2)
                          : value === null || value === undefined
                          ? 'N/A'
                          : String(value)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          <div>
            <p className="font-semibold text-homefit-text-primary mb-1">Data Quality:</p>
            <p className="text-homefit-text-secondary capitalize">
              {pillar.data_quality.quality_tier || 'Unknown'}
            </p>
          </div>
          
          {/* NEW: Natural Beauty specific metrics */}
          {name === 'Natural Beauty' && pillar.summary && (
            <div className="space-y-3 mt-3 pt-3 border-t border-gray-200">
              {/* Landscape Context Tags */}
              {Array.isArray(pillar.summary.landscape_context) && pillar.summary.landscape_context.length > 0 && (
                <div>
                  <p className="font-semibold text-homefit-text-primary mb-1">Landscape Setting:</p>
                  <div className="flex flex-wrap gap-1">
                    {pillar.summary.landscape_context.map((tag: string, idx: number) => (
                      <span 
                        key={idx}
                        className="inline-block px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-homefit-text-secondary mt-1 italic">
                    The Natural Beauty score adapts to different landscapes. For example, mountain areas emphasize terrain and views, while urban areas prioritize greenery and parks.
                  </p>
                </div>
              )}
              
              {/* Data Coverage Indicator */}
              {pillar.summary.data_coverage_tier && (
                <div>
                  <p className="font-semibold text-homefit-text-primary mb-1">Data Coverage:</p>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                    pillar.summary.data_coverage_tier === 'high' 
                      ? 'bg-green-100 text-green-800'
                      : pillar.summary.data_coverage_tier === 'medium'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {pillar.summary.data_coverage_tier.toUpperCase()}
                    {pillar.summary.data_coverage_pct && ` (${pillar.summary.data_coverage_pct}%)`}
                  </span>
                </div>
              )}
              
              {/* Greenery Section */}
              {(pillar.summary.neighborhood_canopy_pct || pillar.summary.green_view_index || pillar.summary.local_green_score) && (
                <div>
                  <p className="font-semibold text-homefit-text-primary mb-1">🌳 Greenery:</p>
                  <div className="text-homefit-text-secondary space-y-0.5">
                    {pillar.summary.neighborhood_canopy_pct !== undefined && (
                      <div className="flex justify-between">
                        <span>Neighborhood Canopy:</span>
                        <span className="font-medium">{pillar.summary.neighborhood_canopy_pct}%</span>
                      </div>
                    )}
                    {pillar.summary.local_canopy_pct !== undefined && (
                      <div className="flex justify-between">
                        <span>Local Canopy:</span>
                        <span className="font-medium">{pillar.summary.local_canopy_pct}%</span>
                      </div>
                    )}
                    {pillar.summary.green_view_index !== undefined && (
                      <div className="flex justify-between">
                        <span>Green View Index:</span>
                        <span className="font-medium">{pillar.summary.green_view_index.toFixed(1)}</span>
                      </div>
                    )}
                    {pillar.summary.local_green_score !== undefined && (
                      <div className="flex justify-between">
                        <span>Local Green Spaces:</span>
                        <span className="font-medium">{pillar.summary.local_green_score.toFixed(1)}</span>
                      </div>
                    )}
                    {pillar.summary.visible_green_fraction !== undefined && (
                      <div className="flex justify-between">
                        <span>Visible Green:</span>
                        <span className="font-medium">{pillar.summary.visible_green_fraction}%</span>
                      </div>
                    )}
                    {pillar.summary.street_level_ndvi !== undefined && (
                      <div className="flex justify-between">
                        <span>Street-Level NDVI:</span>
                        <span className="font-medium">{pillar.summary.street_level_ndvi}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Terrain & Views Section */}
              {(pillar.summary.terrain_relief_m || pillar.summary.terrain_prominence_m || pillar.summary.terrain_ruggedness_m || pillar.summary.visible_natural_pct) && (
                <div>
                  <p className="font-semibold text-homefit-text-primary mb-1">⛰️ Terrain & Views:</p>
                  <div className="text-homefit-text-secondary space-y-0.5">
                    {pillar.summary.terrain_relief_m && (
                      <div className="flex justify-between">
                        <span>Relief:</span>
                        <span className="font-medium">{pillar.summary.terrain_relief_m}m</span>
                      </div>
                    )}
                    {pillar.summary.terrain_prominence_m && (
                      <div className="flex justify-between">
                        <span>Prominence:</span>
                        <span className="font-medium">{pillar.summary.terrain_prominence_m}m</span>
                      </div>
                    )}
                    {pillar.summary.terrain_ruggedness_m && (
                      <div className="flex justify-between">
                        <span>Ruggedness:</span>
                        <span className="font-medium">{pillar.summary.terrain_ruggedness_m}m</span>
                      </div>
                    )}
                    {pillar.summary.visible_natural_pct !== undefined && (
                      <div className="flex justify-between">
                        <span>Visible Natural:</span>
                        <span className="font-medium">{pillar.summary.visible_natural_pct}%</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Water & Landcover Section */}
              {(pillar.summary.water_proximity_km || pillar.summary.water_proximity_type) && (
                <div>
                  <p className="font-semibold text-homefit-text-primary mb-1">💧 Water & Landcover:</p>
                  <div className="text-homefit-text-secondary space-y-0.5">
                    {pillar.summary.water_proximity_km && (
                      <div className="flex justify-between">
                        <span>Nearest {pillar.summary.water_proximity_type || 'waterbody'}:</span>
                        <span className="font-medium">{pillar.summary.water_proximity_km}km</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Eye-Level Greenery - Add to Greenery section if not already there */}
              {(pillar.summary.visible_green_fraction || pillar.summary.street_level_ndvi) && 
               (!pillar.summary.neighborhood_canopy_pct && !pillar.summary.green_view_index && !pillar.summary.local_green_score) && (
                <div>
                  <p className="font-semibold text-homefit-text-primary mb-1">🌳 Greenery:</p>
                  <div className="text-homefit-text-secondary space-y-0.5">
                    {pillar.summary.visible_green_fraction && (
                      <div className="flex justify-between">
                        <span>Visible Green:</span>
                        <span className="font-medium">{pillar.summary.visible_green_fraction}%</span>
                      </div>
                    )}
                    {pillar.summary.street_level_ndvi && (
                      <div className="flex justify-between">
                        <span>Street-Level NDVI:</span>
                        <span className="font-medium">{pillar.summary.street_level_ndvi}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {/* Debug Breakdown - Context Bonus Calculation */}
              {pillar.details?.context_bonus?.debug_breakdown && (
                <div className="mt-3 pt-3 border-t border-gray-300">
                  <p className="font-semibold text-homefit-text-primary mb-2 text-xs">🔍 Debug: Context Bonus Breakdown</p>
                  <div className="text-homefit-text-secondary space-y-1.5 text-xs">
                    <div className="flex justify-between">
                      <span>Area Type:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.area_type_key || 'unknown'}</span>
                    </div>
                    {Array.isArray(pillar.details.context_bonus.debug_breakdown.landscape_tags) && 
                     pillar.details.context_bonus.debug_breakdown.landscape_tags.length > 0 && (
                      <div className="flex justify-between">
                        <span>Landscape Tags:</span>
                        <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.landscape_tags.join(', ')}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span>Topography Raw:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.topography_raw?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Topography Final:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.topography_final?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Landcover Raw:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.landcover_raw?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Landcover Final:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.landcover_final?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Water Raw:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.water_raw?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Water Final:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.water_final?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Viewshed Bonus:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.viewshed?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Water Proximity Available:</span>
                      <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.water_proximity_available ? 'Yes' : 'No'}</span>
                    </div>
                    {pillar.details.context_bonus.debug_breakdown.water_proximity_nearest_km !== null && pillar.details.context_bonus.debug_breakdown.water_proximity_nearest_km !== undefined && (
                      <div className="flex justify-between">
                        <span>Nearest Water (km):</span>
                        <span className="font-medium">{pillar.details.context_bonus.debug_breakdown.water_proximity_nearest_km?.toFixed(2)}</span>
                      </div>
                    )}
                    <div className="mt-2 pt-2 border-t border-gray-200">
                      <div className="flex justify-between font-semibold">
                        <span>Total Context Bonus:</span>
                        <span className="font-bold">{pillar.details.context_bonus.total_bonus?.toFixed(2) || pillar.summary.context_bonus?.toFixed(2) || '0'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
