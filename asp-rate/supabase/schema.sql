-- asp-rate: schema za 1-5 difficulty ratings + procjenu vremena + (opcionalni) email kontakt.
-- Pokreni ovo u Supabase SQL Editoru jednom, prilikom setupa projekta.
-- Za postojeću bazu vidi MIGRATION snippet na dnu datoteke.

-- ───────────────────────────────────────────────────────────────────
-- ratings
-- ───────────────────────────────────────────────────────────────────
create table if not exists ratings (
  id                bigserial primary key,
  task_id           text     not null,
  rater_uuid        text     not null,
  difficulty        smallint not null check (difficulty between 1 and 5),
  time_est_minutes  smallint          check (time_est_minutes in (15, 30, 45, 60)),
  created_at        timestamptz not null default now(),
  unique (task_id, rater_uuid)
);

create index if not exists ratings_task_id_idx     on ratings (task_id);
create index if not exists ratings_rater_uuid_idx  on ratings (rater_uuid);

alter table ratings enable row level security;

drop policy if exists "anon_read_ratings" on ratings;
create policy "anon_read_ratings"
  on ratings for select
  to anon
  using (true);

drop policy if exists "anon_insert_ratings" on ratings;
create policy "anon_insert_ratings"
  on ratings for insert
  to anon
  with check (
    difficulty between 1 and 5
    and (time_est_minutes is null or time_est_minutes in (15, 30, 45, 60))
  );

-- ───────────────────────────────────────────────────────────────────
-- raters  (opcionalni email za kontakt oko nagrada, bez verifikacije)
-- ───────────────────────────────────────────────────────────────────
create table if not exists raters (
  rater_uuid  text primary key,
  email       text,
  created_at  timestamptz not null default now()
);

alter table raters enable row level security;

drop policy if exists "anon_read_raters" on raters;
create policy "anon_read_raters"
  on raters for select
  to anon
  using (true);

drop policy if exists "anon_upsert_raters" on raters;
create policy "anon_upsert_raters"
  on raters for insert
  to anon
  with check (true);

drop policy if exists "anon_update_raters" on raters;
create policy "anon_update_raters"
  on raters for update
  to anon
  using (true)
  with check (true);

-- ───────────────────────────────────────────────────────────────────
-- MIGRATION (već imaš ratings tablicu, pokreni samo ovaj blok):
-- ───────────────────────────────────────────────────────────────────
-- alter table ratings
--   add column if not exists time_est_minutes smallint
--   check (time_est_minutes in (15, 30, 45, 60));
--
-- drop policy if exists "anon_insert_ratings" on ratings;
-- create policy "anon_insert_ratings"
--   on ratings for insert
--   to anon
--   with check (
--     difficulty between 1 and 5
--     and (time_est_minutes is null or time_est_minutes in (15, 30, 45, 60))
--   );
--
-- create table if not exists raters (
--   rater_uuid  text primary key,
--   email       text,
--   created_at  timestamptz not null default now()
-- );
-- alter table raters enable row level security;
-- create policy "anon_read_raters"   on raters for select to anon using (true);
-- create policy "anon_upsert_raters" on raters for insert to anon with check (true);
-- create policy "anon_update_raters" on raters for update to anon using (true) with check (true);
