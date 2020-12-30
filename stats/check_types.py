import os
import common
from utils import iter_proofs
from collections import defaultdict
import json
import pdb

cnt = defaultdict(int)
abnormal_proofs = set()
term_proofs = set()
abnormal_env_files = set()
# TODO check null type
# TODO check if multi terms exist eg. (a:= ss, b:=cc : type_expression)

def count_proof(filename, proof_data):
    global cnt
    global term_proofs
    global abnormal_proofs
    global abnormal_env_files
    tempname = proof_data['name']
    goal_dict = proof_data['goals']
    tempenv = proof_data['env']

    for xx in tempenv['constants']:
        if xx['type'] == None:
            abnormal_env_files.add(filename)
            break

    for tempgoalid in goal_dict:
        tempgoal = goal_dict[tempgoalid]
        if tempgoal['type'] == None:
            abnormal_proofs.add((filename, tempname))
        for temphypo in tempgoal['hypotheses']:
            if temphypo['type'] == None:
                abnormal_proofs.add((filename, tempname))
            if len(temphypo['term']) != 0:
                term_proofs.add((filename, tempname))

    proj = filename.split(os.path.sep)[2]


iter_proofs(common.data_root, count_proof, include_synthetic=False, show_progress=True)
print('')
print(cnt)
print(len(term_proofs))
print(len(abnormal_proofs))
print(len(abnormal_env_files))
term_files = set()
abnormal_files = set()
for xx in term_proofs:
    term_files.add(xx[0])

for xx in abnormal_proofs:
    abnormal_files.add(xx[0])

import pickle
with open('check_types_statistics.pk', 'wb') as pkfile:
    pickle.dump((abnormal_proofs, abnormal_env_files, term_proofs, term_files, abnormal_files), pkfile)