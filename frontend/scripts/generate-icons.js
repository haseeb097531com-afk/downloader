import sharp from 'sharp';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const outDir = join(process.cwd(), 'public', 'icons');
mkdirSync(outDir, { recursive: true });

const gradient = {
  left: '#6C5CE7',
  right: '#00D2FF',
};

const svg = (size: number) => `
<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="${gradient.left}" />
      <stop offset="100%" stop-color="${gradient.right}" />
    </linearGradient>
  </defs>
  <rect width="${size}" height="${size}" rx="${size * 0.2}" fill="url(#bg)" />
  <g transform="translate(${size * 0.35}, ${size * 0.3}) scale(${size * 0.003})">
    <path d="M12 2L12 14M12 14L6 8M12 14L18 8" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </g>
</svg>`;

async function main() {
  const sizes = [192, 512];
  for (const size of sizes) {
    const svgStr = svg(size);
    const buf = Buffer.from(svgStr);
    await sharp(buf)
      .png()
      .resize(size, size, { fit: 'contain', background: { r: 10, g: 10, b: 15, alpha: 1 } })
      .toFile(join(outDir, `icon-${size}.png`));
    console.log(`Generated icon-${size}.png`);
  }
}

main().catch((e) => {
  console.error('Icon generation failed. Using static placeholders instead.', e);
  writeFileSync(join(outDir, 'icon-192.png'), Buffer.from('placeholder'));
  writeFileSync(join(outDir, 'icon-512.png'), Buffer.from('placeholder'));
  console.log('Wrote placeholder icon files. Replace with real PNGs before production.');
  process.exit(0);
});
