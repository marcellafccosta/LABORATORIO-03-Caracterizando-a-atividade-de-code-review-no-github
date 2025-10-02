from github import Github
from github.Auth import Token
from github.GithubException import GithubException, RateLimitExceededException
import csv, time, os, sys
from datetime import datetime, timezone
from requests.exceptions import ReadTimeout, ConnectionError
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Token de autenticação para acessar a API do GitHub
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

if not GITHUB_TOKEN:
    raise Exception('Defina GITHUB_TOKEN (ex.: export GITHUB_TOKEN=seu_token)')

# Configurações do script obtidas através de variáveis de ambiente
TOP_N = int(os.getenv("TOP_N", "250"))                    # Número de repositórios a analisar
MAX_PRS_SCANNED = int(os.getenv("MAX_PRS_SCANNED", "50")) # Máximo de PRs por repositório
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))          # Número de threads para processamento paralelo

# Configurações para controle de rate limit da API
ABUSE_BACKOFF_BASE = float(os.getenv("ABUSE_BACKOFF_BASE", "10.0"))
RATE_SAFETY_WINDOW = int(os.getenv("RATE_SAFETY_WINDOW", "5"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.5"))

# Inicialização da conexão com a API do GitHub
auth = Token(GITHUB_TOKEN)
g = Github(auth=auth, per_page=30)

# Lock para sincronização de threads no controle de rate limit
rate_lock = threading.Lock()

def now_utc_ts():
    # Retorna timestamp UTC atual para controle de rate limit
    return int(datetime.now(timezone.utc).timestamp())

def respect_rate_limit(min_remaining=200):
    # Controla rate limit da API, pausando quando necessário para evitar bloqueios
    with rate_lock:
        try:
            rl = g.get_rate_limit()
            core = rl.core
            
            if core.remaining <= min_remaining:
                reset_ts = int(core.reset.timestamp())
                sleep_s = max(0, reset_ts - now_utc_ts() + RATE_SAFETY_WINDOW)
                time.sleep(sleep_s)
        except Exception:
            # Em caso de erro na consulta do rate limit, continua execução
            pass

def api_call(callable_fn, *args, retries=2, base_sleep=2.0, **kwargs):
    # Wrapper para chamadas da API com retry automático e tratamento de erros
    attempt = 0
    while True:
        try:
            respect_rate_limit()
            time.sleep(REQUEST_DELAY)
            return callable_fn(*args, **kwargs)
        except RateLimitExceededException:
            # Tratamento específico para rate limit excedido
            respect_rate_limit(min_remaining=sys.maxsize)
            continue
        except GithubException as e:
            if e.status == 403:
                # Implementa backoff exponencial para erros 403 (Forbidden)
                sleep_s = ABUSE_BACKOFF_BASE * (3 ** attempt)
                time.sleep(sleep_s)
                attempt += 1
                if attempt > retries:
                    return None
                continue
            return None
        except (ReadTimeout, ConnectionError):
            # Tratamento para erros de conexão
            if attempt >= retries:
                return None
            time.sleep(base_sleep * (2 ** attempt))
            attempt += 1

def process_repo(repo):
    # Analisa repositório individual e extrai métricas do PR com mais arquivos modificados
    try:
        # Busca pull requests fechados ordenados por data de atualização
        closed_pulls = api_call(repo.get_pulls, state='closed', sort='updated', direction='desc')
        if not closed_pulls:
            return None

        # Verifica se o repositório tem volume suficiente de PRs para análise
        try:
            pr_count = closed_pulls.totalCount
        except Exception:
            pr_count = 0

        if pr_count < 100:
            return None

        # Variáveis para rastreamento do melhor PR (mais arquivos modificados)
        melhor_registro = None
        maior_changed_files = -1
        scanned = 0

        # Análise dos pull requests
        for pr in closed_pulls:
            scanned += 1
            if scanned > MAX_PRS_SCANNED:
                break

            # Filtra apenas PRs efetivamente fechados/merged
            if not (pr.merged or pr.state == 'closed'):
                continue

            # Calcula tempo de análise (criação até fechamento)
            closed_at = pr.merged_at if pr.merged else pr.closed_at
            if not closed_at:
                continue

            analysis_time_hours = (closed_at - pr.created_at).total_seconds() / 3600.0
            # Filtra PRs com tempo de análise muito baixo (possivelmente automatizados)
            if analysis_time_hours <= 1.0:
                continue

            # Foca em PRs com modificações significativas
            num_files = getattr(pr, "changed_files", 0)
            if num_files == 0:
                continue

            # Atualiza registro se encontrou PR com mais arquivos modificados
            if num_files > maior_changed_files:
                # Coleta métricas básicas do PR
                lines_added   = getattr(pr, "additions", None)
                lines_deleted = getattr(pr, "deletions", None)
                description_length = len(pr.body or "")

                # Identifica participantes únicos do PR
                participants = set()
                if pr.user and pr.user.login:
                    participants.add(pr.user.login)

                # Análise de comentários gerais do PR
                issue_comments = api_call(pr.get_comments)
                issue_count = 0
                if issue_comments:
                    comment_count = 0
                    for ic in issue_comments:
                        comment_count += 1
                        if comment_count > 50:  # Limitação para performance
                            break
                        if ic.user and ic.user.login:
                            participants.add(ic.user.login)
                    try:
                        issue_count = min(issue_comments.totalCount, 50)
                    except Exception:
                        issue_count = comment_count

                # Análise de comentários de review (específicos do código)
                review_comments = api_call(pr.get_review_comments)
                review_c_count = 0
                if review_comments:
                    rc_count = 0
                    for rc in review_comments:
                        rc_count += 1
                        if rc_count > 30:  # Limitação para performance
                            break
                        if rc.user and rc.user.login:
                            participants.add(rc.user.login)
                    try:
                        review_c_count = min(review_comments.totalCount, 30)
                    except Exception:
                        review_c_count = rc_count

                # Análise de reviews formais
                reviews = api_call(pr.get_reviews)
                if reviews:
                    review_count = 0
                    for rv in reviews:
                        review_count += 1
                        if review_count > 20:  # Limitação para performance
                            break
                        if rv.user and rv.user.login:
                            participants.add(rv.user.login)

                # Compila métricas finais do repositório
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
        # Em caso de erro no processamento, retorna None
        return None

def main():
    # Função principal: busca repositórios populares, processa em paralelo e salva em CSV
    # Fase 1: Coleta de repositórios populares
    repos = []
    for repo in g.search_repositories(query='stars:>1000', sort='stars', order='desc'):
        repos.append(repo)
        if len(repos) >= TOP_N:
            break

    # Fase 2: Processamento paralelo dos repositórios
    linhas_csv = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submete todas as tarefas para o pool de threads
        future_to_name = {executor.submit(process_repo, r): r.full_name for r in repos}
        completed = 0
        total = len(future_to_name)

        # Coleta resultados conforme completam
        for fut in as_completed(future_to_name):
            completed += 1
            name = future_to_name[fut]
            try:
                res = fut.result()
                if res:
                    linhas_csv.append(res)
            except Exception as e:
                # Ignora erros individuais para não interromper o processamento
                pass

    # Fase 3: Persistência dos dados coletados
    if linhas_csv:
        # Define estrutura do arquivo CSV
        campos = [
            'nome', 'num_files', 'lines_added', 'lines_deleted',
            'analysis_time_hours', 'description_length', 'num_participants', 'num_comments_total'
        ]
        
        # Salva dados em formato CSV para análise posterior
        with open('dados_coletados.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(linhas_csv)

# Ponto de entrada do script
if __name__ == "__main__":
    main()
