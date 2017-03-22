import cPickle as pickle
import sys

try:
    fn = sys.argv[1]
except IndexError:
    print 'Usage: read_pkl_example.py <filename>'
    exit()

with open(fn, 'r') as fh:
    x = pickle.load(fh)

times = x['times']
data  = x['data']

print 'There are %d times in file %s' % (len(times), fn)

print 'Times:'
print times

print 'Data dictionary has keys:'
print data[0].keys()

print 'First data entry:'
for vis, vals in data[0].iteritems():
    print vis
    print vals

