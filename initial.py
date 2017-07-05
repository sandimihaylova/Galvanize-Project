
from pulp import *
import itertools

locations = ['ADAB', 'INCK', 'Mariners', 'Braves', 'Red Sox']
times = [[0, 10, 15, 20, 25], [10, 0, 30, 40, 50], [15, 30, 0, 5, 10], \
        [20, 40, 5, 0, 10], [25, 50, 10, 10, 0]]


tanker = ['ADAB', 'INCK']
tankers = {'ADAB': 110, 'INCK': 150}

requests = [1,2,3]
amount = [20,30,60]

# travel_time = {'ADAB':{'ADAB':0, 'INCK':10}}

travel= {}
for location, time in zip(locations, times):
    travel[location]={}
    for dest, cost in zip(locations, time):
        travel[location][dest]=cost

amounts = {}
for r, a in zip(requests, amount):
    amounts[r] = a

airspaces = ['Mariners', 'Braves','Red Sox']
airspace = {}
for r, a in zip(requests, airspaces):
    airspace[r] = a


cost = []
for r in requests:
    cost.append([travel[t][airspace[r]] + amounts[r] for t in tanker])


prob = LpProblem('Tanker Assignment', LpMinimize)
x = [[LpVariable("x_%s,%s" % (t, request), cat='Binary') for t in tanker] for request in requests]

prob += LpAffineExpression(zip(itertools.chain(*x), itertools.chain(*cost)))

for r in range(len(requests)):
    prob += lpSum([x[r][t] for t in range(len(tanker))]) == 1

for t in range(len(tanker)):
    prob += lpSum([x[r][t] * cost[r][t] for r in range(len(requests))]) <= tankers[tanker[t]]

prob.writeLP("prob.lp")
prob.solve()


def print_lp_report(prob):
    print "Status:", LpStatus[prob.status]
    print "-----"
    for v in prob.variables():
        print v.name, "=", v.varValue
    print "-----"
    print "Total cost: ", value(prob.objective)


print_lp_report(prob)
