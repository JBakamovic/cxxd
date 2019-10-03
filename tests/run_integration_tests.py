import sys, subprocess

args = ' '.join(str(arg) for arg in sys.argv[1:])
cmd = 'PYTHONPATH=../ python3 tests/integration/test_all.py ' + args
ret = subprocess.call(cmd, shell=True)
