create table if not exists anchors (
  id text primary key,
  x  double precision not null,
  y  double precision not null
);

insert into anchors(id,x,y) values
  ('A1',0.0,0.0),
  ('A2',6.0,0.0),
  ('A3',6.0,3.5),
  ('A4',0.0,3.5);

create table if not exists tags (
  id text primary key,
  description text
);

insert into tags(id, description) values
  ('tag01','Moto 01'),
  ('tag02','Moto 02'),
  ('tag03','Moto 03');

create table if not exists positions (
  id bigserial primary key,
  tag_id text not null references tags(id),
  x double precision not null,
  y double precision not null,
  created_at timestamptz not null default now()
);

create index if not exists positions_tag_time on positions(tag_id, created_at desc);

create table if not exists ranging (
  id bigserial primary key,
  tag_id text not null references tags(id),
  anchor_id text not null references anchors(id),
  distance_m double precision not null,
  created_at timestamptz not null default now()
);

create index if not exists ranging_tag_time on ranging(tag_id, created_at desc);

create table if not exists events (
  id bigserial primary key,
  tag_id text not null references tags(id),
  type text not null,
  payload jsonb,
  created_at timestamptz not null default now()
);

create index if not exists events_tag_time on events(tag_id, created_at desc);