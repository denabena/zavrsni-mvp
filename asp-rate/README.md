# asp-rate

Mini webapp za prikupljanje 1–5 difficulty ratinga na ASP exam zadacima.
Anonimno (per-browser UUID), bez auth-a. Tasks se renderiraju kao slike stranica iz PDF-ova.

## Setup (jednom)

### 1. Supabase projekt

1. Otvori https://supabase.com → New Project
2. SQL Editor → run `supabase/schema.sql`
3. Settings → API → kopiraj **Project URL** i **anon public key**

### 2. Env varijable

```bash
cp .env.local.example .env.local
# uredi .env.local i ubaci URL + anon key
```

### 3. Dependencies

```bash
npm install
```

### 4. Task images + manifest

PDF stranice i `tasks.json` su već generirani u `public/`.
Ako PDF-ovi promijene ili treba re-generirati:

```bash
# iz repo roota:
python render_task_images.py
```

## Dev

```bash
npm run dev
# http://localhost:3000
```

## Deploy (Vercel)

1. Push repo na GitHub
2. https://vercel.com → New Project → import repo
3. **Root Directory: `asp-rate`**
4. Environment Variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
5. Deploy

## Arhitektura

- `app/page.tsx` — jedini ekran. Učitava `public/tasks.json`, dohvaća sve ratinge iz Supabasea, bira sljedeći zadatak (najmanje ocjena, koji rater još nije ocijenio), spremma ratinge.
- `lib/supabase.ts` — Supabase JS klijent s anon ključem (sigurno u browseru zbog RLS-a).
- `lib/rater-id.ts` — UUID u localStorage.
- `supabase/schema.sql` — jedna tablica `ratings` + RLS politike za anon.

## Sigurnost

- RLS na `ratings` tablici dopušta anon SELECT (potrebno za brojanje) i INSERT (s difficulty 1–5).
- UPDATE/DELETE zabranjeni za anon.
- `unique (task_id, rater_uuid)` sprječava duple ratinge.
