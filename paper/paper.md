<!--
Skica seminarskog/završnog rada.

Strukturirano prema smjernice.md (FER stil + IEEE citiranje) i template.md.
Hrvatski jezik, formalan stil, IEEE citati u uglatim zagradama.

LEGENDA OZNAKA:
  [TODO: ...]   -> što treba napisati u toj sekciji
  [PRIMJER: ...] -> kratak primjer rečenice / odlomka kao polazna točka
  [PODATAK]     -> brojka ili rezultat koji treba ubaciti iz pipelinea
-->

SVEUČILIŠTE U ZAGREBU

FAKULTET ELEKTROTEHNIKE I RAČUNARSTVA

ZAVRŠNI RAD

# Prilagodljivi preporučitelj zadataka za pripremu ispita iz kolegija Algoritmi i strukture podataka

Marin Denić

Voditelj: [Ime i prezime voditelja]

Zagreb, lipanj 2026.


---

## Sadržaj

1. Uvod
2. Pregled srodnih radova
3. Metodologija
4. Implementacija
5. Rezultati
6. Rasprava
7. Zaključak
8. Sažetak
9. Literatura


---

## Sažetak

[TODO: 150-250 znakova. Mora sadržavati cilj, ukratko opisanu metodologiju i
najvažnije rezultate. Strukturira se kao tri-četiri rečenice:
  1. Što je problem (vrijeme za vježbu je ograničeno, korpus zadataka velik)
  2. Što je predloženo (pipeline za parsiranje, klasteriranje i preporuku)
  3. Kako je evaluirano (klasterska metrika + korisničko ocjenjivanje)
  4. Glavni nalaz (preporučitelj proizvodi raznolike, vremenski usklađene liste)]

[PRIMJER: U ovom se radu predstavlja sustav za preporuku zadataka iz kolegija
"Algoritmi i strukture podataka" temeljen na klasteriranju semantičkih ugrađivanja
i knapsack optimizaciji. Cilj je studentu u zadanom vremenu predložiti listu
zadataka koja maksimalno pokriva relevantne teme uz uzimanje u obzir
crowdsourcanih ocjena težine. Rezultati pokazuju [PODATAK] te...]


## Ključne riječi

[TODO: 3-5 ključnih riječi.]

Predložene: preporučitelj, knapsack, klasteriranje teksta, sentence embeddings,
priprema ispita.


---

# 1. Uvod

## 1.1. Motivacija

[TODO: ~1 stranica. Opiši problem iz studentove perspektive:
  - Korpus prošlih ispitnih zadataka iz ASP-a je velik (oko 200 zadataka)
  - Studentsko vrijeme je ograničeno, posebno pred kraj semestra
  - Manualno biranje "korisnih" zadataka je teško bez nadzora nad raznolikošću
    tema i procjenom težine
  - Nedostaje sustav koji uvažava i objektivnu strukturu (klasteri tema) i
    subjektivnu procjenu (težina i potrebno vrijeme)]

[PRIMJER: Tijekom pripreme za ispite iz kolegija "Algoritmi i strukture
podataka" studenti se suočavaju s velikim korpusom prošlih zadataka, no
ograničenim vremenom za njihovo proučavanje. Iako je sav materijal javno
dostupan, izbor najkorisnijeg podskupa zadataka za vježbu nije trivijalan
zadatak.]

## 1.2. Cilj rada

[TODO: Jasno postavljene tvrdnje rada, jedna ili dvije rečenice po točki:
  1. Razviti pipeline koji semantički klasterira zadatke iz prošlih ispita
  2. Implementirati web-aplikaciju za crowdsourcanje subjektivnih ocjena
     težine i potrebnog vremena
  3. Konstruirati preporučitelj koji u zadanom vremenu predlaže raznolik
     i ciljano usmjeren skup zadataka]

## 1.3. Struktura rada

[TODO: 4-5 rečenica, jedna po poglavlju. Standardna fraza:
  "U drugom poglavlju predstavlja se pregled srodnih radova, ...".]


---

# 2. Pregled srodnih radova

[TODO: ~1.5 stranice. Tri pod-teme:
  2.1. Sustavi za preporuku (knapsack pristup, content-based, collaborative)
  2.2. Klasteriranje teksta i sentence embeddings (SBERT, paraphrase modeli,
       UMAP redukcija)
  2.3. Sustavi za pripremu ispita / adaptivno učenje (Anki, Khan Academy SRS,
       relevantne edukacijske platforme)

  Najmanje 8-10 citata iz znanstvenih izvora. Koristi IEEE stil [1], [2]-[5]
  kako je opisano u smjernice.md.]

[PRIMJER citata: "Reimers i Gurevych predstavili su Sentence-BERT [3],
arhitekturu koja prilagođava BERT za učinkovito generiranje semantičkih
ugrađivanja rečenica."]


---

# 3. Metodologija

## 3.1. Pregled arhitekture sustava

[TODO: Pol stranice. Dijagram tijeka podataka (može biti ASCII ili PNG):
  PDF ispita -> Parsiranje (PyMuPDF) -> Sentence embedding (paraphrase-multilingual-MiniLM)
       -> UMAP redukcija (10D) -> K-means (k=15) -> LLM oznake (llama3.1)
       -> Outlier scoring -> Frekvencije po tipu ispita -> Knapsack solver
                  ^
                  | crowdsourcing ocjena (Next.js + Supabase)
                  |
       Web-aplikacija "asp-rate"]

[PRIMJER: Sustav se sastoji od triju glavnih cjelina koje međusobno
komuniciraju kroz dijeljene artefakte: cjevovoda za obradu prošlih ispita,
web-aplikacije za prikupljanje korisničkih ocjena i preporučitelja.]

## 3.2. Korpus i parsiranje

[TODO:
  - Izvor: prošli MI (međuispit) i ZI (završni ispit) iz ASP-a, [PODATAK: 105
    MI + 91 ZI = 196 zadataka]
  - PyMuPDF (fitz) za ekstrakciju teksta
  - Heuristike za odvajanje pojedinih zadataka (regex na "Zadatak N.")
  - Bisect za određivanje pdf_page po offsetu u spojenom tekstu]

## 3.3. Vektorska reprezentacija (sentence embeddings)

[TODO:
  - Model: paraphrase-multilingual-MiniLM-L12-v2 (384D)
  - Razlog: višejezičan (hrvatski podržan), brz, dovoljno bogat za semantičko
    grupiranje kratkih ispitnih zadataka
  - Reference SBERT [3], multilingual variants]

## 3.4. Klasteriranje (UMAP + K-means)

[TODO:
  - Zašto UMAP prije K-meansa? Sparse 384D prostor s 196 točaka nije
    pogodan za K-means; UMAP redukcija na 10D stabilizira rezultate.
  - Hiperparametri: n_components=10, n_neighbors=15, metric="cosine",
    random_state=42
  - Izbor k: sweep k iz [5, 25] (vidi sekciju 5.1)
  - Stabilnost: n_init=50, mjereno preko ARI između run-ova]

## 3.5. LLM oznake klastera

[TODO:
  - Lokalna Ollama s llama3.1 modelom
  - Prompt na hrvatskom: sažmi sadržaj klastera u 2-4 riječi
  - Validacija: ručna provjera labela na uzorku, citiraj ako postoji
    standardna metoda]

## 3.6. Prikupljanje ocjena (crowdsourcing)

[TODO:
  - Arhitektura web-aplikacije asp-rate (Next.js + Supabase)
  - Identitet: anonimna sesija po pregledniku, opcionalan email + OTP kod
    za prijenos napretka kroz uređaje
  - Sigurnosni model: Row-level security na Supabaseu, autentificirani
    korisnici samo umetaju vlastite redove
  - UI: sekvencijalni unos (težina 1-5, zatim vrijeme 15/30/45/60 min)
  - Bird-eye pregled u sekciji 4.2]

## 3.7. Kontinuirani outlier score

[TODO:
  - Po klasteru izračunaj centroid (srednju vrijednost embeddinga)
  - Kosinusna udaljenost svakog zadatka do centroida svojeg klastera
  - Per-cluster normalizacija (percentilski rang unutar klastera) jer
    klasteri imaju različite raspršaje
  - Tumačenje: 0.0 = najtipičniji predstavnik, 1.0 = najveći outlier u skupini]

## 3.8. Frekvencije klastera po tipu ispita

[TODO:
  - P(cluster | exam_type) iz empirijske distribucije
  - Recommender u exam-modu rabi ovo kao težinski faktor: rijetki klasteri
    dobivaju manju vrijednost kad je vrijeme ograničeno]

## 3.9. Knapsack preporučitelj

[TODO: Najopsežnija pod-sekcija. 1-2 stranice.
  - Postavka problema: maks(suma vrijednosti) uz ograničenje vremena
  - Tri komponente bazne vrijednosti:
      1. frequency_bonus (samo exam-mode)
      2. difficulty_bonus (lakše = vrednije, opravdano time da lakši
         zadaci ostavljaju kognitivni prostor za nove)
      3. centroid_bonus (tipičniji = vrednije)
  - Diminishing returns: k-ti zadatak iz istog klastera ima vrijednost
    base * decay^(k-1). Default decay = 0.7.
  - Outlier filter ovisi o ciljanoj ocjeni (samo exam-mode):
      cutoff = target_grade / 100
  - Greedy aproksimacija optimuma (n=196, dovoljno brzo, < 1s)
  - Spomeni razliku od klasičnog 0/1 knapsacka (vrijednost zadatka ovisi o
    već odabranim zadacima -> nije čisti knapsack, već submodularna
    optimizacija sa stop-on-budget pravilom)
  - Cite: knapsack [?], submodular greedy [?]]

## 3.10. Budući rad: RAG za objašnjenja rješenja

[TODO: Kratko, 1-2 odlomka. Skiciraj viziju ali jasno reci da je izvan
opsega trenutne verzije.]


---

# 4. Implementacija

## 4.1. Python cjevovod

[TODO: Struktura paketa `pipeline/`:
  - parsing.py, merge.py, embedding.py, clustering.py, labeling.py, frequency.py
  - embed_pipeline.py kao tanak CLI driver (~90 linija)
  - build_recommender_data.py kao posebni driver za lakše output-e
  - Konfiguracija preko ENV varijabli (config.py)
  Spomeni odluku da se logika izdvoji u paket umjesto monolitnog scripta
  (391 linija prije refaktora).]

## 4.2. Web-aplikacija za ocjenjivanje (asp-rate)

[TODO: Tehnološki stack i ključne odluke:
  - Next.js 15.5 (App Router) + TypeScript + Tailwind
  - Supabase Auth (anonimni signin + OTP kod za email upgrade)
  - Atomski merge anon -> trajni račun preko Postgres `security definer`
    funkcije `merge_anon_ratings`
  - Mobilni pinch-to-zoom (react-zoom-pan-pinch)
  - Deploy: Vercel monorepo s Root Directory `asp-rate/`
  Screenshot: onboarding, rating, zoom modal.]

## 4.3. Streamlit preporučitelj

[TODO:
  - Modovi: Tema (klasteri) i Ispit (MI/ZI/oba) + ciljana ocjena
  - Vrijeme: ukupno ili min/dan x dana
  - Tablica preporuka, pokrivenost klastera, PDF pregled odabranog zadatka
  Screenshot UI-ja.]


---

# 5. Rezultati

## 5.1. Kvaliteta klastera

[TODO:
  - K sweep iz analyze_clusters.py: silhouette, inertia, ARI po k iz [5, 25]
  - Plot iz embeddings/cluster_sweep.png
  - Preporučeni k=15 (silhouette [PODATAK], ARI [PODATAK])
  - UMAP 2D vizualizacija (cluster_umap_2d.png)
  - Tablica oznaka klastera (top tema po klasteru)]

## 5.2. Prikupljene ocjene

[TODO: Pune kad se prikupi dovoljno ocjena. Zasad:
  - Broj korisnika [PODATAK]
  - Broj ocjena [PODATAK]
  - Medijan ocjena po zadatku [PODATAK]
  - Distribucija težine 1-5 (histogram)
  - Distribucija vremena 15/30/45/60 min (histogram)
  - Inter-rater agreement: Krippendorffov alpha ili ICC]

## 5.3. Outlier scoring

[TODO:
  - Top-10 outliera s primjerima (ručno provjeriti jesu li smisleni)
  - Distribucija scoreova po klasteru
  - Primjer: cluster X centar = [tipičan zadatak], outlier = [neobičan]]

## 5.4. Primjer izlaza preporučitelja

[TODO: 3-4 prilagođena slučaja. Za svaki:
  - Konfiguracija (mod, vrijeme, ocjena/klasteri)
  - Izlazna lista (tablica)
  - Pokrivenost klastera
  - Kratka analiza zašto je izbor smislen]


---

# 6. Rasprava

## 6.1. Ograničenja pristupa

[TODO:
  - Korpus je relativno mali (196 zadataka)
  - Sparse ratings: kad je n_ratings/task malen, medijan je nepouzdan
  - Greedy nije optimum knapsacka, ali razlika je u praksi mala za n=196
  - LLM oznake klastera mogu biti nedosljedne
  - Centroid distance ovisi o izboru embedding modela]

## 6.2. Buduća poboljšanja

[TODO:
  - RAG za objašnjenja rješenja
  - Bolji modeli embeddinga (npr. fine-tuned na ASP korpusu)
  - Aktivno učenje: ciljano traži ocjene za zadatke s velikom varijancom
  - Personalizirani decay parametar po korisniku
  - Evaluacija s pravim studentima (kontrolirana skupina)]


---

# 7. Zaključak

[TODO: ~jedna stranica. Tri odlomka:
  1. Sažetak postignutoga (što je napravljeno)
  2. Glavni rezultati (kvantificirano)
  3. Buduća smjernica i osobni doprinos (kratko)]


---

# 8. Sažetak na engleskom

[TODO: Prevedi sažetak na engleski. Često je obvezno na FER-u.]


---

# 9. Literatura

[TODO: IEEE stil. Format imena: "I. Prezime". Više autora odvojeno zarezom;
od sedam autora pa nadalje koristi "I. Prezime *et al.*". Najmanje 10
referenci, mix knjiga i znanstvenih radova. Redoslijed po pojavljivanju
u tekstu, ne abecedno.

Polazni popis (popuni s konkretnim referencama):

[1] [Knjiga: T. H. Cormen, C. E. Leiserson, R. L. Rivest, C. Stein,
    *Introduction to Algorithms*, 3rd ed. Cambridge, MA, USA: MIT Press, 2009.]
[2] [Reimers i Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese
    BERT-Networks", *EMNLP-IJCNLP 2019*, str. 3982-3992.]
[3] [McInnes, Healy, Melville, "UMAP: Uniform Manifold Approximation and
    Projection for Dimension Reduction", *arXiv:1802.03426*, 2018.]
[4] [Knapsack referenca - Kellerer, Pferschy, Pisinger, *Knapsack Problems*,
    Springer, 2004.]
[5] [Submodular greedy - Nemhauser, Wolsey, Fisher, "An analysis of
    approximations for maximizing submodular set functions", *Math. Prog.* 1978.]
[6]-[10] [TODO: dodaj još relevantnih.]
]
