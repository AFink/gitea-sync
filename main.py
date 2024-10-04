#!/usr/bin/env python -B

import logging
import os
import sys
import json
import requests
from github import Github
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

gitea_url = os.getenv("GITEA_URL")
gitea_token = os.getenv("GITEA_TOKEN")
github_username = os.getenv("GITHUB_USERNAME")
github_token = os.getenv("GITHUB_TOKEN")

if not gitea_url or not gitea_token or not github_username or not github_token:
    logging.error("Missing required environment variables")
    sys.exit(1)

def mirror_repos():
    logging.info("Starting repository mirroring...")

    # Gitea session setup
    session = requests.Session()
    session.headers.update({
        "Content-type": "application/json",
        "Authorization": f"token {gitea_token}",
    })

    try:
        # Get user details from Gitea
        r = session.get(f"{gitea_url}/user")
        r.raise_for_status()
        gitea_uid = r.json()["id"]
    except requests.RequestException as e:
        logging.error(f"Error fetching Gitea user details: {e}")
        sys.exit(1)

    # Github API setup
    gh = Github(github_token)

    for repo in gh.get_user().get_repos():
        # Mirror non-forked repositories
        if not repo.fork:
            m = {
                "repo_name": repo.full_name.replace("/", "-"),
                "description": repo.description,
                "clone_addr": repo.clone_url,
                "mirror": True,
                "mirror_interval": "24h",
                "private": True,
                "uid": gitea_uid,
            }
            
            if repo.private:
                m["auth_username"] = github_username
                m["auth_password"] = github_token

            jsonstring = json.dumps(m)

            try:
                r = session.post(f"{gitea_url}/repos/migrate", data=jsonstring)
                if r.status_code == 201:
                    logging.info(f"Successfully mirrored {repo.full_name}")
                elif r.status_code == 409:
                    logging.info(f"Repository {repo.full_name} already exists in Gitea.")
                else:
                    logging.error(f"Failed to mirror {repo.full_name}: {r.status_code} - {r.text}")
            except requests.RequestException as e:
                logging.error(f"Error migrating repo {repo.full_name}: {e}")


    logging.info("Repository mirroring completed.")

# Schedule task every Sunday at 00:00
scheduler = BlockingScheduler()
scheduler.add_job(mirror_repos, 'cron', day_of_week='sun', hour=0)

# Start the scheduler
try:
    logging.info("Syncing once now...")
    mirror_repos()
    
    logging.info("Starting scheduler...")
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    logging.info("Scheduler stopped.")
