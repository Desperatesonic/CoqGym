import os
import lmdb
from progressbar import ProgressBar
import json
from glob import glob
import pdb


def merge_lmdbs():
    print('merging the LMDB files..')
    'merge all the LMDB databases in data/ into one'
    db_path = 'sexp_cache2'
    dst_db = lmdb.open(db_path, map_size=1e11, writemap=True, readahead=False)
    files = glob('data/**/*sexp_cache', recursive=True)

    bar = ProgressBar(max_value=len(files))
    for i, db_path in enumerate(files):
        print(db_path)
        try:
            src_db = lmdb.open(db_path, map_size=1e11, readonly=True, readahead=True, lock=False)
        except lmdb.Error as ex:
            print(ex)
            continue
        with src_db.begin() as txn1:
            cursor = txn1.cursor()
            for key, value in cursor:
                with dst_db.begin(write=True) as txn2:
                    txn2.put(key, value, dupdata=False, overwrite=False)
        src_db.close()
        os.system('rm -r "%s"' % db_path)
        bar.update(i)

    dst_db.close()


def env_diff(new_env, old_env):
    add = {'constants': [json.loads(const) for const in new_env['constants'] if const not in old_env['constants']],
           'inductives': [json.loads(induct) for induct in new_env['inductives'] if induct not in old_env['inductives']]}
    subtract = {'constants': [json.loads(const) for const in old_env['constants'] if const not in new_env['constants']],
                'inductives': [json.loads(induct) for induct in old_env['inductives'] if induct not in new_env['inductives']]}
    env_delta = {'add': add, 'subtract': subtract}
    return env_delta


def merge_proofs():
    print('merging the proof files..')
    files = [f for f in glob('data2/**/*.json', recursive=True) if 'PROOFS' not in f]

    bar = ProgressBar(max_value=len(files))
    for i, f in enumerate(files):
        file_data = json.load(open(f))
        proofs = []
        env = {'constants': [], 'inductives': []}

        # merge the files for the human proofs
        for proof_name in file_data['proofs']:
            proof_file = f[:-5] + '-PROOFS/' + proof_name + '.json'
            if not os.path.exists(proof_file):
                continue
            proof_data = json.load(open(proof_file))
            for j, const in enumerate(proof_data['env']['constants']):
                proof_data['env']['constants'][j] = json.dumps(proof_data['env']['constants'][j])
            for j, const in enumerate(proof_data['env']['inductives']):
                proof_data['env']['inductives'][j] = json.dumps(proof_data['env']['inductives'][j])

            env_delta = env_diff(proof_data['env'], env)
            env = proof_data['env']

            proofs.append({'name': proof_name, 'line_nb': proof_data['line_nb'], 'env_delta': env_delta,
                           'steps': proof_data['steps'], 'goals': proof_data['goals'], 'proof_tree': proof_data['proof_tree']})

        # merge the synthetic proofs
        synthetic_proofs = {}
        for sf in glob(f[:-5] + '-SUBPROOFS/*.json'):
            proof_name = sf.split('/')[-1][:-5]
            subprf_data = json.load(open(sf))
            synthetic_proofs[proof_name] = subprf_data

        file_data['proofs'] = proofs
        file_data['synthetic_proofs'] = synthetic_proofs
        if proofs != []:
            json.dump(file_data, open(f, 'wt'))
        os.system('rm -r ' + f[:-5] + '-*PROOFS')

        bar.update(i)

def merge_proofs2():
    print('merging the proof files..')
    files = [f for f in glob('data/**/*.json', recursive=True) if 'PROOFS' not in f]
    files2 = [f for f in glob('data2/**/*.json', recursive=True) if 'PROOFS' not in f]
    rmfiles = []
    for f in files2:
        if 'data'+f[5:] not in files:
            os.system('rm ' + f)
    bar = ProgressBar(max_value=len(files))
    for i, f in enumerate(files):

        with open(f, 'r') as jsonfile:
            file_data = json.load(jsonfile)

        proof_file2 = 'data2' + f[4:]
        if os.path.exists(proof_file2) and os.path.exists(proof_file2[:-5] + '-PROOFS'):

            # merge the files for the human proofs
            for itemindex in range(len(file_data['proofs'])):
                proof_item = file_data['proofs'][itemindex]
                proof_name = proof_item['name']
                proof_name2 = proof_file2[:-5] + '-PROOFS/' + proof_name + '.json'
                if os.path.exists(proof_name2):

                    proof_data2 = json.load(open(proof_name2))

                    for tempkey in proof_item['goals']:
                        assert tempkey in proof_data2['goals']
                        g2 = proof_data2['goals'][tempkey]
                        g1 = proof_item['goals'][tempkey]
                        if g1['type'] != g2['type']:
                            g1['type'] = g2['type']
                        assert len(g1['hypotheses']) == len(g2['hypotheses'])
                        for j in range(len(g1['hypotheses'])):
                            h1 = g1['hypotheses'][j]
                            h2 = g2['hypotheses'][j]
                            if h1['type'] != h2['type']:
                                h1['type'] = h2['type']

            os.system('rm -r ' + proof_file2[:-5] + '-*PROOFS')
        json.dump(file_data, open(proof_file2, 'wt'))

        bar.update(i)

def merge_synthetic_proofs():
    dirnames = glob('data/**/*-SUBPROOFS', recursive=True)

    bar = ProgressBar(max_value=len(dirnames))
    for i, d in enumerate(dirnames):
        filename = d[:-10] + '.json'
        if not os.path.exists(filename):
            continue
        file_data = json.load(open(filename))
        file_data['synthetic_proofs'] = {}
        for f in glob(os.path.join(d, '*.json')):
            proof_name = f.split('/')[-1][:-5]
            subprf_data = json.load(open(f))
            file_data['synthetic_proofs'][proof_name] = subprf_data
        json.dump(file_data, open(filename, 'wt'))
        os.system('rm %s/*.json' % d)
        bar.update(i)

def compare_types():
    files = [f for f in glob('data2/**/*.json', recursive=True) if 'PROOFS' not in f]
    exceptionset = set()
    exceptionlist = list()
    bar = ProgressBar(max_value=len(files))
    for i, f in enumerate(files):
        proof_file0 = 'data' + f[5:]
        if not os.path.exists(proof_file0):
            continue
        with open (proof_file0, 'r') as jsonfile:
            file_data0 = json.load(jsonfile)
        with open (f, 'r') as jsonfile:
            file_data = json.load(jsonfile)
        proofs = []
        proof_data0 = file_data0['proofs']
        proof_name_list = [xx['name'] for xx in proof_data0]
        proof_dict = {xx['name']: xx for xx in proof_data0}
        # merge the files for the human proofs
        for proof_name in file_data['proofs']:
            proof_file = f[:-5] + '-PROOFS/' + proof_name + '.json'
            if not os.path.exists(proof_file):
                continue
            if proof_name not in proof_name_list:
                continue
            temp_proof_data = proof_dict[proof_name]
            proof_data = json.load(open(proof_file))
            assert len(proof_data['goals']) == len(temp_proof_data['goals'])
            for tempkey in proof_data['goals']:
                assert tempkey in temp_proof_data['goals']
                g1 = temp_proof_data['goals'][tempkey]
                g2 = proof_data['goals'][tempkey]
                assert g2['type'] != None
                if g1['type'] != None:
                    if g2['type'] != g1['type']:
                        exceptionset.add(i)
                        exceptionlist.append((g1, g2))
                assert len(g1['hypotheses']) == len(g2['hypotheses'])
                for j in range(len(g1['hypotheses'])):
                    h1 = g1['hypotheses'][j]
                    h2 = g2['hypotheses'][j]
                    if h1['type'] != None:
                        if not h2['type'].endswith(h1['type']):
                            exceptionset.add(i)
                            exceptionlist.append((h1, h2))

        #if proofs != []:
        #    json.dump(file_data, open(f, 'wt'))

        bar.update(i)
    return

if __name__ == '__main__':
    #merge_lmdbs()
    #merge_proofs()
    #compare_types()
    merge_proofs2()
