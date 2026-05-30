-- asp-rate: ratings keyed to Supabase Auth users.
-- Identitet je auth.uid(): anonimni korisnici (signInAnonymously) i trajni
-- (email + OTP kod) dijele isti model. rater_uuid drži auth.uid()::text.
--
-- Pokreni ovo u Supabase SQL Editoru. WIPE: briše stare ratings i raters tablice.

drop table if exists raters;
drop table if exists ratings;

create table ratings (
  id                bigserial primary key,
  task_id           text     not null,
  rater_uuid        text     not null,
  difficulty        smallint not null check (difficulty between 1 and 5),
  time_est_minutes  smallint          check (time_est_minutes in (15, 30, 45, 60)),
  created_at        timestamptz not null default now(),
  unique (task_id, rater_uuid)
);

create index ratings_task_id_idx    on ratings (task_id);
create index ratings_rater_uuid_idx on ratings (rater_uuid);

alter table ratings enable row level security;

-- Svi prijavljeni (uklj. anonimni) smiju čitati sve ratinge: treba za brojanje
-- koliko je puta koji zadatak ocijenjen (pick fewest-rated).
create policy "auth_read_ratings"
  on ratings for select
  to authenticated
  using (true);

-- Insert samo vlastitih redaka: rater_uuid mora biti tvoj auth.uid().
create policy "auth_insert_own_ratings"
  on ratings for insert
  to authenticated
  with check (rater_uuid = auth.uid()::text);

-- Atomski merge: prebaci ratinge s napuštenog anonimnog usera na trenutno
-- prijavljenog (auth.uid()). Postojeći ratinzi na istom (task_id, rater_uuid)
-- se preskaču (unique constraint + ON CONFLICT DO NOTHING). Anonimni redci se
-- nakon toga brišu da nema duplikata pod mrtvim UID-om. Security definer da
-- bismo mogli pisati i brisati pod auth.uid()/p_anon_uid bez RLS prepreka.
create or replace function merge_anon_ratings(p_anon_uid text)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_current_uid text := auth.uid()::text;
  v_inserted   integer;
begin
  if v_current_uid is null or v_current_uid = p_anon_uid then
    return 0;
  end if;

  with moved as (
    insert into ratings (task_id, rater_uuid, difficulty, time_est_minutes)
    select task_id, v_current_uid, difficulty, time_est_minutes
    from ratings
    where rater_uuid = p_anon_uid
    on conflict (task_id, rater_uuid) do nothing
    returning 1
  )
  select count(*)::int into v_inserted from moved;

  delete from ratings where rater_uuid = p_anon_uid;

  return v_inserted;
end;
$$;

revoke all on function merge_anon_ratings(text) from public;
grant execute on function merge_anon_ratings(text) to authenticated;
