'use client';
import { Profile } from '@/lib/api/profiles';
import { motion } from 'framer-motion';
import { Trash2, RefreshCw, ChevronRight } from 'lucide-react';
import Link from 'next/link';

export function ProfileCard({ profile, onDelete, onRescrape }: { profile: Profile; onDelete: (id: string) => void; onRescrape: (url: string) => void }) {
  return (
    <motion.div whileHover={{ scale: 1.02 }} className="glass-card p-4 rounded-xl flex flex-col gap-4 relative overflow-hidden group">
      <div className="flex items-center gap-4">
        <div className={`w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold bg-white/10 ${profile.platform}-glow`}>
          {profile.avatar_url ? <img src={profile.avatar_url} alt={profile.username} className="rounded-full w-full h-full object-cover" /> : profile.username.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white">{profile.display_name || profile.username}</h3>
          <p className="text-sm text-gray-400">@{profile.username}</p>
          <span className={`inline-block mt-1 text-xs px-2 py-1 rounded-full bg-white/5 border border-white/10`}>{profile.platform}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-center text-sm bg-black/20 rounded-lg p-2">
        <div><p className="text-gray-400 text-xs">Total Videos</p><p className="font-medium text-white">{profile.total_videos}</p></div>
        <div><p className="text-gray-400 text-xs">Auto Download</p><p className={`font-medium ${profile.auto_download ? 'text-green-400' : 'text-gray-500'}`}>{profile.auto_download ? 'ON' : 'OFF'}</p></div>
      </div>
      <div className="flex items-center justify-between mt-2">
        <p className="text-xs text-gray-500">Scraped: {profile.last_scraped_at ? new Date(profile.last_scraped_at).toLocaleDateString() : 'Never'}</p>
        <div className="flex gap-2">
          <button onClick={() => onRescrape(profile.profile_url)} className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition" title="Re-Scrape"><RefreshCw size={16} /></button>
          <button onClick={() => { if (confirm('Delete profile?')) onDelete(profile.id); }} className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-red-400 transition" title="Delete"><Trash2 size={16} /></button>
          <Link href={`/profiles/${profile.id}`} className="p-2 hover:bg-white/10 rounded-lg text-gray-400 hover:text-white transition" title="View Videos"><ChevronRight size={16} /></Link>
        </div>
      </div>
    </motion.div>
  );
}
