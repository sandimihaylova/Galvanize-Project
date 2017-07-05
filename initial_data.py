import pandas as pd
from pulp import *
from random import random
import itertools

requests = pd.read_excel('data/sample_requests_min.xlsx')
contracts = pd.read_excel('data/sample_contracts_min.xlsx')

# Force multiple requests per sorite
# contracts = contracts[:1]
flight_times = pd.read_excel('data/sample_flight_times.xlsx')

prob = LpProblem('Tanker Assignment', LpMinimize)

# Variables
# Fake cost function
x = []
cost= []
for contract_id in contracts['id']:
    t= []
    ct = []
    for tanker_id in range(contracts['front_lines'][contract_id]):
        r = []
        cr = []
        for request_id in requests['id']:
            r.append(LpVariable("x_%s_%s:%s" % (contract_id, tanker_id, request_id), cat='Binary'))
            cr.append(random())
        t.append(r)
        ct.append(cr)
    x.append(t)
    cost.append(ct)

# Objective
obj = [zip(itertools.chain(*x[i]), itertools.chain(*cost[i])) for i in range(len(x))]
obj_flat = [item for sublist in obj for item in sublist]
prob += LpAffineExpression(obj_flat)

#Constraints

# Requests by sortie
x_tanker = [item for sublist in x for item in sublist]
# Satisfy all requests
for r in range(len(requests)):
    prob += lpSum([x_tanker[t][r] for t in range(len(x_tanker))]) == 1

# Sortie is time feasible
for t in x_tanker:
    prob += LpConstraint([flight_times[requests['airspace_id'][r]][requests['airspace_id'][r-1]] - \
    (requests['requested_at'][r] - requests['requested_at'][r-1]).seconds/60./60 \
    for r in range(1, len(requests))] >= 0)

# Sortie is fuel feasible



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
