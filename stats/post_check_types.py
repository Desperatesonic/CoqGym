import pickle
import os
import common
from utils import iter_proofs

with open('check_types_statistics.pk', 'rb') as pkfile:
    abnormal_proofs, abnormal_env_files, term_proofs, term_files, abnormal_files = pickle.load(pkfile)

special_terms_proofs = set()

def count_proof(filename, proof_data):
    global cnt
    global term_proofs
    global abnormal_proofs
    global abnormal_env_files
    tempname = proof_data['name']
    if tempname not in term_proofs:
        return
    goal_dict = proof_data['goals']
    tempenv = proof_data['env']
    """
    for xx in tempenv['constants']:
        if xx['type'] == None:
            abnormal_env_files.add(filename)
            break
    """
    for tempgoalid in goal_dict:
        tempgoal = goal_dict[tempgoalid]
        #if tempgoal['type'] == None:
        #    abnormal_proofs.add((filename, tempname))
        for temphypo in tempgoal['hypotheses']:
        #    if temphypo['type'] == None:
        #        abnormal_proofs.add((filename, tempname))
            if len(temphypo['term']) > 1:
                special_terms_proofs.add((filename, tempname))

    proj = filename.split(os.path.sep)[2]


iter_proofs(common.data_root, count_proof, include_synthetic=False, show_progress=True)
print(special_terms_proofs)