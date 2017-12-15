import subprocess

cmd = 'PYTHONPATH=../ python tests/integration/test_all.py --do_not_drop_symbol_db'
ret = subprocess.call(cmd, shell=True)
