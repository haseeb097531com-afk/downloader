export const QUALITY_PRESETS = [
  { value: 'best', label: 'Best Available (source max)' },
  { value: '4320p', label: '8K Ultra HD (4320p)' },
  { value: '2160p', label: '4K Ultra HD (2160p)' },
  { value: '1440p', label: 'QHD (1440p)' },
  { value: '1080p', label: 'Full HD (1080p)' },
  { value: '720p', label: 'HD (720p)' },
  { value: '480p', label: 'SD (480p)' },
  { value: 'audio_only', label: 'Audio Only' },
] as const;

export type QualityPreset = typeof QUALITY_PRESETS[number]['value'];
