# LINDA brand in the product

**LINDA** — Linked Intelligence for Networked Development & Administration.
Slogan: *One Platform. Every Business.* Powered by Saccharum Technologies.

## What the app does with it
- Colours: navy `#101D2B`, gold `#D6A85F` (accent only), light grey `#F5F6F8`. Defined in `frontend/app/globals.css` (`--linda-gold`, `--linda-gold-text`).
- Font: Inter (`@fontsource-variable/inter`).
- Logo: `frontend/components/LindaLogo.tsx` (geometric L, no industry imagery). Favicon: `frontend/app/icon.svg`.
- Top-right of every screen: the business name with its platform label underneath, from `frontend/lib/platform.ts`:
  - funeral business → **Funeral Platform**
  - any other business → **Business Management Platform**
- Sign-in and register pages follow the split-screen layout in the brand document.

## Deliberately not renamed
Database names (`funeralos`, `funeralos_test`), the backup file prefix, logger names and browser storage keys
(`funeralos_theme` and similar). Renaming these would break existing installs and saved settings for no visible gain.

## Adding a new business type
Add its label in `platformLabel()` in `frontend/lib/platform.ts` and its rules in `backend/app/services/business_type.py`.
