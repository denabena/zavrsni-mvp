-- asp-rate: schema za 1-5 difficulty ratings.
-- Pokreni ovo u Supabase SQL Editoru jednom, prilikom setupa projekta.

create table if not exists ratings (
  id          bigserial primary key,
  task_id     text not null,
  rater_uuid  text not null,
  difficulty  smallint not null check (difficulty between 1 and 5),
  created_at  timestamptz not null default now(),
  unique (task_id, rater_uuid)
);

create index if not exists ratings_task_id_idx on ratings (task_id);
create index if not exists ratings_rater_uuid_idx on ratings (rater_uuid);

-- RLS: anonimni pristup, ali read-only osim INSERTa
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
  with check (difficulty between 1 and 5);
