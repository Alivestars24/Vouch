begin;
select plan(12);

select has_schema('vouch', 'API and worker runtime schema exists');
select ok(
  exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'vouch' and c.relkind in ('r', 'p')),
  'runtime migration creates persistence tables'
);
select ok(not has_schema_privilege('anon', 'vouch', 'USAGE,CREATE'),
  'anonymous users cannot reach or create runtime objects');
select ok(not has_schema_privilege('authenticated', 'vouch', 'USAGE,CREATE'),
  'authenticated Data API cannot reach or create runtime objects');
select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
   cross join (values ('anon'), ('authenticated')) as client_role(name)
   where n.nspname = 'vouch' and c.relkind in ('r', 'p', 'v', 'm', 'f')
     and has_table_privilege(client_role.name, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')),
  0, 'no runtime table or view grants leak to Data API roles'
);
select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
   cross join (values ('anon'), ('authenticated')) as client_role(name)
   where n.nspname = 'vouch' and c.relkind = 'S'
     and has_sequence_privilege(client_role.name, c.oid, 'USAGE,SELECT,UPDATE')),
  0, 'no runtime sequence grants leak to Data API roles'
);
select is(
  (select count(*)::integer from pg_proc p join pg_namespace n on n.oid = p.pronamespace
   cross join (values ('anon'), ('authenticated')) as client_role(name)
   where n.nspname = 'vouch' and has_function_privilege(client_role.name, p.oid, 'EXECUTE')),
  0, 'no runtime function is callable by Data API roles'
);
select is(
  (select count(*)::integer from pg_type t join pg_namespace n on n.oid = t.typnamespace
   cross join (values ('anon'), ('authenticated')) as client_role(name)
   -- PostgreSQL generates row and array types for tables. Their implicit USAGE
   -- does not bypass the schema and relation access checks tested above.
   where n.nspname = 'vouch' and t.typrelid = 0 and t.typelem = 0
     and has_type_privilege(client_role.name, t.oid, 'USAGE')),
  0, 'no independently created runtime type grants leak to Data API roles'
);

set local role authenticated;
select throws_ok($$select * from vouch.organizations$$, '42501', null,
  'authenticated Data API cannot read private runtime organizations');
select throws_ok($$insert into vouch.organizations default values$$, '42501', null,
  'authenticated Data API cannot write private runtime organizations');
set local role anon;
select throws_ok($$select * from vouch.organizations$$, '42501', null,
  'anonymous users cannot read private runtime organizations');
select throws_ok($$insert into vouch.organizations default values$$, '42501', null,
  'anonymous users cannot write private runtime organizations');

select * from finish();
rollback;
