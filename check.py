import difflib
import os
import requests
import subprocess
import sys

from scripts.cksum import cksum

ERRORCODES = ['.github/workflows/scripts/validate_errorcodes.sh']
EVENTNAMES = ['.github/workflows/scripts/validate_events.sh']
TESTS = ['brownie', 'test','-n','8']
LINTING = ['solhint', 'contracts/**/*.sol', '|', 'grep', 'error']

GITHUB_USER = 'etherisc'
GITHUB_REPO = 'registry-contracts'
GITHUB_BRANCH = 'experiment/upgradable-struct' # 'develop'
REPO_BASE = '{}/{}/{}'.format(GITHUB_USER, GITHUB_REPO, GITHUB_BRANCH)
GITHUB_BASE = 'https://raw.githubusercontent.com/{}'.format(REPO_BASE)

FACADE_NFT = 'contracts/registry/IChainNftFacade.sol'
FACADE_REGISTRY = 'contracts/registry/IChainRegistryFacade.sol'
FACADE_STAKING = 'contracts/staking/IStakingFacade.sol'


def diff_with_github(filepath):
    github_url = '{}/{}'.format(GITHUB_BASE, filepath)
    local_filepath = './{}'.format(filepath)

    response = requests.get(github_url)
    github_content = response.text

    with open(local_filepath, "r") as f:
        local_content = f.read()
    
    diff = difflib.unified_diff(
        local_content.splitlines(), 
        github_content.splitlines(),
        fromfile=local_filepath, 
        tofile=github_url)

    diff_txt = [line for line in diff]
    lines = diff_txt[2:]
    lines_cksum = cksum('\n'.join(lines))

    return (lines, lines_cksum)


def run_file_diff(filepath):
    local_filepath = './{}'.format(filepath)

    print('checking local file {} against {}'.format(local_filepath.split('/')[-1], GITHUB_BASE))

    if not os.path.isfile(local_filepath):
        print('ERROR file not found {}'.format(local_filepath))
        return
    
    else:
        (lines, lines_cksum) = diff_with_github(filepath)
        cksum_expected = 858801941
        result = 'OK' if lines_cksum == cksum_expected else 'ERROR expected cksum {}'.format(cksum_expected)

        if lines_cksum != cksum_expected:
            print('\n'.join(lines))
            print('')

        print('cksum {} {}'.format(lines_cksum, result))


def run_command(command, description, max_lines=5):
    print(description)
    output = subprocess.run(command, capture_output=True, text=True)

    lines = output.stdout.split('\n')

    if len(lines) < max_lines:
        print('\n'.join(lines))
    else:
        print('\n'.join(['...'] + lines[-max_lines:]))

    return output

if '--no_unit_tests' not in sys.argv:
    run_command(TESTS, '#### run unit tests...')
else:
    print('#### NOT running unit tests')

run_command(LINTING, '#### run linting check...')
run_command(ERRORCODES, '#### run error code check...')
run_command(EVENTNAMES, '#### run event name check...')

print('#### run facade contract checks...')
run_file_diff(FACADE_NFT)
run_file_diff(FACADE_REGISTRY)
run_file_diff(FACADE_STAKING)