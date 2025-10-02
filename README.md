# Laboratório 03 - Caracterizando a Atividade de Code Review no Github

## 1. Informações da dupla
- **Curso:** Engenharia de Software
- **Disciplina:** Laboratório de Experimentação de Software
- **Período:** 6° Período
- **Professor(a):** Prof. Wesley Dias Maciel
- **Membros:** [Ana Julia Teixeira Candido](https://github.com/anajuliateixeiracandido) e [Marcella Ferreira Chaves Costa](https://github.com/marcellafccosta)

---

## 2. Introdução
O laboratório tem como objetivo analisar a maturidade e o nível de atividade de sistemas populares hospedados em repositórios públicos.  
Espera-se compreender padrões de desenvolvimento, adoção de linguagens e engajamento da comunidade em projetos open-source.

### 2.1. Questões de Pesquisa

**A. Feedback Final das Revisões (Status do PR):**
1. Qual a relação entre o tamanho dos PRs e o feedback final das revisões?
2. Qual a relação entre o tempo de análise dos PRs e o feedback final das revisões?
3. Qual a relação entre a descrição dos PRs e o feedback final das revisões?
4. Qual a relação entre as interações nos PRs e o feedback final das revisões?

**B. Número de Revisões:**
1. Qual a relação entre o tamanho dos PRs e o número de revisões realizadas?
2. Qual a relação entre o tempo de análise dos PRs e o número de revisões realizadas?
3. Qual a relação entre a descrição dos PRs e o número de revisões realizadas?
4. Qual a relação entre as interações nos PRs e o número de revisões realizadas?

### 2.2. Hipóteses Informais

**A. Feedback Final das Revisões (Status do PR):**

1. Quanto maior o tamanho do Pull Request, pior tende a ser o feedback final das revisões.  
*Pull Requests muito grandes aumentam a complexidade da revisão, elevando o risco de rejeição, solicitações de mudanças ou até mesmo de serem fechados sem merge.*

2. Quanto maior o tempo de análise do Pull Request, pior tende a ser o feedback final das revisões.  
*PRs que levam mais tempo para serem analisados geralmente passam por mais rodadas de sugestões e correções, indicando maior dificuldade de aceitação.*

3. Quanto mais extensa for a descrição do Pull Request, melhor tende a ser o feedback final das revisões.  
*Descrições detalhadas ajudam os revisores a entenderem o contexto e as motivações das mudanças, facilitando a aprovação e reduzindo objeções.*

4. Quanto maior o número de interações no Pull Request, pior tende a ser o feedback final das revisões.  
*Um alto volume de discussões e comentários pode indicar divergências, dúvidas ou problemas, resultando em maior probabilidade de rejeição ou solicitações de mudanças.*

**B. Número de Revisões:**



---

## 3. Metodologia

### 3.1 Métricas

#### Métricas de Laboratório 
| Código | Métrica                        | Descrição                                                                                 |
|--------|--------------------------------|-------------------------------------------------------------------------------------------|
| LM01   | Tamanho: Número de Arquivos    | Quantidade total de arquivos modificados no Pull Request.                                 |
| LM02   | Tamanho: Linhas Adicionadas    | Total de linhas de código adicionadas no Pull Request.                                    |
| LM03   | Tamanho: Linhas Removidas      | Total de linhas de código removidas no Pull Request.                                      |
| LM04   | Tempo de Análise               | Intervalo de tempo (em horas ou dias) entre a criação do Pull Request e sua última atividade (fechamento ou merge). |
| LM05   | Descrição (Caracteres)         | Número de caracteres presentes no corpo de descrição do Pull Request (em markdown).        |
| LM06   | Interações: Participantes      | Número de participantes únicos envolvidos no Pull Request.                                 |
| LM07   | Interações: Comentários        | Número total de comentários feitos no Pull Request.                                        |

### 3.2 Coleta e Seleção dos Dados

O dataset foi coletado de forma automatizada utilizando a **GitHub REST API**, acessada por meio da biblioteca `PyGithub` em um script desenvolvido em **Python**. O script foi projetado para garantir eficiência, robustez e respeito às limitações de uso da API do GitHub, além de assegurar a qualidade dos dados coletados.

O processo de coleta seguiu os seguintes passos:

1. **Seleção dos repositórios:**  
Foram identificados os repositórios mais populares do GitHub (com mais de 1000 estrelas), sendo analisados até 250 repositórios, conforme parametrização do script.

2. **Filtragem de PRs:**  
Para cada repositório, foram considerados apenas Pull Requests com status **MERGED** ou **CLOSED**, que tivessem pelo menos uma revisão e um tempo de análise superior a uma hora (evitando revisões automáticas). Além disso, apenas repositórios com pelo menos 100 PRs fechados foram incluídos.

3. **Automação e concorrência:**  
O script faz uso de múltiplas threads para acelerar a coleta dos dados em vários repositórios simultaneamente, respeitando os limites de requisições da API (rate limit). Foram implementados mecanismos de controle de taxa e backoff automático para evitar bloqueios por excesso de requisições.

4. **Tratamento e validação:**  
O processo inclui tratamento de exceções para lidar com instabilidades de rede, timeouts e eventuais erros de acesso à API, garantindo a robustez da coleta. Apenas os repositórios e PRs que atenderam a todos os critérios de qualidade e filtragem foram incluídos no dataset final.

5. **Armazenamento dos dados:**  
Os dados coletados foram organizados em um arquivo CSV, estruturado para facilitar a análise estatística posterior.

Este processo garantiu a coleta padronizada, eficiente e confiável dos dados necessários para responder às questões de pesquisa propostas.

---

## 4. Resultados e Discussão

### 4.1 Tabelas

### 4.2 Gráficos

### 4.3 Discussão dos Resultados

---

## 5. Limitações e Dificuldades
---

## 6. Aprendizados e Melhorias em Relação ao Trabalho Anterior

---

## 7. Conclusão

---

## 8. Referências

---
