// Single source of page titles and descriptions. Used at runtime (document
// head) and at build time (scripts/postbuild.mjs writes a pre-rendered
// index.html per route so crawlers and link previews see the right metadata).
export const SITE_NAME = 'Cable-N'
export const TAGLINE = 'Cable Sizing & Engineering Intelligence'

export const ROUTES = [
  { path: '/', title: `${SITE_NAME} — ${TAGLINE}`,
    description: 'Free online electrical cable sizing: single feeders, batch cable schedules, duct-bank current-rating checks and full IEC 60287 / 60949 MV-HV analysis. No sign-up.',
    priority: 1.0 },
  { path: '/calculators', title: 'Cable calculators — Cable-N',
    description: 'Four engineering calculators: single feeder sizing, batch cable schedule, current-rating verification and advanced MV/HV IEC 60287 analysis.', priority: 0.9 },
  { path: '/calculators/single-feeder', title: 'Single feeder cable sizing calculator — Cable-N',
    description: 'Size a cable for one feeder: design current, derating factors, voltage drop, short-circuit withstand and parallel-run options with installation diagrams.', priority: 0.9 },
  { path: '/calculators/batch', title: 'Batch cable schedule calculator — Cable-N',
    description: 'Size many feeders at once and produce a cable schedule. Excel import template, row-level validation, PDF and Excel export.', priority: 0.8 },
  { path: '/calculators/current-rating', title: 'Duct bank current rating verification — Cable-N',
    description: 'Check the current rating of cables in duct banks or buried groups with grouping, depth, soil and inter-bank factors.', priority: 0.8 },
  { path: '/calculators/advanced-mv-hv', title: 'IEC 60287 MV/HV cable rating calculator — Cable-N',
    description: 'Full IEC 60287 / 60949 analysis: T1–T4 thermal resistances, losses, mutual heating, sequence impedance, induced voltage, short-circuit and emergency ratings.', priority: 0.8 },
  { path: '/cable-library', title: 'Cable library — Cable-N',
    description: 'Browse the built-in ampacity, resistance and reactance tables used by the Cable-N engine and keep your own cable definitions in your browser.', priority: 0.6 },
  { path: '/comparison', title: 'Compare cable options, sensitivity and cost — Cable-N',
    description: 'Compare saved cable calculations side by side, run sensitivity sweeps with the real engine and estimate cost from your own prices.', priority: 0.6 },
  { path: '/validation', title: 'Engine validation centre — Cable-N',
    description: 'Run the calculation engine against its reference workbook and CYMCAP benchmark cases and see every deviation.', priority: 0.6 },
  { path: '/resources', title: 'Engineering resources: cable rating methods and symbols — Cable-N',
    description: 'How Cable-N sizes cables: derating factors, voltage drop, adiabatic short-circuit, IEC 60287 thermal resistances, losses and a glossary of symbols.', priority: 0.7 },
  { path: '/settings', title: 'Settings — Cable-N', description: 'Appearance, engineering defaults, cookies and your locally stored data.', priority: 0.3 },
  { path: '/about', title: 'About Cable-N', description: 'What Cable-N is, how the calculation engine works and how your data is handled.', priority: 0.5 },
  { path: '/contact', title: 'Contact — Cable-N', description: 'How to reach the Cable-N team.', priority: 0.3 },
  { path: '/privacy', title: 'Privacy policy — Cable-N', description: 'How Cable-N handles data, cookies and advertising.', priority: 0.3 },
  { path: '/terms', title: 'Terms of service — Cable-N', description: 'Terms for using the Cable-N website and calculation tools.', priority: 0.3 },
  { path: '/disclaimer', title: 'Engineering disclaimer — Cable-N', description: 'Cable-N results support, and never replace, qualified engineering judgement.', priority: 0.3 },
]

export function routeMeta(pathname) {
  return ROUTES.find((r) => r.path === pathname) || null
}
