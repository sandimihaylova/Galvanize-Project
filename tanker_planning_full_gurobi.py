import pandas as pd
import numpy as np
from gurobipy import *
from random import random
import itertools
import datetime


requests = pd.read_excel('data/sample_day.xlsx', sheetname='fuel_request')
requests = requests.sort_values('requested_at')
requests['index'] = np.arange(len(requests))
contracts = pd.read_excel('data/sample_day.xlsx', sheetname='contract')
flight_times = pd.read_excel('data/sample_day.xlsx', sheetname='flight_times')
compatibility = pd.read_excel('data/sample_day.xlsx', sheetname='compatibility')
contract_compatibility = pd.read_excel('data/sample_day.xlsx', sheetname='j_contract_configured_tanker')

# Model
m = Model("Tanker Planning")


# Compatibilities
ci = []
[ci.append(c) for c in list(contract_compatibility.contract_id) if c in list(contracts.id)]

config_contract = {}
for c in ci:
    configs = list(contract_compatibility['configured_tanker_Id'][contract_compatibility['contract_id']==c])
    config_contract.setdefault(c, configs)

for c in range(len(contracts)):
    if contracts['id'][c] not in config_contract:
        contracts.drop(c, inplace=True)

contracts = contracts.reset_index()

compat_cti = list(compatibility.configured_tanker_id)
compat_ri = list(compatibility.receiver_id)
compat = zip(compat_cti, compat_ri)
compats = {}
for c_tanker, receiver in compat:
    compats.setdefault(c_tanker, []).append(receiver)

request_id = list(requests.index)
receiver_id = list(requests.receiver_id)
req = zip(receiver_id, request_id)
req_by_receiver = {}
for receiver, request in req:
    req_by_receiver.setdefault(receiver, []).append(request)

requests_for_config_tanker = {}
for t in compats:
    for i in range(len(compats[t])):
        if compats[t][i] in req_by_receiver:
            requests_for_config_tanker.setdefault(t, []).extend(req_by_receiver[compats[t][i]])


base_request = list(contracts['base_id']) + list(requests['index'])
request_request = list(requests['index'])
request_base = list(requests['index']) + list(contracts['base_id'])

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
    if (p[0] in destinations) and (p[1] in destinations):
        if (p[0] in list(contracts['base_id'])) and (p[1] in list(contracts['base_id'])):
            continue
        elif (p[0] in list(contracts['base_id'])) or (p[1] in list(contracts['base_id'])):
            edges.append(p)
            edge_times.append(flight_times[destinations[p[0]]][destinations[p[1]]])
        elif (p[0] not in list(contracts['base_id'])) and (p[1] not in list(contracts['base_id'])):
            transit_time = flight_times[destinations[p[0]]][destinations[p[1]]]
            time_between = (requests['requested_at'][p[1]] - requests['requested_at'][p[0]]).seconds/60.
            if (time_between >= transit_time) and (time_between - transit_time <= 60):
                edges.append(p)
                edge_times.append(time_between)


x = []
compatible= []
for c in range(len(contracts)):
    xt= []
    ct = []
    for tanker_id in range(contracts['front_lines'][c]):
        xr = []
        cr = []
        for config_id in config_contract[contracts['id'][c]]:
            xrc = []
            crc = []
            for request_id in requests['id']:
                xrc.append(m.addVar(vtype=GRB.BINARY,
                                    # obj=compatible[c][t][config_id][request_id],
                                    name="x_%s_%s (%s): %s" % (contracts['id'][c], tanker_id, config_id, request_id)))
                if config_id in requests_for_config_tanker:
                    crc.append(1 if int(requests['index'][requests['id']==request_id]) in requests_for_config_tanker[config_id] else 0)
                elif config_id not in requests_for_config_tanker:
                    crc.append(0)
            xr.append(xrc)
            cr.append(crc)
        xt.append(xr)
        ct.append(cr)
    x.append(xt)
    compatible.append(ct)

y = []
times = []
for c in range(len(contracts)):
    yt = []
    t_times = []
    for tanker_id in range(contracts['front_lines'][c]):
        yr = []
        r_times = []
        for config_id in config_contract[contracts['id'][c]]:
            yrc = []
            r_times_c = []
            for i in range(len(edges)):
                yrc.append(m.addVar(vtype=GRB.BINARY,
                                    obj=edge_times[i],
                                    name="y_%s_%s (%s):%s_%s" % (contracts['id'][c], tanker_id, config_id, edges[i][0], edges[i][1])))
                r_times_c.append(edge_times[i])
            yr.append(yrc)
            r_times.append(r_times_c)
        yt.append(yr)
        t_times.append(r_times)
    y.append(yt)
    times.append(t_times)

m.update()
m.modelSense = GRB.MINIMIZE

sorties = 0
for c in range(len(contracts)):
    for t in range(contracts['front_lines'][c]):
        for i in range(len(config_contract[contracts['id'][c]])):
            sorties += quicksum(y[c][t][i][j] for j in range(len(edges)) \
            if edges[j][0] == contracts['base_id'][c])

m.setObjective(sorties)

#Constraints

# Satisfy all requests

for r in range(len(requests)):
    m.addConstr(quicksum(x[c][t][i][r] for c in range(len(contracts)) \
    for t in range(len(x[c])) \
    for i in range(len(x[c][t]))) == 1)


# # Fuel feasible constraint
for c in range(len(x)):
    for t in range(len(x[c])):
        for i in range(len(x[c][t])):
            disposable_fuel = contracts['takeoff_fuel'][c] - contracts['climbout_fuel'][c] - contracts['fuel_reserves'][c] + contracts['over_frag'][c]
            offloaded = quicksum(x[c][t][i][r] * requests['amount'][r] for r in range(len(requests)))
            time_inflight = quicksum(y[c][t][i][e] * times[c][t][i][e] for e in range(len(edges)))
            fuel_burned = time_inflight/60. * contracts['avg_burn_rate_per_hr'][c]
            m.addConstr(offloaded + fuel_burned <= disposable_fuel)


# One configuration per tanker
for c in range(len(x)):
    for t in range(len(x[c])):
        m.addConstr(quicksum(y[c][t][i][j] for i in range(len(x[c][t])) for j in range(len(edges)) \
        if edges[j][0] == contracts['base_id'][c]) <= 1)

# edge variables reflect node variables

for c in range(len(x)):
    for t in range(len(x[c])):
        for i in range(len(x[c][t])):
            for r in range(len(requests)):
                outbound = quicksum(y[c][t][i][j] for j in range(len(edges)) if r == edges[j][0])
                inbound = quicksum(y[c][t][i][j] for j in range(len(edges)) if r == edges[j][1])
                homebase = quicksum(y[c][t][i][j] for j in range(len(edges)) if contracts['base_id'][c] in edges[j])
                not_homebase = quicksum(y[c][t][i][j] for j in range(len(edges)) \
                if (edges[j][0] in list(contracts['base_id']) and (contracts['base_id'][c] not in edges[j])))
                m.addConstr(x[c][t][i][r] == inbound)
                m.addConstr(x[c][t][i][r] == outbound)
                m.addConstr(homebase <= 2)
                m.addConstr(not_homebase == 0)


# only pair compatible requests
for c in range(len(x)):
    for t in range(len(x[c])):
        for i in range(len(x[c][t])):
            for r in range(len(requests)):
                m.addConstr(x[c][t][i][r] <= compatible[c][t][i][r])

m.update()
m.write('gurobi_out.lp')
m.optimize()

# Print solution
print('\nTOTAL COSTS: %g' % m.objVal)
print('SOLUTION:')
for c in range(len(x)):
    for t in range(len(x[c])):
        for i in range(len(x[c][t])):
            for r in range(len(requests)):
                if x[c][t][i][r].x > 0:
                    print x[c][t][i][r]
