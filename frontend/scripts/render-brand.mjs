// Renders brand PNGs (OG image, touch icon, PDF logo) and an optional preview
// sheet from the SVGs using headless Chromium (Playwright).
// Run from frontend/:  node scripts/render-brand.mjs [--preview <out.png>]
import { chromium } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pub = resolve(here, '../public')
const b = (f) => readFileSync(resolve(pub, 'brand', f), 'utf8')
const font = readFileSync(resolve(here, '../node_modules/@fontsource/montserrat/files/montserrat-latin-700-normal.woff2')).toString('base64')
const font5 = readFileSync(resolve(here, '../node_modules/@fontsource/montserrat/files/montserrat-latin-500-normal.woff2')).toString('base64')
const css = `@font-face{font-family:M;font-weight:700;src:url(data:font/woff2;base64,${font})}
@font-face{font-family:M;font-weight:500;src:url(data:font/woff2;base64,${font5})}
body{margin:0;font-family:M,sans-serif}`

const browser = await chromium.launch()
const page = await browser.newPage({ deviceScaleFactor: 1 })
async function shot(html, w, h, out, transparent = false) {
  await page.setViewportSize({ width: w, height: h })
  await page.setContent(`<style>${css}</style>${html}`)
  await page.waitForTimeout(150)
  const buf = await page.screenshot({ omitBackground: transparent, clip: { x: 0, y: 0, width: w, height: h } })
  writeFileSync(out, buf)
}

await shot(`<div style="width:1200px;height:630px;background:#F4F5F6;position:relative;overflow:hidden">
 <div style="position:absolute;inset:0 0 auto 0;height:14px;background:#CE1B28"></div>
 <div style="position:absolute;left:90px;top:150px">${b('cable-n-logo-full.svg').replace('<svg ', '<svg style="width:760px;height:auto" ')}</div>
 <div style="position:absolute;left:96px;top:360px;font-size:30px;font-weight:500;color:#333;max-width:900px;line-height:1.4">
 Free online cable sizing: single feeders, batch cable schedules, duct-bank current-rating checks and full IEC 60287 / 60949 MV-HV analysis.</div>
 <div style="position:absolute;right:-120px;bottom:-120px;opacity:.07">${b('cable-n-icon-mono-dark.svg').replace('<svg ', '<svg style="width:520px;height:520px" ')}</div>
</div>`, 1200, 630, resolve(pub, 'brand/og-image.png'))

await shot(`<div style="width:180px;height:180px;background:#fff;display:grid;place-items:center">${b('cable-n-icon.svg').replace('<svg ', '<svg style="width:150px;height:150px" ')}</div>`, 180, 180, resolve(pub, 'apple-touch-icon.png'))
for (const s of [192, 512]) {
  await shot(`<div style="width:${s}px;height:${s}px;display:grid;place-items:center">${b('cable-n-icon.svg').replace('<svg ', `<svg style="width:${s}px;height:${s}px" `)}</div>`, s, s, resolve(pub, `brand/icon-${s}.png`), true)
}
const logo = b('cable-n-logo.svg'); const vb = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(logo)
const lw = Math.round(+vb[1] * 6), lh = Math.round(+vb[2] * 6)
await shot(`<div style="width:${lw}px;height:${lh}px">${logo.replace('<svg ', `<svg style="width:${lw}px;height:${lh}px" `)}</div>`, lw, lh, resolve(pub, 'brand/cable-n-logo.png'), true)

const i = process.argv.indexOf('--preview')
if (i > 0) {
  const tile = (f, bg) => `<div style="background:${bg};padding:28px;border-radius:12px;display:flex;align-items:center;justify-content:center;min-height:120px">${b(f).replace('<svg ', '<svg style="max-width:100%;height:auto" ')}</div>`
  await shot(`<div style="width:1100px;padding:30px;background:#e9eaec;display:grid;grid-template-columns:1fr 1fr;gap:20px">
  ${tile('cable-n-logo.svg', '#fff')}${tile('cable-n-logo-full.svg', '#fff')}
  ${tile('cable-n-logo-on-dark.svg', '#14100f')}${tile('cable-n-logo-full-on-dark.svg', '#14100f')}
  ${tile('cable-n-logo-mono-dark.svg', '#fff')}${tile('cable-n-logo-mono-white.svg', '#CE1B28')}
  <div style="background:#fff;padding:20px;border-radius:12px;display:flex;gap:24px;align-items:center">${[16, 32, 64, 128].map((s) => b('cable-n-icon.svg').replace('<svg ', `<svg style="width:${s}px;height:${s}px" `)).join('')}</div>
  <div style="background:#fff;padding:20px;border-radius:12px;display:flex;gap:24px;align-items:center">${b('cable-n-icon-mono-dark.svg').replace('<svg ', '<svg style="width:64px;height:64px" ')}</div>
  </div>`, 1160, 720, process.argv[i + 1])
}
await browser.close()
console.log('brand PNGs written')
