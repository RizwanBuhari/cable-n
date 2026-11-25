# Optional Google AdSense

Ads appear only in a labelled “Sponsored” panel in the right-hand rail of Home, Calculators hub, Cable Library, Validation, Resources and the info pages (below the content on mobile). They never appear inside the calculators, over results, as pop-ups or with autoplay. Slots load lazily when scrolled into view and collapse when Google returns no ad, when blocked, or when the visitor has an ad-free licence.

## 1. Get approved
1. Deploy the site publicly on your own domain with HTTPS (DEPLOYMENT.md) and the Privacy, Terms, About and Contact pages reachable (they are built in).
2. Sign up at https://adsense.google.com → **Sites → Add site** → enter your domain.
3. AdSense shows your **publisher ID** `ca-pub-XXXXXXXXXXXXXXXX`.
4. Site verification: choose the **ads.txt** method. Cable-N writes `ads.txt` automatically at build time once step 2 below is done. (You can also choose “AdSense code snippet”; the script is only loaded after consent, so ads.txt is the reliable choice.)
5. Request review. Approval can take days to weeks.

## 2. Configure Cable-N
Create the ad units in AdSense → **Ads → By ad unit → Display ads** (responsive). Make two: “Rail” and “Inline”. Copy each `data-ad-slot` number.

`frontend/.env.production` (or Docker build args in `docker-compose.yml` via a root `.env`):
```
VITE_SITE_URL=https://your-domain.example
VITE_ADS_ENABLED=true
VITE_ADSENSE_CLIENT=ca-pub-XXXXXXXXXXXXXXXX
VITE_ADSENSE_SLOT_RAIL=1234567890
VITE_ADSENSE_SLOT_INLINE=0987654321
VITE_ADSENSE_CMP=own
```
Rebuild and redeploy. These values are public (they are in every AdSense page anyway) — no secrets.

## 3. Consent (required)
- **Visitors from the EEA, UK or Switzerland:** Google requires a **Google-certified CMP**. Easiest: AdSense → **Privacy & messaging → European regulations → Create message** (free, certified), publish it, then set `VITE_ADSENSE_CMP=google`. Cable-N then lets Google's message handle consent and does not show its own banner.
- **Otherwise:** `VITE_ADSENSE_CMP=own` uses Cable-N's banner: the AdSense script is not loaded at all until the visitor clicks “Accept advertising cookies”. “Essential only” means no ads. Visitors can change their choice via the footer “Cookie preferences” link.
- For US state privacy laws, enable the AdSense “US state regulations” message as well.

## 4. Test
- `https://your-domain.example/ads.txt` shows `google.com, pub-…, DIRECT, f08c47fec0942fa0`.
- Visit the home page, accept cookies, scroll: a “Sponsored” panel appears (before approval it may stay blank and collapse — that is expected).
- Choose “Essential only”: the network tab shows no request to `googlesyndication.com`.

## Disable
`VITE_ADS_ENABLED=false`, rebuild. No ad containers or scripts remain.

## Ad-free premium
See MANUAL_SETUP.md §6 (licence keys, no accounts needed).
