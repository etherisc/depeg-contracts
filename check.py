import subprocess

ERRORCODES = ['.github/workflows/scripts/validate_errorcodes.sh']
EVENTNAMES = ['.github/workflows/scripts/validate_events.sh']
TESTS = ['brownie', 'test','-n','8']
LINTING = ['solhint', 'contracts/**/*.sol', '|', 'grep', 'error']

def run_command(command, description, max_lines=5):
    print(description)
    output = subprocess.run(command, capture_output=True, text=True)

    lines = output.stdout.split('\n')

    if len(lines) < max_lines:
        print('\n'.join(lines))
    else:
        print('\n'.join(['...'] + lines[-max_lines:]))

    return output

run_command(TESTS, '#### run unit tests...')
run_command(ERRORCODES, '#### run error code check...')
run_command(EVENTNAMES, '#### run event name check...')
run_command(LINTING, '#### run linting check...')
