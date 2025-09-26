import os
import pandas as pd
from github import Github, Auth
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise Exception("Defina a variável de ambiente GITHUB_TOKEN antes de rodar o script.")

auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)

repos_df = pd.read_csv("repositorios_populares.csv")

repo_name = repos_df.iloc[0]['name']
repo = g.get_repo(repo_name)

pr_data = []

pulls = repo.get_pulls(state='closed', sort='created', direction='desc')[:50]

for pr in pulls:
    if pr.merged or pr.state == 'closed':
        reviews = pr.get_reviews()
        if reviews.totalCount >= 1:
            if pr.closed_at and pr.created_at:
                time_diff = pr.closed_at - pr.created_at
                if time_diff.total_seconds() > 3600:
                    pr_data.append({
                        "repo": repo_name,
                        "pr_number": pr.number,
                        "merged": pr.merged,
                        "num_files": pr.changed_files,
                        "lines_added": pr.additions,
                        "lines_removed": pr.deletions,
                        "time_to_close_hours": time_diff.total_seconds() / 3600,
                        "desc_length": len(pr.body) if pr.body else 0,
                        "num_participants": len(set([c.user.login for c in pr.get_comments()] + [pr.user.login])),
                        "num_comments": pr.comments,
                        "num_reviews": reviews.totalCount
                    })

pr_df = pd.DataFrame(pr_data)
pr_df.to_csv("prs_exemplo.csv", index=False)
