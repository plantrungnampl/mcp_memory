alter table fact_versions
  add column if not exists salience_class text not null default 'WARM';

alter table entities
  add column if not exists salience_score numeric not null default 0.5,
  add column if not exists salience_class text not null default 'WARM';

alter table episodes
  add column if not exists salience_score numeric not null default 0.5,
  add column if not exists salience_class text not null default 'WARM';

update fact_versions
set salience_score = coalesce(salience_score, 0.5)
where salience_score is null;

update fact_versions
set salience_class = 'WARM'
where salience_class is null
   or btrim(salience_class) = '';
