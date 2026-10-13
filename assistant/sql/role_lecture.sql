-- Rôle PostgreSQL en lecture seule pour l'agent texte vers SQL (défense en profondeur).
-- Même si une requête dangereuse passait les vérifications Python, ce rôle ne peut rien modifier.
--
--   Get-Content assistant\sql\role_lecture.sql | docker exec -i scouting_postgres psql -U scout -d scouting
--
-- Puis, dans .env (adapter le port à celui de POSTGRES_PORT) :
--   ASSISTANT_DB_URL=postgresql+psycopg2://scout_lecteur:lecture_seule@localhost:5432/scouting

do $$
begin
    if not exists (select from pg_roles where rolname = 'scout_lecteur') then
        create role scout_lecteur login password 'lecture_seule';
    end if;
end $$;

alter role scout_lecteur set default_transaction_read_only = on;
alter role scout_lecteur set statement_timeout = '10s';

grant connect on database scouting to scout_lecteur;
grant usage on schema gold, ml to scout_lecteur;
grant select on all tables in schema gold, ml to scout_lecteur;
-- les tables recréées par dbt gardent ce droit :
alter default privileges in schema gold grant select on tables to scout_lecteur;
alter default privileges in schema ml grant select on tables to scout_lecteur;
