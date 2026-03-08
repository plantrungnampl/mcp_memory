alter table projects
  alter column isolation_mode set default 'falkordb_graph';

update projects
set isolation_mode = 'falkordb_graph'
where isolation_mode = 'neo4j_database';
