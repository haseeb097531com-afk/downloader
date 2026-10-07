export function getPlatformFromUrl(url: string): string {
  const lowerUrl = url.toLowerCase();
  if (lowerUrl.includes('youtube.com') || lowerUrl.includes('youtu.be')) return 'youtube';
  if (lowerUrl.includes('tiktok.com') || lowerUrl.includes('vm.tiktok.com')) return 'tiktok';
  if (lowerUrl.includes('instagram.com')) return 'instagram';
  if (lowerUrl.includes('facebook.com') || lowerUrl.includes('fb.watch')) return 'facebook';
  if (lowerUrl.includes('twitter.com') || lowerUrl.includes('x.com')) return 'twitter';
  return 'other';
}

export function isProfileUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.toLowerCase();
    const platform = getPlatformFromUrl(url);

    if (platform === 'youtube') {
      return path.startsWith('/@') || path.startsWith('/c/') || path.startsWith('/channel/') || path.startsWith('/user/');
    }
    if (platform === 'tiktok') {
      return path.startsWith('/@') && !path.includes('/video/');
    }
    if (platform === 'instagram') {
      const parts = path.split('/').filter(Boolean);
      return parts.length === 1 && !['p', 'reel', 'tv', 'stories', 'explore'].includes(parts[0]);
    }
    if (platform === 'twitter') {
      const parts = path.split('/').filter(Boolean);
      return parts.length === 1 && !['home', 'explore', 'notifications', 'messages'].includes(parts[0]);
    }
    if (platform === 'facebook') {
      const parts = path.split('/').filter(Boolean);
      return parts.length === 1 && !['watch', 'reel', 'videos', 'story'].includes(parts[0]);
    }
  } catch {
    return false;
  }
  return false;
}
