import argparse
import hashlib
import json
import re
import subprocess

SOLC = '/home/vscode/.solcx/solc-v0.8.2'
REMAPPINGS = '@openzeppelin=/home/vscode/.brownie/packages/OpenZeppelin/openzeppelin-contracts@4.7.3 @etherisc/gif-contracts=/home/vscode/.brownie/packages/etherisc/gif-contracts@b58fd27 @etherisc/gif-interface=/home/vscode/.brownie/packages/etherisc/gif-interface@3b0002a'
OPTIONS = '--storage-layout'


def process_storage(storage_layout):
    storage_in = storage_layout['storage']
    storage_out = []

    for element in storage_in:
        storage_out.append({
            'label': element['label'],
            'offset': element['offset'],
            'slot': element['slot'],
            'type': process_type_names(element['type']),
            # 'type': element['type'],
        })

    return storage_out


def process_type_names(type_names_string):

    def replacer(match):
        type_name = match.group(1)

        # get type id hash
        sha = hashlib.sha256()
        sha.update(type_name.encode())
        type_id = sha.hexdigest()[:5]

        return f'({type_name}){type_id}'

    return re.sub(r'\((\w+)\)\d+', replacer, type_names_string)


def process_types(storage_layout):
    types_in = storage_layout['types']
    types_out = {}

    for key, element in types_in.items():
        key_processed = process_type_names(key)
        types_out[key_processed] = process_type_element(element)

    return types_out


def process_type_element(element):
    if element['encoding'] == 'dynamic_array':
        element['base'] = process_type_names(element['base'])

    elif element['encoding'] == 'mapping':
        element['key'] = process_type_names(element['key'])
        element['value'] = process_type_names(element['value'])
    
    elif 'members' in element:
        members_out = []
        for member in element['members']:
            members_out.append({
                'label': member['label'],
                'offset': member['offset'],
                'slot': member['slot'],
                'type': process_type_names(member['type']),
            })
        
        element['members'] = members_out

    return element


def main(file_name, unify):

    # run solc
    command = f"{SOLC} {REMAPPINGS} {OPTIONS} {file_name}"
    process = subprocess.run(command, shell=True, capture_output=True, text=True)

    # parse the JSON from the last line of the output
    last_line = process.stdout.strip().split('\n')[-1]
    storage_layout = json.loads(last_line)

    # process the json
    if unify:
        storage_layout = {
            'storage': process_storage(storage_layout),
            'types': process_types(storage_layout),
        }

    storage_layout['params'] = {
        'file_name': file_name,
        'unify': unify,
        'solc': SOLC,
        'remappings': REMAPPINGS,
    }

    # pretty print the JSON to the console
    print(json.dumps(storage_layout, indent=4))


if __name__ == "__main__":

    # prepare comand line arg parsing
    parser = argparse.ArgumentParser(description="get solidity storage layout in json format")
    parser.add_argument('solidity_file', type=str, help="the solidity file to check")
    parser.add_argument('--unify', action='store_true', help="process json to unify diffs")

    # get/process command line args
    args = parser.parse_args()

    main(args.solidity_file, args.unify)