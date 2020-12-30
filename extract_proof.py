import os 
import json
from glob import glob
from utils import get_code, SexpCache, set_paths, extract_code, dst_filename
from serapi import SerAPI
from time import time
import sexpdata
from proof_tree import ProofTree
import pdb
import pickle

def check_topology(proof_steps):  # TODO what is the use of 'inductives'?
    'Only the first focused goal can be decomposed. This facilitates reconstructing the proof tree'
    # the proof starts with one focused goal
    if not (len(proof_steps[0]['goal_ids']['fg']) == 1 and proof_steps[0]['goal_ids']['bg'] == []):
        return False

    for i, step in enumerate(proof_steps[:-1]):
        step = step['goal_ids']
        next_step = proof_steps[i + 1]['goal_ids']
        if next_step['fg'] == step['fg'] and next_step['bg'] == step['bg']:  # all goals remain the same
            pass
        elif next_step['fg'] == step['fg'][1:] and next_step['bg'] == step['bg']:  # a focused goal is solved
            pass
        elif len(step['fg']) == 1 and next_step['fg'] == step['bg'] and next_step['bg'] == []:
            pass
        elif step['fg'] != [] and next_step['fg'] == [step['fg'][0]] and next_step['bg'] == step['fg'][1:] + step['bg']:  # zoom in
            pass
        elif step['fg'] == [] and next_step['fg'] == [step['bg'][0]] and next_step['bg'] == step['bg'][1:]:  # zoom out
            pass
        elif step['fg'] != [] and ''.join([str(x) for x in next_step['fg']]).endswith(''.join([str(x) for x in step['fg'][1:]])) and \
             step['fg'][0] not in next_step['fg'] and next_step['bg'] == step['bg']:  # a focused goal is decomposed
            pass
        else:
            return False

    return True


def goal_is_prop(goal, serapi):
    'Check if the sort of a goal is Prop'
    sort = serapi.query_type(goal['sexp'], return_str=True)
    return sort == 'Prop'


def record_proof(num_extra_cmds, line_nb, script, sexp_cache, serapi, args):

    proof_data = {
        'line_nb': num_extra_cmds + line_nb,
        'env': {},  # TODO get the env in proof_data0 when merging them
        'steps': [],
        'goals': {},
        'proof_tree': None,
    }
    """
    # get the global environment
    serapi.set_timeout(3600)
    constants, inductives = serapi.query_env(args.file[:-5] + '.vo')
    serapi.set_timeout(args.timeout)
    for const in constants:
        const['sexp'] = sexp_cache.dump(const['sexp'])
    for induct in inductives:
        induct['sexp'] = sexp_cache.dump(induct['sexp'])
    proof_data['env'] = {
        'constants': constants,
        'inductives': inductives,
    }"""

    # execute the proof
    for num_executed, (code_line, tags) in enumerate(script, start=line_nb + 1):
        if 'END_TACTIC' in tags:
            return None
        assert tags['VERNAC_TYPE'] != 'VernacProof'
        if tags['VERNAC_TYPE'] not in ['VernacEndProof', 'VernacBullet', 'VernacSubproof', 'VernacEndSubproof', 'VernacExtend']:
            return None

        # keep track of the goals
        fg_goals, bg_goals, shelved_goals, given_up_goals = serapi.query_goals()
        if shelved_goals + given_up_goals != []:
            return None
        if num_executed == 0:  # we only consider Prop
            assert fg_goals != []
            if not goal_is_prop(fg_goals[0], serapi):
                return None
        for g in fg_goals + bg_goals:
            g['sexp'] = sexp_cache.dump(g['sexp'])
            for i, h in enumerate(g['hypotheses']):
                g['hypotheses'][i]['sexp'] = sexp_cache.dump(h['sexp'])
            proof_data['goals'][g['id']] = g
        ast = sexpdata.dumps(serapi.query_ast(code_line))
        proof_data['steps'].append({'command': (code_line, tags['VERNAC_TYPE'], sexp_cache.dump(ast)),
                                    'goal_ids': {'fg': [g['id'] for g in fg_goals],
                                                 'bg': [g['id'] for g in bg_goals]}
                                   })

        # run the tactic
        if args.debug:
            print('PROOF %d: %s' % (num_executed, code_line))
        serapi.execute(code_line)

        # the proof ends
        if tags['VERNAC_TYPE'] == 'VernacEndProof':
            break

    if not check_topology(proof_data['steps']):
        return None
    proof_data['proof_tree'] = ProofTree(proof_data['steps'], proof_data['goals']).to_dict()

    return proof_data
    

def get_proof(args):


    coq_filename = os.path.splitext(args.file)[0] + '.v'
    fields = coq_filename.split(os.path.sep)
    loc2code = get_code(open(coq_filename, 'rb').read())
    meta = open(args.file).read()
    coq_code = extract_code(meta, loc2code)
    with open(os.path.join(args.data_path, args.file[13:-5] + '.json'), "r") as json_data:
        file_data = json.load(json_data)
    with open(args.file0, "r") as json_data:
        proof_data0 = json.load(json_data)
    proof_data0 = [tempdic['name'] for tempdic in proof_data0['proofs']]
    for tempproof in file_data['proofs']:
        args.proof = tempproof
        if tempproof not in proof_data0:
            continue
        if os.path.isfile(os.path.join(dirname, args.proof + '.json')):  # tempproof != 'loc_unconstrained_satisf':
            continue
        db_path = os.path.join(dirname, args.proof + '-sexp_cache')
        sexp_cache = SexpCache(db_path)

        with SerAPI(args.timeout, args.debug) as serapi:
            num_extra_cmds = len(set_paths(meta, serapi, sexp_cache))

            # process the coq code
            proof_start_lines = []
            in_proof = False
            for num_executed, (code_line, tags) in enumerate(coq_code):
                assert code_line == file_data['vernac_cmds'][num_extra_cmds + num_executed][0]
                if 'PROOF_NAME' in tags and tags['PROOF_NAME'] == args.proof:  # the proof ends
                    serapi.pop()
                    line_nb = proof_start_lines[-1]

                    proof_data = record_proof(num_extra_cmds, line_nb, coq_code[line_nb + 1:], sexp_cache, serapi, args)
                    if proof_data is not None:
                        dump(proof_data, args)
                    break
                # execute the code
                if args.debug:
                    print('%d: %s' % (num_executed, code_line))
                serapi.execute(code_line)
                if serapi.has_open_goals():
                    if not in_proof:  # the proof starts
                        in_proof = True
                        proof_start_lines.append(num_executed)
                        serapi.push()
                else:
                    in_proof = False

    return


def dump(proof_data, args):
    dirname = dst_filename(args.file, args.data_path) + '-PROOFS'
    with open(os.path.join(dirname, args.proof + '.json'), 'wt') as json_data:
        json.dump(proof_data, json_data)
        print('dump ' + args.proof)
  
if __name__ == '__main__':
    import sys
    sys.setrecursionlimit(100000)
    import argparse
    arg_parser = argparse.ArgumentParser(description='Extract the proofs from Coq source code')
    arg_parser.add_argument('--debug', action='store_true')
    arg_parser.add_argument('--file', type=str, help='The meta file to process')
    arg_parser.add_argument('--file0', type=str, help='The json file in original program')
    arg_parser.add_argument('--proof', type=str, help='The proof to extract')
    arg_parser.add_argument('--timeout', type=int, default=600, help='Timeout for SerAPI')
    arg_parser.add_argument('--filter', type=str, default='')
    arg_parser.add_argument('--data_path0', type=str, default='./data')
    arg_parser.add_argument('--data_path', type=str, default='./data2')
    args = arg_parser.parse_args()
    print(args)
    #targetfiles = glob(os.path.join(args.data_path0, '**/*.json'))

    meta_files = list(glob('coq_projects/**/*.meta', recursive=True))
    meta_files.sort()

    with open('./stats/check_types_statistics.pk', 'rb') as pkfile:
        abnormal_proofs, abnormal_env_files, term_proofs, term_files, abnormal_files = pickle.load(pkfile)
    new_meta_files = []
    for i, filename in enumerate(meta_files):
        targetfile = args.data_path0+filename[12:-5]+'.json'
        if not os.path.isfile(targetfile):
            continue
        if '.'+targetfile not in abnormal_files:
            continue
        new_meta_files.append(filename)
    print('%d Coq files to process' % len(new_meta_files))
    # process each of them
    for i, filename in enumerate(new_meta_files):
        if args.filter and i % 8 != int(args.filter):
            continue
        targetfile = args.data_path0+filename[12:-5]+'.json'
        print(targetfile)
        dirname = dst_filename(filename, args.data_path) + '-PROOFS'
        args.file = filename
        args.file0 = targetfile
        try:
            os.makedirs(dirname)
        except os.error:
             pass

        get_proof(args)

