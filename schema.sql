create table if not exists games (
   id integer primary key autoincrement,
   game_date integer not null,
   weekday string not null,
   home_team integer not null, -- consider foreign key
   away_team integer not null,
   home_score integer not null,
   away_score integer not null,
   ot_or_so integer not null, -- 0 => regulation, 1 => overtime, 2 => shootout
   attendance integer not null
);

create table if not exists teams (
   id integer primary key autoincrement,
   city string not null,
   name string
);

