'use client';

export type TripType = 'beach' | 'mountain' | 'city' | 'road_trip';

const TRIP_TYPES: { value: TripType; label: string; icon: string; desc: string }[] = [
  { value: 'beach', label: 'Beach', icon: '🏖️', desc: 'Coast, sun, water' },
  { value: 'mountain', label: 'Mountain', icon: '🏔️', desc: 'Trails, peaks, skiing' },
  { value: 'city', label: 'City', icon: '🏙️', desc: 'Culture, food, nightlife' },
  { value: 'road_trip', label: 'Road Trip', icon: '🚗', desc: 'Parks, scenery, small towns' },
];

interface TripTypeSelectorProps {
  value: TripType | null;
  onChange: (v: TripType) => void;
}

export default function TripTypeSelector({ value, onChange }: TripTypeSelectorProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {TRIP_TYPES.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={[
            'flex flex-col items-center gap-1 rounded-xl border-2 px-3 py-4 text-sm font-medium transition-all',
            value === t.value
              ? 'border-blue-500 bg-blue-50 text-blue-700'
              : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50',
          ].join(' ')}
        >
          <span className="text-2xl">{t.icon}</span>
          <span className="font-semibold">{t.label}</span>
          <span className="text-xs text-gray-500">{t.desc}</span>
        </button>
      ))}
    </div>
  );
}
