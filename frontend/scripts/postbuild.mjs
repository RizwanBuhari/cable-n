// Runs after `vite build`:
//  * writes dist/<route>/index.html with the route's own <title>, description,
//    canonical URL and Open Graph tags (search engines and link previews get
//    correct metadata without server-side rendering);
//  * writes sitemap.xml, robots.txt and - when AdSense is configured - ads.txt.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadEnv } from 'vite'
import { ROUTES } from '../src/seo/routes.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const env = loadEnv('production', root, 'VITE_')
const site = (env.VITE_SITE_URL || 'http://localhost:8000').replace(/\/$/, '')
const dist = resolve(root, 'dist')
const template = readFileSync(resolve(dist, 'index.html'), 'utf8')
const esc = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')

for (const r of ROUTES) {
  const url = site + (r.path === '/' ? '/' : r.path)
  let html = template
    .replace(/<title>.*?<\/title>/s, `<title>${esc(r.title)}</title>`)
    .replace(/<meta name="description" content=".*?" \/>/, `<meta name="description" content="${esc(r.description)}" />`)
    .replace("</head>", `  <link rel="canonical" href="${url}" />
  </head>`)
    .replace(/<meta property="og:title" content=".*?" \/>/, `<meta property="og:title" content="${esc(r.title)}" />`)
    .replace(/<meta property="og:description" content=".*?" \/>/, `<meta property="og:description" content="${esc(r.description)}" />`)
    .replace(/<meta property="og:url" content=".*?" \/>/, `<meta property="og:url" content="${url}" />`)
    .replace(/<meta property="og:image" content=".*?" \/>/, `<meta property="og:image" content="${site}/brand/og-image.png" />`)
  const dir = r.path === '/' ? dist : resolve(dist, '.' + r.path)
  mkdirSync(dir, { recursive: true })
  writeFileSync(resolve(dir, 'index.html'), html)
}

const today = new Date().toISOString().slice(0, 10)
const urls = ROUTES.filter((r) => r.path !== '/settings').map((r) =>
  `  <url><loc>${site}${r.path === '/' ? '/' : r.path}</loc><lastmod>${today}</lastmod><priority>${r.priority.toFixed(1)}</priority></url>`)
writeFileSync(resolve(dist, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`)
writeFileSync(resolve(dist, 'robots.txt'), `User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: ${site}/sitemap.xml\n`)

const client = (env.VITE_ADSENSE_CLIENT || '').trim()
if (env.VITE_ADS_ENABLED === 'true' && /^ca-pub-\d{10,20}$/.test(client)) {
  writeFileSync(resolve(dist, 'ads.txt'), `google.com, ${client.replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n`)
  console.log('ads.txt written')
}
console.log(`postbuild: ${ROUTES.length} pre-rendered routes, sitemap.xml, robots.txt (site ${site})`)
