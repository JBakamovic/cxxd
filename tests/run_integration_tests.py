from builtins import str
import sys, subprocess

args = ' '.join(str(arg) for arg in sys.argv[1:])
cmd = 'PYTHONPATH=../ python tests/integration/test_all.py ' + args
ret = subprocess.call(cmd, shell=True)
