'use client';
import { Profile } from '@/lib/api/profiles';
import { QUALITY_PRESETS } from '@/lib/constants/quality-presets';
import { RefreshCw } from 'lucide-react';
import { useProfileStore } from '@/lib/store/profiles';

export function ProfileHeader({ profile }: { profile: Profile }) {
  const { startScrape, qualityPreference, setQuality } = useProfileStore();

  return (
    <div className="glass-card p-6 rounded-2xl border border-white/5 flex flex-col md:flex-row gap-6 items-start md:items-center relative overflow-hidden">
      <div className={`w-24 h-24 rounded-full flex items-center justify-center text-3xl font-bold bg-white/10 ${profile.platform}-glow shrink-0`}>
        {profile.avatar_url ? <img src={profile.avatar_url} alt={profile.username} className="rounded-full w-full h-full object-cover" /> : profile.username.charAt(0).toUpperCase()}
      </div>
      <div className="flex-1">
        <h1 className="text-3xl font-bold text-white mb-1">{profile.display_name || profile.username}</h1>
        <div className="flex items-center gap-3">
          <p className="text-gray-400 text-sm">@{profile.username}</p>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full bg-white/10 border border-white/20 text-${profile.platform}`}>{profile.platform}</span>
        </div>
        <div className="flex gap-6 mt-4">
          <div><p className="text-gray-500 text-xs uppercase tracking-wider mb-1">Total Videos</p><p className="text-xl font-medium text-white">{profile.total_videos}</p></div>
        </div>
      </div>
      <div className="flex flex-col gap-3 min-w-[200px] w-full md:w-auto">
        <select value={qualityPreference} onChange={(e) => setQuality(e.target.value)} className="bg-black/40 border border-white/10 text-white text-sm rounded-lg p-2.5 focus:ring-blue-500 focus:border-blue-500 w-full outline-none">
          {QUALITY_PRESETS.map(q => (
            <option key={q.value} value={q.value}>{q.label}</option>
          ))}
        </select>
        <button onClick={() => startScrape(profile.profile_url, 50)} className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-white px-4 py-2.5 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition">
          <RefreshCw size={16} /> Re-Scrape Profile
        </button>
      </div>
    </div>
  );
}
