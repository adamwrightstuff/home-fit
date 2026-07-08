'use client';

import type { ClimateProfile } from '@/types/api';

const COMFORT_COLORS: Record<string, string> = {
  hot: 'bg-red-100 text-red-700',
  warm: 'bg-orange-100 text-orange-700',
  warm_wet: 'bg-amber-100 text-amber-700',
  pleasant: 'bg-green-100 text-green-700',
  mild_wet: 'bg-teal-100 text-teal-700',
  cool: 'bg-blue-100 text-blue-700',
  cold: 'bg-indigo-100 text-indigo-700',
  unknown: 'bg-gray-100 text-gray-500',
};

const COMFORT_LABELS: Record<string, string> = {
  hot: 'Hot',
  warm: 'Warm',
  warm_wet: 'Warm & Wet',
  pleasant: 'Pleasant',
  mild_wet: 'Mild & Rainy',
  cool: 'Cool',
  cold: 'Cold',
  unknown: '—',
};

interface ClimateProfileCardProps {
  profile: ClimateProfile;
  highlightMonth?: number | null;
}

export default function ClimateProfileCard({ profile, highlightMonth }: ClimateProfileCardProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-base font-semibold text-gray-900">Climate</h3>
        <span className="text-xs text-gray-400">{profile.normals_period} normals</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400">
              <th className="pb-2 pr-3 font-medium">Month</th>
              <th className="pb-2 pr-3 font-medium text-right">High</th>
              <th className="pb-2 pr-3 font-medium text-right">Low</th>
              <th className="pb-2 pr-3 font-medium text-right">Rain</th>
              <th className="pb-2 font-medium">Feel</th>
            </tr>
          </thead>
          <tbody>
            {profile.months.map((m) => {
              const isHighlight = highlightMonth === m.month;
              return (
                <tr
                  key={m.month}
                  className={[
                    'border-t border-gray-100',
                    isHighlight ? 'bg-blue-50' : '',
                  ].join(' ')}
                >
                  <td className="py-1.5 pr-3 font-medium text-gray-700">
                    {isHighlight ? <strong>{m.month_name}</strong> : m.month_name}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-700">
                    {m.avg_high_f != null ? `${m.avg_high_f}°` : '—'}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-500">
                    {m.avg_low_f != null ? `${m.avg_low_f}°` : '—'}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-gray-500">
                    {m.avg_precip_in != null ? `${m.avg_precip_in}"` : '—'}
                  </td>
                  <td className="py-1.5">
                    <span
                      className={[
                        'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
                        COMFORT_COLORS[m.comfort] ?? COMFORT_COLORS.unknown,
                      ].join(' ')}
                    >
                      {COMFORT_LABELS[m.comfort] ?? m.comfort}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
