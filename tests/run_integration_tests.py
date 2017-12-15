import subprocess

cmd = 'PYTHONPATH=../ python -m unittest discover -s tests/integration -v'
ret = subprocess.call(cmd, shell=True)
