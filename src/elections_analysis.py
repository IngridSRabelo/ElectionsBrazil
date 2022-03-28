import basedosdados as bd
import pandas as pd
import json
import matplotlib.pyplot as plt
import urllib.request
import plotly as plt
import plotly.express as px
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from ibge.localidades import Estados
import os

bd.list_dataset_tables(dataset_id='br_tse_eleicoes', with_description=True)

bd.get_table_columns(
    dataset_id='br_tse_eleicoes',
    table_id='despesas_candidato'
)

bd.get_table_columns(
    dataset_id='br_tse_eleicoes',
    table_id='resultados_candidato'
)

query1 = """
SELECT sigla_uf AS state_abbrev, nome_partido AS political_party,
valor_despesa AS expenses, id_candidato_bd, nome_candidato
FROM basedosdados.br_tse_eleicoes.despesas_candidato
WHERE ano = 2018 AND cargo = 'deputado federal'
"""
db1 = bd.read_sql(query1, billing_project_id='natural-axiom-342415')

query2 = """
SELECT id_candidato_bd, resultado AS result
FROM basedosdados.br_tse_eleicoes.resultados_candidato
WHERE ano = 2018 AND cargo = 'deputado federal'
"""
db2 = bd.read_sql(query2, billing_project_id='natural-axiom-342415')

# Expenses of Candidates for Federal Deputies in 2018,
# by political party, state and candidate
base = pd.merge(db1, db2, how='inner', on='id_candidato_bd')
base = base.groupby(["state_abbrev", "political_party", "id_candidato_bd", "result"]).agg(
    {"expenses": "sum"}).reset_index()

states_data = Estados()
states = states_data.getNome()
states_abbrev = states_data.getSigla()  # States and States abbreviation (IBGE)
loc = Nominatim(user_agent="GetLoc")  # Georeferencing function

states_lat_lon = pd.DataFrame(states_abbrev, states)
states_lat_lon = states_lat_lon.reset_index()
states_lat_lon = states_lat_lon.rename(
    columns={'index': 'state', 0: 'state_abbrev'}, index={})


def long(state):
    geoloc = loc.geocode(state)
    return geoloc.longitude


def lat(state):
    geoloc = loc.geocode(state)
    return geoloc.latitude


states_lat_lon['latitude'] = states_lat_lon['state'].apply(lambda x: lat(x))
states_lat_lon['longitude'] = states_lat_lon['state'].apply(
    lambda x: long(x))

total_db = pd.merge(base, states_lat_lon, how='inner', on='state_abbrev')

expenses_state_mean = total_db.groupby(["state", "state_abbrev", "latitude", "longitude"]).agg(
    {"expenses": "mean"}).sort_values('expenses', ascending=True).reset_index()
expenses_state_mean['expenses'] = expenses_state_mean['expenses'].round(
    decimals=2)
expenses_state_mean = expenses_state_mean.rename(
    columns={"expenses": "expenses_state_mean"})

elected_politicians = total_db[(total_db.result == 'eleito por qp') | (
    total_db.result == 'eleito por media')]

expenses_state_elected = elected_politicians.groupby(["state", "state_abbrev", "latitude", "longitude"]).agg(
    {"expenses": "mean"}).sort_values('expenses', ascending=True).reset_index()
expenses_state_elected['expenses'] = expenses_state_elected['expenses'].round(
    decimals=2)
expenses_state_elected = expenses_state_elected.rename(
    columns={"expenses": "expenses_state_elected"})

expenses_state = pd.merge(expenses_state_mean, expenses_state_elected, how='inner', on=[
    "state", "state_abbrev", "longitude", "latitude"])

expenses_political_party_mean = total_db.groupby(["political_party"]).agg(
    {"expenses": "mean"}).sort_values('expenses', ascending=True).reset_index()
expenses_political_party_mean['expenses'] = expenses_political_party_mean['expenses'].round(
    decimals=2)
expenses_political_party_mean = expenses_political_party_mean.rename(
    columns={"expenses": "expenses_political_party_mean"})

expenses_political_party_elected = elected_politicians.groupby(["political_party"]).agg(
    {"expenses": "mean"}).sort_values('expenses', ascending=True).reset_index()
expenses_political_party_elected['expenses'] = expenses_political_party_elected['expenses'].round(
    decimals=2)
expenses_political_party_elected = expenses_political_party_elected.rename(
    columns={"expenses": "expenses_political_party_elected"})

expenses_political_party = pd.merge(expenses_political_party_mean,
                                    expenses_political_party_elected, how='inner', on="political_party")

dir = os.path.dirname(__file__)
out_dir = os.path.abspath(os.path.join(dir, '..', 'out'))
if (not os.path.isdir(out_dir)):
    os.mkdir(out_dir)

# 1) Map with the average expenses of federal deputies, by state (2018)
br_shape_url = 'https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson'
with urllib.request.urlopen(br_shape_url) as response:
    # Polygons corresponding to the states of Brazil:
    Brazil = json.load(response)

state_id_map = {}
for feature in Brazil['features']:
    feature['id'] = feature['properties']['name']
    state_id_map[feature['properties']['sigla']] = feature['id']

map_state = px.choropleth(
    expenses_state,
    locations="state",
    geojson=Brazil,
    color="expenses_state_mean",
    labels={'expenses_state_mean': 'Average expense in BRL'},
    color_continuous_scale="Emrld",
    hover_name="state",
    hover_data=["expenses_state_mean", "longitude", "latitude"],
    title="How much, on average, is the value of electoral expenses" +
    " for a candidate for federal deputy? (2018)",
)
map_state.update_geos(fitbounds="locations", visible=False)

plt.offline.plot(map_state, filename=os.path.join(out_dir, 'map_state.html'))

# 2) Graphic: Showing the average electoral expenditure of candidates for federal deputy,
# by political party (2018)

graph_party = px.bar(expenses_political_party, x="expenses_political_party_mean", y="political_party",
                     color="expenses_political_party_mean",
                     color_continuous_scale="deep", orientation='h',
                     height=1000, labels={'expenses_political_party_mean': 'Average expense in BRL'},
                     title='Average electoral expenditure of candidates for federal deputy,' +
                     ' by political party (2018)',
                     text_auto='.2s')

plt.offline.plot(graph_party, filename=os.path.join(
    out_dir, 'graph_party.html'))

# 3) Graphs: Comparison between the average of electoral expenses of all candidates for deputy
# federal with the average of electoral expenses of candidates ELECTED for federal deputy (2018)

graph_comp_state = go.Figure(data=[
    go.Bar(name='Average electoral expenditure of candidates (all)', x=expenses_state
           ["expenses_state_mean"],
           y=expenses_state
           ["state"], orientation='h', marker_color='slateblue'),
    go.Bar(name='Average electoral expenditure of elected candidates', x=expenses_state
           ["expenses_state_elected"],
           y=expenses_state
           ["state"], orientation='h', marker_color='turquoise')
])
graph_comp_state.update_layout(title=go.layout.Title(
    text="Average electoral expenditure: All candidates X Elected candidates <br>" +
    "<sup>Candidates for federal deputy</sup>",
    xref="paper",
    x=0
),
    xaxis=go.layout.XAxis(
    title=go.layout.xaxis.Title(
        text="2018<br><sup>Average expenditure of candidates by state</sup>"
    )
), barmode='group', height=1000, width=1000)

plt.offline.plot(graph_comp_state, filename=os.path.join(
    out_dir, 'graph_comp_state.html'))

graph_comp_party = go.Figure(data=[
    go.Bar(name='Average electoral expenditure of candidates (all)', x=expenses_political_party["expenses_political_party_mean"],
           y=expenses_political_party["political_party"], orientation='h', marker_color='slateblue'),
    go.Bar(name='Average electoral expenditure of elected candidates', x=expenses_political_party["expenses_political_party_elected"],
           y=expenses_political_party["political_party"], orientation='h', marker_color='turquoise')
])
graph_comp_party.update_layout(title=go.layout.Title(
    text="Average electoral expenditure: All candidates X Elected candidates " +
    "<br><sup>Candidates for federal deputy</sup>",
    xref="paper",
    x=0
),
    xaxis=go.layout.XAxis(
    title=go.layout.xaxis.Title(
        text="2018<br><sup>Average expenditure of candidates by political party</sup>"
    )
), barmode='group', height=1000, width=1000)

plt.offline.plot(graph_comp_party, filename=os.path.join(
    out_dir, 'graph_comp_party.html'))
