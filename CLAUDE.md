# CLAUDE.md

Checkpoint za buduće sesije. Ako Claude Code počne novu sesiju (npr. nakon
restart-a kompjutera), ovo + `PIPELINE.md` + `asp-rate/README.md` daje
dovoljno konteksta za nastavak rada bez ponavljanja.

---

## Što je ovaj projekt

Zavrsni rad (thesis MVP) oko ASP (Algoritmi i strukture podataka) ispitnih
zadataka. Tri međusobno povezane stvari:

1. **Embedding + clustering pipeline** za parsiranje PDF-ova ispita i grupiranje
   zadataka po sličnosti (K-means na UMAP-reduciranim sentence-transformer
   embeddinzima).
2. **`asp-rate/` webapp** (Next.js + Supabase + Vercel) za crowdsourcing
   subjektivnih ocjena težine od kolega.
3. **Budući recommender** koji koristi i klastere i prikupljene ocjene da
   predloži zadatke za vježbanje prema cilju i raspoloživom vremenu.

---

## Gdje što gledati

| Datoteka                    | Što je unutra                                       |
|-----------------------------|-----------------------------------------------------|
| `PIPELINE.md`               | Detaljan workflow embedding/clustering pipelinea    |
| `asp-rate/README.md`        | Setup, env vars, Supabase schema, deploy            |
| `pipeline/`                 | Python paket: parsing/merge/embedding/clustering/labeling |
| `embed_pipeline.py`         | Tanak CLI driver — orkestrira pipeline              |
| `analyze_clusters.py`       | K-selection sweep s plotovima                       |
| `render_task_images.py`     | Generira PDF stranice → PNG-ovi + `tasks.json`      |
| `asp-rate/app/page.tsx`     | Cijeli rating UI (single page, client-side only)    |
| `asp-rate/supabase/schema.sql` | Tablica `ratings` + RLS politike                 |
| `~/.claude/projects/.../memory/MEMORY.md` | Auto-loaded memory: scope + preferences |

---

## Što je dosad napravljeno

### Pipeline / klasteri
- [x] PDF parsing s `fitz` (PyMuPDF) — riješen UnicodeDecodeError, parser zna
      i `pdf_page` za svaki zadatak (bisect na page offsete u joined tekstu).
- [x] Refaktor `embed_pipeline.py` (391 linija) → `pipeline/` paket + tanak driver.
- [x] Stabilizacija K-meansa: UMAP → 10D prije K-meansa, `n_init=50`,
      `random_state=42`. Silhouette ∈ [0.476, 0.609], ARI ≥ 0.86 kroz sweep.
- [x] Diagnostic sweep (`analyze_clusters.py`) — silhouette + ARI stability +
      elbow plot. Preporučeni k = 15 (silhouette 0.61, ARI 0.98).
- [x] LLM labeling klastera preko Ollame (llama3.1, hrvatski).

### Webapp (asp-rate/)
- [x] Bootstrap Next.js 15.5 + TypeScript + Tailwind + @supabase/supabase-js,
      bez izvođenja `create-next-app` (sve datoteke ručno napisane).
- [x] Anonymous per-browser UUID (`lib/rater-id.ts`).
- [x] Lazy Supabase client (proxy) tako da `next build` ne pada bez env-a.
- [x] Single-page UI: učitava `tasks.json`, fetcha sve ratinge iz Supabasea,
      bira fewest-rated task kojeg trenutni rater nije ocijenio, šalje
      `INSERT into ratings` direktno iz browsera kroz RLS.
- [x] Keyboard prečaci 1-5, auto-advance, progress counter.
- [x] Zoom modal: klik slike → fullscreen, scroll-friendly (`overflow-auto`,
      ne `flex items-center`), pinch-zoom radi na mobitelu.
- [x] Animacije: card slide-in na novi task, button-pulse na klik, "Spremljeno"
      toast.
- [x] Diagnostic Supabase error koji pokazuje host + hint-listu za Failed to fetch.
- [x] **Supabase project je već setupan i radi** — user je potvrdio da ratinzi
      ulaze u bazu.
- [x] Info aside na vrhu stranice s opisom — user je počeo pisati pravi tekst
      umjesto placeholdera (vidi `app/page.tsx` ~line 183-216). Jedan bullet je
      ostao nedovršen ("Što se tiče estimacije vremena, također, ").

### Image rendering
- [x] 89 jedinstvenih PDF stranica @ 130 DPI → `asp-rate/public/task-images/`
      (~16 MB). `asp-rate/public/tasks.json` s 196 task entrija.

---

## GDJE SMO STALI (checkpoint)

Razgovor je prekinut na temi **`time_est`** (estimacija vremena potrebnog za
zadatak). User je rekao doslovno:

> "oh yeah i forgot about time_est. ill tell you all about it, but i need to
> restart my computer now. (...) we stopped at talking about time_est (spoiler
> alert, we're going to add it to the webpage and will also collect info
> about it)."

Što znamo do sada:
- `time_est` je trenutno kolona u `data/asp_index_last3_mi_last3_zi.csv`
  (manualno procijenjeno vrijeme rješavanja po zadatku) — vidi tablicu u
  CLAUDE chatu / `PIPELINE.md`.
- User je već naznačio da time_est NIJE lako automatski derivirat iz čistog
  PDF teksta — za razliku od `difficulty_guess` (zamijenit će se real ocjenama),
  `type`/`concepts` (zamijenjuju se klasterima), `points` (lako regex iz
  `(N bod...)` markera).
- Plan koji još NIJE detaljno raspravljen: dodati time_est input u asp-rate
  webapp tako da user osim difficulty (1-5) procjeni i koliko mu vremena treba
  / je trebalo za zadatak. Spoiler je rekao "we're going to add it to the
  webpage and will also collect info about it" — open question: hoće li to
  biti samo-procjena (slider/input "10 min, 30 min, ...") ili stvarno mjerenje
  (timestamp od prikaza taska do submita ratinga), ili oboje.

**Sljedeća akcija u idućoj sesiji**: čekati na user-ov detaljan opis kako
točno žele time_est rješavati. Ne implementirati ništa unaprijed.

---

## Otvorene stvari (osim time_est)

- **Info aside u `app/page.tsx`** — user piše vlastiti tekst preko mojih
  placeholder bulleta. Jedan bullet ("Što se tiče estimacije vremena, također,")
  je nedovršen — ne dirati dok user ne kaže.
- **CSV `data/asp_index_last3_mi_last3_zi.csv`** — još uvijek se koristi u:
  - `pipeline/merge.py` (left-join u `tasks_with_clusters.csv`, ali samo
    28/196 redaka matcha)
  - `app.py` (legacy Streamlit UI)
  Plan je postepeno ga umiroviti čim ratinzi i klasteri pokriju potrebne
  signale. Vidi posljednju poruku u chatu za detaljnu tablicu replacementa.
- **Mobile testing** — user je htio mobilno testiranje. Zoom modal je
  popravljen, ali nije eksplicitno potvrđeno da je sve OK na mobitelu.
- **Deploy na Vercel** — user može sad pushat na GitHub i deployat. Supabase
  env vars treba dodati u Vercel project settings.

---

## Setup state (za fresh sesiju)

- Python deps: `sentence-transformers`, `sklearn`, `umap-learn`, `pymupdf`,
  `pandas`, `numpy`, `requests`, `matplotlib` — sve već instalirano.
- Node deps: u `asp-rate/node_modules/` (Next 15.5.18). Pokreni
  `npm run dev` iz `asp-rate/` za lokalno testiranje.
- Supabase: već konfiguriran. URL je u `asp-rate/.env.local` (NE commitati u git).
- Embeddings cached u `embeddings/embeddings.npy` (shape 196 × 384).
- Trenutni N_CLUSTERS u `pipeline/config.py` je 15 (preporuka iz sweep-a).

---

## Memory pointeri (auto-loaded)

User memory je u `~/.claude/projects/C--Users-DenaBena-Documents-Projects-zavrsni-mvp/memory/`:
- `project_scope.md` — pravila projekta i prošle odluke
- `feedback_plan_before_code.md` — user želi plan + clarifying Qs prije
  implementacije multi-step taskova
- `feedback_pace_pragmatism.md` — minimal/working > polished, ne paditi
  estimate-e ni scope

Tijekom novih sesija ovi se učitavaju automatski preko `MEMORY.md` indeksa.
