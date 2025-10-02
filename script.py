from github import Github
from github.Auth import Token
from github.GithubException import GithubException, RateLimitExceededException
import csv, time, os, sys
from datetime import datetime, timezone
from requests.exceptions import ReadTimeout, ConnectionError
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN') or 'SEU_TOKEN_AQUI'
if not GITHUB_TOKEN:
    raise Exception('Defina GITHUB_TOKEN (ex.: export GITHUB_TOKEN=seu_token)')

TOP_N = int(os.getenv("TOP_N", "250"))
MAX_PRS_SCANNED = int(os.getenv("MAX_PRS_SCANNED", "50"))    
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))             

ABUSE_BACKOFF_BASE = float(os.getenv("ABUSE_BACKOFF_BASE", "10.0"))
RATE_SAFETY_WINDOW = int(os.getenv("RATE_SAFETY_WINDOW", "5"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.5"))    

auth = Token(GITHUB_TOKEN)
g = Github(auth=auth, per_page=30)  

rate_lock = threading.Lock()

def now_utc_ts():
    return int(datetime.now(timezone.utc).timestamp())

def respect_rate_limit(min_remaining=200):
    with rate_lock:
        try:
            rl = g.get_rate_limit()
            core = rl.core
            print(f"[rate] Remaining: {core.remaining}/{core.limit}")
            if core.remaining <= min_remaining:
                reset_ts = int(core.reset.timestamp())
                sleep_s = max(0, reset_ts - now_utc_ts() + RATE_SAFETY_WINDOW)
                print(f"[rate] Atingiu limite (remaining={core.remaining}). Dormindo {sleep_s}s até reset...", flush=True)
                time.sleep(sleep_s)
        except Exception:
            pass

def api_call(callable_fn, *args, retries=2, base_sleep=2.0, **kwargs):
    attempt = 0
    while True:
        try:
            respect_rate_limit()
            time.sleep(REQUEST_DELAY)
            return callable_fn(*args, **kwargs)
        except RateLimitExceededException:
            print(f"[rate] Rate limit excedido oficialmente", flush=True)
            respect_rate_limit(min_remaining=sys.maxsize)
            continue
        except GithubException as e:
            if e.status == 403:
                sleep_s = ABUSE_BACKOFF_BASE * (3 ** attempt)
                print(f"[403] Forbidden. Backoff {sleep_s:.1f}s (tentativa {attempt+1}/{retries})", flush=True)
                time.sleep(sleep_s)
                attempt += 1
                if attempt > retries:
                    print(f"[403] Desistindo de {callable_fn.__name__} após {retries} tentativas.", flush=True)
                    return None
                continue
            print(f"[GitHubException {e.status}] {e}", flush=True)
            return None
        except (ReadTimeout, ConnectionError):
            if attempt >= retries:
                return None
            time.sleep(base_sleep * (2 ** attempt))
            attempt += 1


def process_repo(repo):
    try:
        print(f"Analisando: {repo.full_name}")

        closed_pulls = api_call(repo.get_pulls, state='closed', sort='updated', direction='desc')
        if not closed_pulls:
            return None

        try:
            pr_count = closed_pulls.totalCount
        except Exception:
            pr_count = 0

        if pr_count < 100:
            print(f"Pulando {repo.full_name} (menos de 100 PRs fechados).")
            return None

        melhor_registro = None
        maior_changed_files = -1
        scanned = 0

        for pr in closed_pulls:
            scanned += 1
            if scanned > MAX_PRS_SCANNED:
                break

            if not (pr.merged or pr.state == 'closed'):
                continue

            closed_at = pr.merged_at if pr.merged else pr.closed_at
            if not closed_at:
                continue

            analysis_time_hours = (closed_at - pr.created_at).total_seconds() / 3600.0
            if analysis_time_hours <= 1.0:
                continue

            num_files = getattr(pr, "changed_files", 0)
            if num_files == 0:
                continue

            if num_files > maior_changed_files:
                lines_added   = getattr(pr, "additions", None)
                lines_deleted = getattr(pr, "deletions", None)
                description_length = len(pr.body or "")

                participants = set()
                if pr.user and pr.user.login:
                    participants.add(pr.user.login)

                issue_comments = api_call(pr.get_comments)
                issue_count = 0
                if issue_comments:
                    comment_count = 0
                    for ic in issue_comments:
                        comment_count += 1
                        if comment_count > 50:
                            break
                        if ic.user and ic.user.login:
                            participants.add(ic.user.login)
                    try:
                        issue_count = min(issue_comments.totalCount, 50)
                    except Exception:
                        issue_count = comment_count

                review_comments = api_call(pr.get_review_comments)
                review_c_count = 0
                if review_comments:
                    rc_count = 0
                    for rc in review_comments:
                        rc_count += 1
                        if rc_count > 30:
                            break
                        if rc.user and rc.user.login:
                            participants.add(rc.user.login)
                    try:
                        review_c_count = min(review_comments.totalCount, 30)
                    except Exception:
                        review_c_count = rc_count

                reviews = api_call(pr.get_reviews)
                if reviews:
                    review_count = 0
                    for rv in reviews:
                        review_count += 1
                        if review_count > 20:
                            break
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
                    'num_comments_total': issue_count + review_c_count
                }
                maior_changed_files = num_files

        return melhor_registro

    except Exception as e:
        print(f"Erro em {repo.full_name}: {e}")
        return None

def main():
    print("Coletando lista de repositórios...")
    repos = []
    for repo in g.search_repositories(query='stars:>1000', sort='stars', order='desc'):
        repos.append(repo)
        if len(repos) >= TOP_N:
            break
    print(f"Total de repositórios coletados: {len(repos)}")

    linhas_csv = []
    print(f"Iniciando processamento com {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_name = {executor.submit(process_repo, r): r.full_name for r in repos}
        completed = 0
        total = len(future_to_name)

        for fut in as_completed(future_to_name):
            completed += 1
            name = future_to_name[fut]
            try:
                res = fut.result()
                if res:
                    linhas_csv.append(res)
                    print(f"✓ {name} — {completed}/{total}")
                else:
                    print(f"- {name} — {completed}/{total}")
            except Exception as e:
                print(f"✗ {name}: {e} — {completed}/{total}")

    if linhas_csv:
        campos = [
            'nome', 'num_files', 'lines_added', 'lines_deleted',
            'analysis_time_hours', 'description_length', 'num_participants', 'num_comments_total'
        ]
        with open('dados_coletados.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(linhas_csv)
        print(f"✓ Salvos {len(linhas_csv)} repositórios qualificados.")
    else:
        print("Nenhum repositório qualificado encontrado.")

if __name__ == "__main__":
    main()