import sys, subprocess

args = ' '.join(str(arg) for arg in sys.argv[1:])
cmd = 'python3 tests/run_integration_tests.py --do_not_drop_symbol_db ' + args
ret = subprocess.call(cmd, shell=True)
