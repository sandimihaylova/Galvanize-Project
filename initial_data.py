import pandas as pd
from pulp import *
from random import random
import itertools

requests = pd.read_excel('data/sample_requests_min.xlsx')
#TODO sort by requestsed at and reasssign index
# requests = requests.sort_values('requested_at')
contracts = pd.read_excel('data/sample_contracts_min.xlsx')
flight_times = pd.read_excel('data/sample_flight_times.xlsx')


prob = LpProblem('Tanker Assignment', LpMinimize)

# Variables
# TODO fix cost function, minimize fuel remaining/sorties, et
# TODO configuration combaitibility


base_request = list(contracts['base_id']) + list(requests['id'])
request_request = list(requests['id'])
request_base = list(requests['id']) + list(contracts['base_id'])

destination_airspace = list(contracts['base_id']) + list(requests['airspace_id'])
destinations = dict(zip(base_request, destination_airspace))

path_list = list(itertools.combinations(base_request,2)) +\
list(itertools.combinations(request_request,2)) +\
list(itertools.combinations(request_base,2))

paths = []
for path in path_list:
    if path not in paths:
        paths.append(path)


# only time feasible edges
edges = []
edge_times = []
for p in paths:
    if p[0] in requests['id'] and p[1] in requests['id']:
        transit_time = flight_times[destinations[p[0]]][destinations[p[1]]]
        time_between = (requests['requested_at'][p[1]] - requests['requested_at'][p[0]]).seconds/60.
        if time_between >= transit_time:
            edges.append(p)
            edge_times.append(time_between)
    elif p[0] not in requests['id'] and p[1] not in requests['id']:
        continue
    else:
        edges.append(p)
        edge_times.append(flight_times[destinations[p[0]]][destinations[p[1]]])


x = []
y = []
cost= []
times = []
for contract_id in contracts['id']:
    xt= []
    yt = []
    ct = []
    t_times = []
    for tanker_id in range(contracts['front_lines'][contract_id]):
        xr = []
        yr = []
        cr = []
        r_times = []
        for request_id in requests['id']:
            xr.append(LpVariable("x_%s_%s:%s" % (contract_id, tanker_id, request_id), cat='Binary'))
            cr.append(random())
        for i in range(len(edges)):
            yr.append(LpVariable("y_%s_%s:%s_%s" % (contract_id, tanker_id, edges[i][0], edges[i][1]), cat='Binary',lowBound=0))
            r_times.append(edge_times[i])
        xt.append(xr)
        yt.append(yr)
        t_times.append(r_times)
        ct.append(cr)
    x.append(xt)
    y.append(yt)
    times.append(t_times)
    cost.append(ct)


# Objective
obj = [zip(itertools.chain(*x[i]), itertools.chain(*cost[i])) for i in range(len(x))]
travel = [zip(itertools.chain(*y[i]), itertools.chain(*times[i])) for i in range(len(y))]
obj_flat = [item for sublist in obj for item in sublist]
travel_flat = [item for sublist in travel for item in sublist]
prob += LpAffineExpression(obj_flat)
prob += LpAffineExpression(travel_flat)

#Constraints

# Requests by sortie
x_tanker = [item for sublist in x for item in sublist]
# Satisfy all requests
for r in range(len(requests)):
    prob += lpSum([x_tanker[t][r] for t in range(len(x_tanker))]) == 1


# Fuel feasible constraint
# fuel burned based off of transit time, not loiter
for c in range(len(x)):
    for t in range(len(x[c])):
        disposable_fuel = contracts['takeoff_fuel'][c] - contracts['climbout_fuel'][c] - contracts['fuel_reserves'][c] + contracts['over_frag'][c]
        offloaded = lpSum([x[c][t][r] * requests['amount'][r] for r in range(len(requests))])
        time_inflight = lpSum([y[c][t][e] * times[c][t][e] for e in range(len(edges))])
        fuel_burned = time_inflight/60. * contracts['avg_burn_rate_per_hr'][c]
        prob += offloaded + fuel_burned <= disposable_fuel

# edge variables reflect node variables
for c in range(len(x)):
    for t in range(len(x[c])):
        for r in range(len(requests)):
            inbound = lpSum([y[c][t][i] for i in range(len(edges)) if r == edges[i][0]])
            outbound = lpSum([y[c][t][i] for i in range(len(edges)) if r == edges[i][1]])
            homebase = lpSum([y[c][t][i] for i in range(len(edges)) if contracts['base_id'][c] in edges[i]])
            prob += x[c][t][r] == inbound
            prob += x[c][t][r] == outbound
            prob += homebase == 2

prob.writeLP("prob_data.lp")
prob.solve()


def print_lp_report(prob):
    print "Status:", LpStatus[prob.status]
    print "-----"
    for v in prob.variables():
        print v.name, "=", v.varValue
    print "-----"
    print "Total cost: ", value(prob.objective)


print_lp_report(prob)
