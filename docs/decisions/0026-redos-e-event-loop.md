# ADR 0026 — Regex sem backtracking e event loop livre

- **Status:** aceita
- **Data:** 2026-10-19

## Contexto

A auditoria do projeto encontrou um problema que nenhuma das barreiras de
[ADR 0002](0002-parser-sem-eval.md) pegava: **uma entrada de 455 caracteres
derrubava o servidor inteiro**.

O problema estava na regra de estatística de `interpreter/language.py`:

```python
_NUMBER = r"[-+\u2212]?\s*\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?"
_DATA = rf"(?P<data>{_NUMBER}(?:\s*(?:;|,\s|\se\s)\s*{_NUMBER})*)"
```

O corpo da repetição termina com `\s*` e o `_NUMBER` começa com `\s*`: os dois
disputavam **o mesmo espaço em branco**. Cada item da lista tinha duas maneiras
de lê-lo, e o regex tentava todas — 2ⁿ maneiras para n itens.

Medido em `match_language`, com a entrada `"media " + "; ".join(["1"] * n) + ","`
(a vírgula final força o regex a voltar atrás):

| Itens | Tempo |
|---|---|
| 18 | 0,039 s |
| 22 | 0,622 s |
| 26 | 10,06 s |

O tempo dobra a cada item. Com os 500 caracteres que `MAX_INPUT_LENGTH` permite,
são ~150 itens: 2¹⁵⁰ maneiras de ler a mesma frase.

**Por que isso derrubava o servidor, e não só um pedido:** as regras são lidas
em dois lugares.

- No **worker** (`calculator.py`), o cálculo tem timeout de 5 s (ADR 0002): o
  worker morre e é substituído. O dano é limitado.
- Na **API** (`api/calculate.py`), a chamada a `needs_ai()` lia as regras
  **direto no event loop**, sem timeout nenhum. Uma requisição segurava o event
  loop por tempo indeterminado: o health check parava de responder e qualquer
  outra requisição ficava esperando.

Confirmado na API rodando, com a configuração padrão (`MATHCODE_AI_PROVIDER=none`):
a requisição `POST /api/calculate` com `allow_ai=true` e o payload acima
levou o servidor a 100% de indisponibilidade, e ele não voltou sozinho.

`needs_ai()` é avaliado antes de o provedor de IA ser consultado, então
desligar a IA não evitava o problema: bastava `allow_ai=true`.

## Decisão

Duas camadas, porque uma só deixa a classe do problema aberta: `language.py`
tem 30 regras, e qualquer regex novo pode repetir o mesmo padrão.

### 1. O regex não tem ambiguidade

O número não pega mais o espaço antes dele; o separador pega, uma vez só. E o
vão entre dois itens é **atômico** (`(?>...)`), para o regex se comprometer com
uma única divisão dos espaços:

```python
_NUMBER = r"[-+\u2212]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?"
_DATA = rf"(?P<data>\s*{_NUMBER}(?:(?>\s*(?:;|,\s|\se\s)\s*){_NUMBER})*)"
```

Com isso, cada item tem **uma** leitura possível e o backtracking é linear.

### 2. Nada de CPU no event loop

O event loop atende todas as requisições. Regex e parsing são trabalho de CPU,
sem limite de tempo conhecido: eles **não rodam** nele.

- `needs_ai()` e `plan_request()` vão para `asyncio.to_thread()`, como o cálculo
  já fazia (`core/workers.py`).
- O cálculo em si continua no pool de processos, que tem timeout.

A regra que fica para o projeto: **uma requisição nunca faz trabalho de CPU
ilimitado no event loop**. Se algo não cabe no pool de processos, vai para uma
thread; se nem isso basta, vira um worker com timeout.

### 3. As duas barreiras viram teste

- `tests/test_security.py`: uma lista de 150 itens com lixo no fim é lida em
  menos de 2 s (a versão quebrada levava mais que a idade do universo).
- `tests/api/test_calculate.py`: as regras são lidas **fora** do event loop — o
  teste falha se alguma delas voltar a ser lida nele.

## Alternativas consideradas

- **Só corrigir o regex.** Resolve este caso, mas deixa o event loop exposto a
  qualquer regex futuro. As duas camadas custam quase nada e fecham a classe
  do problema.
- **Limitar o número de itens da lista no regex** (`{0,200}`). Não impede o
  backtracking: 200 itens ainda dão 2²⁰ maneiras. O limite de itens já existe
  em outro lugar (`MAX_DATA_VALUES`), mas ele não impede o custo.
- **Pôr um timeout no event loop.** Não existe em Python; e o event loop não
  pode ser interrompido no meio de um `re.match`.
- **Recusar listas longas na entrada.** Mudaria o que o projeto aceita, sem
  necessidade: o defeito era o regex, não a lista.

## Consequências

- A API responde normalmente ao payload que antes derrubava o servidor
  (medido: 0,028 s, e o health check responde em seguida).
- As listas continuam sendo lidas exatamente como antes: "10, 20 e 30",
  "2,5; 3,5", "1/2; 3/4" e "-1; +2" não mudaram de significado, e há teste
  para cada forma.
- **Custo de uma thread por requisição** que chega ao `needs_ai()` ou ao
  planejador. É o mesmo mecanismo que o pool de processos já usava, e a thread
  é curta.
- O planejador (`interpreter/planner.py`) também passa a ser lido fora do event
  loop, pelos mesmos motivos: os padrões dele também leem texto do usuário.
- Regra para as próximas fases: regex novo em `interpreter/` precisa de um
  teste de tempo, como o de `test_security.py`.
