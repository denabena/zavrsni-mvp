-- Migracija ratinga: stari task_id -> novi task_id.
-- Generirano iz tasks.old.json + tasks.json poredanog po picker-pravilu
-- (prvi entry s tim task_id-om u tasks.old.json odlučuje image_path).
--
-- Stari unique task_ids: 108
-- Nepromijenjeni:        100  (nema SQL-a, ratings već OK)
-- Za migraciju:           8
-- Orphan (drop ratings):  0

begin;

-- 1) Update task_id na novi format.
UPDATE ratings SET task_id = 'MI|2012-04-25|1' WHERE task_id = 'MI|25.travnja 2012|1';
UPDATE ratings SET task_id = 'MI|2012-04-25|2' WHERE task_id = 'MI|25.travnja 2012|2';
UPDATE ratings SET task_id = 'MI|2012-04-25|3' WHERE task_id = 'MI|25.travnja 2012|3';
UPDATE ratings SET task_id = 'MI|2012-04-25|4' WHERE task_id = 'MI|25.travnja 2012|4';
UPDATE ratings SET task_id = 'MI|2012-04-25|5' WHERE task_id = 'MI|25.travnja 2012|5';
UPDATE ratings SET task_id = 'MI|2011-05-02|6' WHERE task_id = 'MI|25.travnja 2012|6';
UPDATE ratings SET task_id = 'ZI|2011-06-13|5' WHERE task_id = 'ZI|2012-06-20|5';
UPDATE ratings SET task_id = 'ZI|2010-07-02|6' WHERE task_id = 'ZI|2012-06-20|6';

commit;