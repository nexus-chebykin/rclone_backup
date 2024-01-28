import sys
import pathlib

s = [sys.argv[1], sys.argv[2]]


def build_dict(file):
    d = dict()

    for line in open(file, 'r'):
        tmp = line.split()
        h = tmp[0]
        filename = ' '.join(tmp[1:])
        path = pathlib.Path(filename)
        d.setdefault((h, path.name), []).append(path)
    return d


d = [build_dict(x) for x in s]
for k in set(d[0].keys()).union(set(d[1].keys())):
    l1 = d[0].get(k, [])
    l2 = d[1].get(k, [])
    if len(l1) > len(l2):
        print(f'{l1} != {l2}')
