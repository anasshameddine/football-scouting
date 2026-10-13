with ligues as (
    select distinct league from {{ ref('stg_fbref_player_team_season') }}
),
pays as (select * from (values
    ('ENG-Premier League','GB1','Angleterre'), ('ESP-La Liga','ES1','Espagne'),
    ('ITA-Serie A','IT1','Italie'), ('GER-Bundesliga','L1','Allemagne'),
    ('FRA-Ligue 1','FR1','France'), ('NED-Eredivisie','NL1','Pays-Bas'),
    ('POR-Primeira Liga','PO1','Portugal'), ('BEL-Pro League','BE1','Belgique'),
    ('TUR-Super Lig','TR1','Turquie'), ('SCO-Premiership','SC1','Écosse'),
    ('AUT-Bundesliga','A1','Autriche'), ('SUI-Super League','C1','Suisse'),
    ('DEN-Superliga','DK1','Danemark'), ('KSA-Pro League','SA1','Arabie saoudite')
) as t(league, tm_competition, pays))
select l.league, p.tm_competition, p.pays,
       l.league in ('ENG-Premier League','ESP-La Liga','ITA-Serie A','GER-Bundesliga','FRA-Ligue 1') as est_big5
from ligues l left join pays p using (league)
