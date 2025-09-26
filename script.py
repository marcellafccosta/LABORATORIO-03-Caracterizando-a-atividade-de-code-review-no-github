from github import Github
from github.Auth import Token
import csv, time, math
from requests.exceptions import ReadTimeout, ConnectionError
import os

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

if not GITHUB_TOKEN:
    raise Exception('Defina GITHUB_TOKEN (ex.: export GITHUB_TOKEN=seu_token)')

auth = Token(GITHUB_TOKEN)
g = Github(auth=auth)

TOP_N = 200
MAX_PRS_SCANNED = 300      # limite por repo
DOC_EXTS = ('.md', '.rst', '.txt')
DOC_PREFIXES = ('docs/', 'doc/')

def retry_call(fn, *args, retries=4, base_sleep=1.5, **kwargs):
    """
    Executa fn(*args, **kwargs) com retries exponenciais em erros de rede/timeout.
    """
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except (ReadTimeout, ConnectionError) as e:
            if attempt >= retries:
                raise
            sleep_s = base_sleep * (2 ** attempt)
            time.sleep(sleep_s)
            attempt += 1


repos = []
for repo in g.search_repositories(query='stars:>1000', sort='stars', order='desc'):
    repos.append(repo)
    if len(repos) >= TOP_N:
        break

print(f"Total de repositórios coletados (top por estrelas): {len(repos)}")

linhas_csv = []

for repo in repos:
    print(f"Analisando: {repo.full_name}")
    try:
        closed_pulls = repo.get_pulls(state='closed')
        pr_count = closed_pulls.totalCount
        if pr_count < 100:
            print(f"Pulando {repo.full_name} (menos de 100 PRs fechados).")
            continue

        melhor_registro = None
        maior_changed_files = -1
        escaneados = 0

        for pr in closed_pulls:
            escaneados += 1
            if escaneados > MAX_PRS_SCANNED:
                break

            # status: merged ou closed (já é 'closed'; checamos merged para timestamp)
            if not (pr.merged or pr.state == 'closed'):
                continue

            closed_at = pr.merged_at if pr.merged else pr.closed_at
            if not closed_at:
                continue

            analysis_time_hours = (closed_at - pr.created_at).total_seconds() / 3600.0
            if analysis_time_hours <= 1.0:
                continue

            reviews = pr.get_reviews()
            if reviews.totalCount == 0:
                continue

            # Ignorar PRs apenas de documentação (todos os arquivos .md/.rst/.txt ou em docs/)
            so_docs = True
            try:
                files_iter = pr.get_files()
                files_list = list(files_iter)
                for f in files_list:
                    path = (f.filename or "").lower()
                    if not (path.endswith(DOC_EXTS) or path.startswith(DOC_PREFIXES)):
                        so_docs = False
                        break
            except Exception:
                # se não for possível listar arquivos, não classifica como só-doc
                so_docs = False

            if so_docs:
                continue

            num_files = getattr(pr, "changed_files", None)
            if num_files is None:
                continue

            if num_files > maior_changed_files:
                lines_added  = getattr(pr, "additions", None)
                lines_deleted = getattr(pr, "deletions", None)
                description_length = len(pr.body or "")

                # participantes e comentários (com retries)
                participants = set()
                if pr.user and pr.user.login:
                    participants.add(pr.user.login)

                issue_comments = retry_call(pr.get_comments)
                for ic in issue_comments:
                    if ic.user and ic.user.login:
                        participants.add(ic.user.login)

                review_comments = retry_call(pr.get_review_comments)
                for rc in review_comments:
                    if rc.user and rc.user.login:
                        participants.add(rc.user.login)

                for rv in reviews:
                    if rv.user and rv.user.login:
                        participants.add(rv.user.login)

                melhor_registro = {
                    'nome': repo.full_name,
                    'num_files': num_files,
                    'lines_added': lines_added,
                    'lines_deleted': lines_deleted,
                    'analysis_time_hours': round(analysis_time_hours, 2),
                    'description_length': description_length,
                    'num_participants': len(participants),
                    'num_comments_total': issue_comments.totalCount + review_comments.totalCount
                }
                maior_changed_files = num_files

        if melhor_registro:
            linhas_csv.append(melhor_registro)
        else:
            print(f"Nenhum PR válido (não-doc) encontrado em {repo.full_name}")

    except (ReadTimeout, ConnectionError) as e:
        print(f"Erro de rede em {repo.full_name}: {e}. Pulando após retries.")
        continue
    except Exception as e:
        print(f"Erro em {repo.full_name}: {e}")
        continue

# 3) Salvar CSV
if linhas_csv:
    campos = [
        'nome',
        'num_files',
        'lines_added',
        'lines_deleted',
        'analysis_time_hours',
        'description_length',
        'num_participants',
        'num_comments_total'
    ]
    with open('repos_qualificados.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas_csv)
    print(f"Arquivo repos_qualificados.csv salvo com {len(linhas_csv)} repositórios qualificados (≤ {TOP_N}).")
else:
    print("Nenhum repositório qualificado encontrado.")
