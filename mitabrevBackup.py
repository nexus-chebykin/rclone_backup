import argparse
import pathlib
import subprocess
import sys

interpreter = sys.executable
workingDirectory = pathlib.Path('/root/MitabrevFolder/backupScriptWorkingDirectory')
if not workingDirectory.is_dir():
    workingDirectory.mkdir()
    print("Created working directory")
    subprocess.run("git clone https://github.com/nexus-chebykin/rclone_backup .", cwd=workingDirectory,
                   shell=True)
    print("Cloned the repository")
else:
    subprocess.run("git pull", cwd=workingDirectory, shell=True)
    print("Pulled the changes")

subprocess.run([interpreter, '-m', 'pip', 'install', '--requirement', 'requirements.txt', '--upgrade'], cwd=workingDirectory)
print("Installed & updated libraries")
print("Now running main")
with open(workingDirectory / 'log.txt', 'w') as log_file:
    subprocess.run([interpreter, "-u", "main.py"], cwd=workingDirectory, text=True, stdout=log_file, stderr=subprocess.STDOUT)