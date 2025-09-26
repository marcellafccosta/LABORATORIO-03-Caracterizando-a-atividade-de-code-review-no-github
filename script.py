import os
import pandas as pd
from github import Github, Auth

# Lê o token da variável de ambiente
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise Exception("Defina a variável de ambiente GITHUB_TOKEN antes de rodar o script.")

auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)

query = "stars:>1000"
repos = g.search_repositories(query=query, sort="stars", order="desc")

repo_list = []

for i, repo in enumerate(repos):
    if len(repo_list) >= 200:
        break
    closed_prs = repo.get_pulls(state='closed').totalCount
    if closed_prs >= 100:
        repo_list.append({
            "name": repo.full_name,
            "url": repo.html_url,
            "language": repo.language,
            "stars": repo.stargazers_count,
            "closed_prs": closed_prs
        })

df = pd.DataFrame(repo_list)
df.to_csv("repositorios_populares.csv", index=False)
