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
      const nbPref: Record<string, string> = {
        beach: '["ocean"]',
        mountain: '["mountains"]',
        road_trip: '["lakes_rivers"]',
      };
      const result = await getScore({
        location,
        mode: 'vacation',
        trip_type: tripType,
        travel_month: travelMonth,
        natural_beauty_preference: nbPref[tripType] ?? undefined,
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
        {/* Entry form */}
        <div className="hf-card" style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--hf-text-primary)' }}>
            What kind of trip?
          </h2>
          <TripTypeSelector value={tripType} onChange={setTripType} />

          <div style={{ marginTop: '1.25rem' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--hf-text-primary)', display: 'block', marginBottom: '0.5rem' }}>
              When are you going?
            </label>
            <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
              {MONTH_NAMES.map((name, i) => {
                const month = i + 1;
                return (
                  <button
                    key={month}
                    onClick={() => setTravelMonth(month)}
                    style={{
                      borderRadius: 8,
                      border: `1.5px solid ${travelMonth === month ? '#3B82F6' : '#E5E7EB'}`,
                      background: travelMonth === month ? '#EFF6FF' : '#fff',
                      color: travelMonth === month ? '#1D4ED8' : '#4B5563',
                      padding: '4px 10px',
                      fontSize: '0.8125rem',
                      fontWeight: travelMonth === month ? 600 : 400,
                      cursor: 'pointer',
                    }}
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
              disabled={loading || !tripType}
              examples={['Sedona, AZ', 'Charleston, SC', 'Asheville, NC']}
            />
            {!tripType && (
              <p style={{ fontSize: '0.8rem', color: 'var(--hf-text-secondary)', marginTop: '0.5rem' }}>
                Select a trip type above to enable search.
              </p>
            )}
          </div>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <LoadingSpinner />
            <p style={{ marginTop: '1rem', color: 'var(--hf-text-secondary)', fontSize: '0.875rem' }}>
              Scoring 7 vacation pillars…
            </p>
          </div>
        )}

        {!loading && error && <ErrorMessage message={error} />}

        {!loading && scoreData && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <span style={{ fontSize: '0.75rem', background: '#E0F2FE', color: '#0369A1', padding: '3px 10px', borderRadius: 10, fontWeight: 500 }}>
                Vacation · {tripType?.replace('_', ' ')} · {MONTH_NAMES[travelMonth - 1]}
              </span>
              <button
                onClick={handleReset}
                style={{ fontSize: '0.8rem', color: 'var(--hf-text-secondary)', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                ← New search
              </button>
            </div>

            {/* NOAA climate profile — descriptive, not scored */}
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
              searchOptions={null}
            />
          </>
        )}

        <div style={{ marginTop: '2rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--hf-text-secondary)' }}>
          <Link href="/search" style={{ color: 'var(--hf-text-secondary)' }}>
            Looking to move? Try livability scoring →
          </Link>
        </div>
      </div>
    </main>
  );
}
