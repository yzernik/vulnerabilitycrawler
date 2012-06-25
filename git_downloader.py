import csv
import re
import os, shutil
import git
from git import *
import subprocess

from functools import wraps
import errno
import signal
import psycopg2

# Connect to an existing database
conn = psycopg2.connect(dbname="patch_db", user="patch_user")
# Open a cursor to perform database operations
cur = conn.cursor()

class TimeoutError(Exception):
    pass

def timeout(seconds=120, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator


def main():
  cur.execute("SELECT location_id, location FROM locations ORDER BY location_id DESC;")
  query_results = cur.fetchall()
  for query_result in query_results:
      location_id, location = query_result
      create_location_dir(location_id, location)
      
def create_location_dir(location_id, location):
    location_id_str = 'locaton_' + str(location_id)
    try:
        os.mkdir(location_id_str)
    except OSError:
        #print "folder already exists"
        pass
    os.chdir(location_id_str)
    r_dir = None
    try:
        r_dir = download_from_location(location_id, location)
    except TimeoutError:
        print 'timeout'
    if r_dir:
        create_diffs(location_id, r_dir)
    os.chdir('..')

@timeout(3600)
def download_from_location(location_id, location):
    repo_dir = 'source'
    try:
        shutil.rmtree(repo_dir)
    except OSError:
        pass
    try:
        print 'trying to clone: ' + str(location)
        git.Git().clone(location, repo_dir)
    except git.exc.GitCommandError:
        repo_dir = None
        print 'clone failed'
    return repo_dir
    


def create_diffs(location_id, repo_dir):
    repo = Repo(repo_dir)
    cur.execute("SELECT entries.cve, entries.commit_number FROM entries, location_mapping WHERE entries.cve=location_mapping.cve AND location_mapping.location_id = %s;", (location_id,))
    query_results = cur.fetchall()
    print 'entries for this source location: ' + str(len(query_results))
    for query_result in query_results:
        cve, commit_number = query_result
        try:
            os.mkdir(cve)
        except OSError:
            #print "folder already exists"
            pass
        os.chdir('source')
        try:
            repo.head.reset(commit=commit_number, index=True, working_tree=True)
            subprocess.call("git show -W " + str(commit_number) + " > ../" + cve + "/function.patch", shell=True)
            subprocess.call("git show " + str(commit_number) + " > ../" + cve + "/diff.patch", shell=True)
        except git.exc.GitCommandError:
            print 'invalid commit number'
        os.chdir('..')


if __name__ == "__main__":
  main()
