import subprocess

cmd = 'PYTHONPATH=../ python -m unittest discover -s tests/unit -v'
ret = subprocess.call(cmd, shell=True)
