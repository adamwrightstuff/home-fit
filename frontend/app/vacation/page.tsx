'use client';

import { useState } from 'react';
import Link from 'next/link';
import AppHeader from '@/components/AppHeader';
import LocationSearch from '@/components/LocationSearch';
import ScoreDisplay from '@/components/ScoreDisplay';
import ErrorMessage from '@/components/ErrorMessage';
import LoadingSpinner from '@/components/LoadingSpinner';
import ClimateProfileCard from '@/components/vacation/ClimateProfileCard';
import TripTypeSelector, { type TripType } from '@/components/vacation/TripTypeSelector';
import type { ScoreResponse } from '@/types/api';
import { getScore } from '@/lib/api';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const NB_PREF: Record<string, string> = {
  beach: '["ocean"]',
  mountain: '["mountains"]',
  road_trip: '["lakes_rivers"]',
};

export default function VacationPage() {
  const [tripType, setTripType] = useState<TripType | null>(null);
  const [travelMonth, setTravelMonth] = useState<number>(new Date().getMonth() + 1);
  const [loading, setLoading] = useState(false);
  const [scoreData, setScoreData] = useState<ScoreResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (location: string) => {
    if (!tripType) {
      setError('Please select a trip type first.');
      return;
    }
    setLoading(true);
    setError(null);
    setScoreData(null);

    try {
      const result = await getScore({
        location,
        mode: 'vacation',
        trip_type: tripType,
        travel_month: travelMonth,
        natural_beauty_preference: NB_PREF[tripType] ?? undefined,
      });
      setScoreData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not score that location.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setScoreData(null);
    setError(null);
  };

  return (
    <main className="hf-page">
      <AppHeader tagline="Score any destination for your next trip" />

      <div className="hf-container" style={{ maxWidth: 720 }}>

        {/* Entry form — hidden once results load */}
        {!scoreData && !loading && (
          <div className="hf-card" style={{ marginBottom: '1.5rem' }}>
            <h2 className="hf-section-title" style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>
              What kind of trip?
            </h2>
            <TripTypeSelector value={tripType} onChange={setTripType} />

            <div style={{ marginTop: '1.25rem' }}>
              <p className="hf-label" style={{ marginBottom: '0.5rem' }}>When are you going?</p>
              <div className="hf-chip-row" style={{ marginTop: 0, gap: '0.375rem' }}>
                {MONTH_NAMES.map((name, i) => {
                  const month = i + 1;
                  const active = travelMonth === month;
                  return (
                    <button
                      key={month}
                      onClick={() => setTravelMonth(month)}
                      className="hf-chip"
                      style={active ? {
                        background: 'var(--hf-hover-bg)',
                        borderColor: 'var(--hf-primary-1)',
                        color: 'var(--hf-primary-1)',
                        fontWeight: 600,
                      } : {}}
                    >
                      {name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div style={{ marginTop: '1.25rem' }}>
              <LocationSearch
                onSearch={handleSearch}
                disabled={!tripType}
                examples={['Sedona, AZ', 'Charleston, SC', 'Asheville, NC']}
              />
              {!tripType && (
                <p className="hf-helper" style={{ marginTop: '0.5rem' }}>
                  Select a trip type above to enable search.
                </p>
              )}
            </div>
          </div>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
            <LoadingSpinner />
            <p className="hf-helper" style={{ marginTop: '1rem' }}>
              Scoring 7 vacation pillars…
            </p>
          </div>
        )}

        {!loading && error && (
          <>
            <ErrorMessage message={error} />
            <button onClick={handleReset} className="hf-btn-secondary" style={{ marginTop: '1rem' }}>
              ← Try again
            </button>
          </>
        )}

        {!loading && scoreData && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <span style={{
                fontSize: '0.8125rem', fontWeight: 500,
                background: '#E0F2FE', color: '#0369A1',
                padding: '3px 12px', borderRadius: 10,
              }}>
                Vacation · {tripType?.replace('_', ' ')} · {MONTH_NAMES[travelMonth - 1]}
              </span>
              <button
                onClick={handleReset}
                className="hf-chip--ghost"
                style={{ fontSize: '0.8125rem' }}
              >
                ← New search
              </button>
            </div>

            {scoreData.climate_profile && (
              <div style={{ marginBottom: '1.5rem' }}>
                <ClimateProfileCard
                  profile={scoreData.climate_profile}
                  highlightMonth={travelMonth}
                />
              </div>
            )}

            <ScoreDisplay
              data={scoreData}
              readOnlyPriorities
              hideNotIncluded
              hideCompositeIndices
              searchOptions={null}
            />
          </>
        )}

        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <Link href="/search" className="hf-helper" style={{ textDecoration: 'none' }}>
            Looking to move? Try livability scoring →
          </Link>
        </div>
      </div>
    </main>
  );
}
