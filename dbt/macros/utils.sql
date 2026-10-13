{# Convertit en nombre une colonne texte ou numérique (virgule des milliers, vide). #}
{% macro num(col) %}nullif(replace(({{ col }})::text, ',', ''), '')::numeric{% endmacro %}

{# Nom du schéma tel quel (sans préfixe "public_") #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}

{# Tranche de budget selon la valeur marchande (€) #}
{% macro tranche_budget(col) %}
case when {{ col }} is null then 'inconnu'
     when {{ col }} < {{ var('tranche_low_max') }} then 'low'
     when {{ col }} < {{ var('tranche_mid_max') }} then 'medium'
     when {{ col }} < {{ var('tranche_high_max') }} then 'high'
     else 'superstar' end
{% endmacro %}

{# Compteurs FBref conservés (nom de colonne dans le modèle) #}
{% macro compteurs_fbref() %}
{{ return([
  'performance_gls','performance_ast','performance_g_minus_pk','performance_pk','performance_pkatt',
  'performance_crdy','performance_crdr','performance_2crdy','performance_fls','performance_fld',
  'performance_off','performance_crs','performance_int','performance_tklw','performance_pkwon',
  'performance_pkcon','performance_og','standard_sh','standard_sot']) }}
{% endmacro %}

{# Compteurs Understat #}
{% macro compteurs_understat() %}
{{ return(['us_xg','us_np_xg','us_xa','us_shots','us_key_passes','us_xg_chain','us_xg_buildup']) }}
{% endmacro %}
