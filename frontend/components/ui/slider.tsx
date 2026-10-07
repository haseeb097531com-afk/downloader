'use client';

interface SliderProps {
  value: number[];
  onValueChange: (value: number[]) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
}

export function Slider({ value, onValueChange, min = 0, max = 100, step = 1, disabled }: SliderProps) {
  const percentage = ((value[0] - min) / (max - min)) * 100;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onValueChange([Number(e.target.value)]);
  };

  return (
    <div className="relative w-full h-2 bg-bg-tertiary rounded-full cursor-pointer">
      <div
        className="absolute h-full rounded-full bg-gradient-to-r from-accent-primary to-accent-secondary"
        style={{ width: `${percentage}%` }}
      />
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value[0]}
        onChange={handleChange}
        disabled={disabled}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
      />
      <div
        className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full shadow-lg border-2 border-accent-primary pointer-events-none"
        style={{ left: `calc(${percentage}% - 10px)` }}
      />
    </div>
  );
}

