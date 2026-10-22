# Contexto — Média ponderada e tabela de frequências

- **Fase:** pós-Fase 12, item do backlog "média ponderada e tabela de frequências"
- **ADR:** [0032](decisions/0032-media-ponderada-e-frequencias.md)
- **Data:** 2026-10-21
- **Status:** implementação concluída, testada, documentada e commitada em
  `1d9b49e` (enviada para `origin/main`); CI verde
- **Base do Git:** `e1dbb14` (`main`, já com a ADR 0031 / quartis e IQR)
- **Commit da fase:** `1d9b49e`, feito pelo usuário; working tree limpo

Este arquivo é um handoff da fase: decisões, mudanças por arquivo, exemplos,
verificação, testes e o que ficou pendente. O resumo permanente do projeto
continua em [`CLAUDE.md`](../CLAUDE.md) e em
[`docs/architecture.md`](architecture.md).

---

## 1. Objetivo da fase

Implementar, na estatística descritiva:

1. **média ponderada**, com pesos informados pelo usuário;
2. **tabela de frequências** (valor, frequência, relativa exata e acumulada);
3. frases em português, API, verificação independente, frontend e documentação,
   seguindo o fluxo de uma fase por vez.

O item veio da ADR 0011 e estava registrado no backlog do
[`roadmap.md`](roadmap.md).

---

## 2. Decisões principais

### 2.1 Pesos são frequências inteiras

- `weights` é uma lista de **inteiros positivos**, um para cada valor.
- Cada peso diz quantas vezes o valor entra no cálculo.
- A soma dos pesos (`Σw`) não pode passar de **200**, o mesmo
  `MAX_DATA_VALUES` da estatística.
- Pesos com quantidade diferente da quantidade de valores são recusados.
- Zero e negativos são recusados; decimais como `2,5` são recusados.
- Frações que valem um inteiro (por exemplo `6/2`) são aceitas, porque o valor
  final é inteiro.
- **Hipótese assumida:** o usuário não respondeu à pergunta sobre pesos
  fracionários; a opção recomendada (inteiros positivos) foi seguida e está
  registrada na ADR 0032. Pesos fracionários ficaram no backlog.

### 2.2 Média ponderada = média dos dados expandidos

- O motor **expande** cada valor `w` vezes:
  `7, 8, 9` com pesos `2, 3, 5` vira
  `7, 7, 8, 8, 8, 9, 9, 9, 9, 9`.
- Todas as medidas existentes são calculadas sobre a lista expandida, sem
  fórmula paralela:
  - `count = Σw` (n);
  - `total = Σ(w·x)`;
  - `mean = Σ(w·x) / Σw`;
  - mediana, quartis, moda, variâncias, desvios, mínimo, máximo e amplitude
    usam a lista expandida.
- A linha da média vira **"Média ponderada"** (`\bar{x}_w`) e a da soma vira
  **"Soma ponderada"** (`\sum wx`) quando há pesos.
- O aviso `WEIGHTED_DATA` explica que os pesos são frequências e que
  `n = Σw`.

### 2.3 Tabela de frequências

- Todo resultado de estatística traz `details.frequency`: uma linha por valor
  distinto, em ordem crescente:
  - `value`: valor como foi digitado (decimal finito ou fração);
  - `frequency`: quantas vezes aparece (o peso, ou 1 sem pesos);
  - `relative`: `frequency / n` como fração exata (`"1/3"`, `"1/2"`, ...);
  - `cumulative`: soma das frequências até a linha.
- A tabela é construída a partir da lista expandida, então valores repetidos
  digitados separadamente são combinados.
- O resumo continua com **15 medidas numéricas**; a tabela é uma seção à parte,
  não uma 16ª medida.
- `Measure` ganhou `"frequency"` para pedir a tabela explicitamente. Nesse
  caso:
  - a manchete é `tabela de frequências (n = …)`;
  - não há um número único;
  - o frontend destaca a seção da tabela, e nenhuma linha do resumo.

### 2.4 Frases aceitas

- `média ponderada de 7, 8, 9 com pesos 2, 3, 5`
- `média ponderada das notas 7, 8, 9 com os pesos 2, 3, 5`
- `média ponderada de 7, 8 e 9 com pesos 2, 3 e 5`
- `média ponderada: 7, 8 e 9; pesos: 2, 3 e 5`
- `média com pesos 2, 3, 5` (com os valores antes, no formato usual)
- `tabela de frequências de 1, 2, 2, 3`
- `frequências de 1, 2, 2, 3`
- `qual a tabela de frequências de 1, 2, 2, 3?`

Sem os pesos, a frase de média ponderada dá erro explicado: ela precisa dos
valores e dos pesos.

### 2.5 Sem entrada agrupada nesta fase

Não foi criada a sintaxe `1 (2), 2 (3)`. A frase
`média ponderada … com pesos …` cobre o mesmo caso e a tabela é derivada dos
dados. Entrada agrupada ficou registrada no backlog, junto com pesos
fracionários e dados irracionais.

### 2.6 Limite das opções da API

- Para uma lista de pesos caber na opção de texto da API, o limite geral das
  opções subiu de **100 para 500 caracteres** (o mesmo limite da entrada).
- O teste de "opção longa" passou a usar 501 caracteres.
- A frase e a opção explícita continuam sujeitas ao limite de 500 da entrada.

---

## 3. Backend — mudanças por arquivo

### 3.1 `backend/app/math_engine/statistics.py`

- Novo dataclass `FrequencyRow`:
  - `value: Fraction`
  - `frequency: int`
  - `relative: Fraction`
  - `cumulative: int`
- `StatisticsOutcome` ganhou:
  - `weight_items: tuple[Node, ...]`;
  - `weights: tuple[int, ...] | None`;
  - `expanded: tuple[Fraction, ...]`;
  - `frequency: tuple[FrequencyRow, ...]`.
- `count` passou a ser `len(expanded)` (ou seja, `Σw`).
- `weighted` é uma propriedade (`weights is not None`).
- `statistics(params)`:
  - lê `params.weights` com `parse(..., number_list=True)`;
  - valida quantidade, inteiros positivos e `Σw ≤ MAX_DATA_VALUES`;
  - expande os valores;
  - calcula todas as medidas sobre `expanded`;
  - monta a tabela de frequências com `Counter`;
  - adiciona o aviso `WEIGHTED_DATA`.
- `_frequency(expanded)`:
  - uma linha por valor distinto, ordenado;
  - relativa exata `Fraction(count, total)`;
  - acumulada.
- Mensagens em português:
  - `"A quantidade de pesos deve ser igual à quantidade de valores."`
  - `"Os pesos precisam ser inteiros positivos (frequências)."`
  - `"A soma dos pesos não pode passar de 200."`
  - aviso: `"Os pesos são frequências: cada valor entra no cálculo w vezes; n = soma dos pesos."`

### 3.2 `backend/app/models/intents.py`

- `Measure` inclui `"frequency"` (a tabela, sem valor numérico único).
- `StatisticsParams` ganhou `weights: str | None = None`.
- `INTENT_OPTIONS[IntentName.STATISTICS]` inclui `"weights"`.
- `OptionValue`:
  - texto até 500 caracteres (era 100), para caber uma lista de pesos;
  - número continua de −1000 a 1000.
- Import de `MAX_INPUT_LENGTH` para não duplicar o número 500.

### 3.3 `backend/app/formatting/results.py`

- Com pesos:
  - `mean` → rótulo `"Média ponderada"`, símbolo `\bar{x}_w`;
  - `sum` → rótulo `"Soma ponderada"`, símbolo `\sum wx`.
- `measure == "frequency"`:
  - `plain = "tabela de frequências (n = …)"`;
  - `latex = r"\text{Tabela de frequências}"`;
  - sem `approx`.
- `details` ganhou:
  - `weighted: bool`;
  - `frequency: list[{value, frequency, relative, cumulative}]`.
- `details.sorted` usa a lista expandida; `details.data` continua com os
  valores digitados.
- O resumo continua com 15 medidas.

### 3.4 `backend/app/interpreter/language.py`

- `_MEASURE` ganhou:
  - `"tabela de frequências"` / `"frequências"` → `measure: "frequency"`.
- Novo padrão `_WEIGHTS`, no mesmo formato de lista dos dados.
- Regra `weighted_mean`:
  - aceita `média ponderada` e `média com pesos`;
  - usa `_FILLER` antes dos dados, então aceita `de`, `das notas`,
    `dos números`, `:` etc.;
  - aceita `com pesos`, `com os pesos` e `pesos`;
  - devolve `{"measure": "mean", "weights": "2, 3, 5"}`.
- Regra `weighted_mean_without_weights`:
  - se a frase começa com média ponderada mas não casa a regra completa,
    explica que precisa dos valores e dos pesos.
- A medida `frequency` foi incluída na orientação de formato quando não há
  números.
- Exemplos normalizados:
  - `"média ponderada de 7, 8 e 9 com pesos 2, 3 e 5"` →
    dados `"7, 8; 9"` e pesos `"2, 3; 5"`;
  - `"média ponderada das notas 7, 8, 9 com os pesos 2, 3, 5"` →
    dados `"7, 8, 9"` e pesos `"2, 3, 5"`.

### 3.5 `backend/app/interpreter/detect.py`

- A mensagem de medida desconhecida agora lista `frequency`.

### 3.6 `backend/app/core/notices.py`

- Novo código `WEIGHTED_DATA`.

### 3.7 `backend/app/ai/prompt.py`

- O prompt da IA passou a listar:
  - a opção `weights` (lista de inteiros positivos, uma por valor, até 200 no
    total);
  - a medida `frequency`.
- A IA continua só interpretando; não calcula.

### 3.8 `backend/app/verification/statistics.py`

- Relê **valores e pesos** da árvore do parser com `exact_value`, sem SymPy.
- Reconstrói a expansão a partir dos valores e pesos relidos.
- Recalcula todas as medidas pelo módulo `statistics` do Python sobre a lista
  expandida.
- Confere a tabela de frequências:
  - valores e frequências contra `Counter(expanded)`;
  - relativas exatas `frequency / n`;
  - acumuladas;
  - soma das frequências = n;
  - soma das relativas = 1;
  - última acumulada = n.
- Novos checks/tamper tests:
  - pesos alterados;
  - expansão alterada;
  - tabela alterada;
  - média alterada por `1/10⁹`.
- Pesos que não são frações simples deixam a releitura inconclusiva, como já
  acontecia com valores assim; as medidas continuam conferidas a partir do que
  o motor leu.
- Status: `verified_symbolic`.

---

## 4. Frontend — mudanças por arquivo

### 4.1 `frontend/src/utils/statistics.ts`

- Novo tipo `FrequencyRow`.
- `StatisticsDetails` ganhou:
  - `weighted: boolean`;
  - `frequency: FrequencyRow[]`.
- Validador `isFrequencyRow` confere tipos e inteiros.
- `statisticsDetails` valida os novos campos; qualquer linha malformada
  invalida os detalhes.

### 4.2 `frontend/src/components/StatisticsView.tsx`

- Nova seção **Tabela de frequências**:
  - colunas Valor, Frequência, Relativa, Acumulada;
  - valor como `<th scope="row">` (cabeçalho de linha);
  - `<caption>` acessível;
  - contêiner com rolagem horizontal.
- Com dados ponderados, a linha de dados vira:
  - `Dados agrupados (n = 10): 7 (×2); 8 (×3); 9 (×5)`.
- Quando `measure === "frequency"`:
  - a seção recebe `aria-current="true"`;
  - nenhuma linha do resumo é destacada.
- Caso contrário, o destaque continua na linha da medida pedida.

### 4.3 `frontend/src/utils/interpretation.ts`

- Novos rótulos:
  - `frequency` → `"tabela de frequências"`;
  - `weights` → `"pesos: 2, 3, 5"`;
  - média com pesos → `"média ponderada"`.

### 4.4 Testes e fixtures

- `StatisticsView`/`Calculator.test.tsx`:
  - tabela de frequências no resumo;
  - dados agrupados e tabela no resultado ponderado;
  - `frequency` destacada quando pedida.
- `utils/statistics.test.ts`:
  - detalhes ponderados;
  - tabela de frequência;
  - linha malformada rejeitada.
- `utils/interpretation.test.ts`:
  - `"medida: média ponderada"` + `"pesos: 2, 3, 5"`;
  - `"medida: tabela de frequências"`.
- Fixtures recapturados da API real:
  - `statistics-summary.json`;
  - `statistics-phrase.json`;
  - `statistics-single.json`;
  - `statistics-no-mode.json`.
- Fixtures novos:
  - `statistics-weighted.json`;
  - `statistics-frequency.json`.
- `fixtures/index.ts` atualizado.

---

## 5. Exemplos de referência

### 5.1 Média ponderada

Entrada:

```text
média ponderada de 7, 8, 9 com pesos 2, 3, 5
```

Dados expandidos:

```text
7, 7, 8, 8, 8, 9, 9, 9, 9, 9
```

Resultados:

| Medida | Valor |
|---|---|
| n | 10 |
| Soma ponderada | 83 |
| Média ponderada | `83/10` = 8,3 |
| Mediana | `17/2` |
| Moda | 9 |
| Q1 | 8 |
| Q3 | 9 |
| IQR | 1 |

Tabela:

| Valor | Frequência | Relativa | Acumulada |
|---|---|---|---|
| 7 | 2 | 1/5 | 2 |
| 8 | 3 | 3/10 | 5 |
| 9 | 5 | 1/2 | 10 |

Manchete: `média ponderada = 83/10` (`\bar{x}_w = \frac{83}{10}`).
Verificação: `verified_symbolic`.
Avisos: `WEIGHTED_DATA` e `POPULATION_AND_SAMPLE`.

### 5.2 Tabela de frequências

Entrada:

```text
tabela de frequências de 1, 2, 2, 3
```

Resultado:

- manchete `tabela de frequências (n = 4)`;
- `measure: "frequency"`.

| Valor | Frequência | Relativa | Acumulada |
|---|---|---|---|
| 1 | 1 | 1/4 | 1 |
| 2 | 2 | 1/2 | 3 |
| 3 | 1 | 1/4 | 4 |

### 5.3 API

Resumo ponderado:

```json
{
  "input": "7, 8, 9",
  "intent": "statistics",
  "options": { "measure": "mean", "weights": "2, 3, 5" }
}
```

Tabela:

```json
{
  "input": "1, 2, 2, 3",
  "intent": "statistics",
  "options": { "measure": "frequency" }
}
```

Resposta (trecho):

```json
{
  "result": {
    "plain": "média ponderada = 83/10",
    "latex": "\\bar{x}_w = \\frac{83}{10}",
    "approx": "8.3"
  },
  "details": {
    "measure": "mean",
    "count": 10,
    "weighted": true,
    "frequency": [
      { "value": "7", "frequency": 2, "relative": "1/5", "cumulative": 2 },
      { "value": "8", "frequency": 3, "relative": "3/10", "cumulative": 5 },
      { "value": "9", "frequency": 5, "relative": "1/2", "cumulative": 10 }
    ]
  },
  "verification": { "status": "verified_symbolic" }
}
```

---

## 6. Verificação e qualidade

### 6.1 Backend

```text
ruff check .                      → All checks passed!
ruff format --check .             → 127 files already formatted
pytest -q                         → 1740 passed
```

Antes da fase: **1713** testes. Depois: **1740** (+27).

Principais testes novos:

- média ponderada, expansão, medidas e tabela;
- tabela de dados brutos;
- resumo ponderado e manchete;
- medida `frequency`;
- pesos inválidos (quantidade, zero, negativo, decimal, variável, irracional);
- soma dos pesos > 200;
- verificação de dados ponderados;
- adulteração de pesos, expansão, tabela e média;
- frases ponderadas e de frequência;
- opção `weights` e `measure: "frequency"` na API;
- limite de opção longa (501) e teste da IA com 501.

### 6.2 Frontend

```text
npm run typecheck                 → ok
npm run lint                      → ok
npm run test -- --run             → 25 arquivos, 363 testes
npm run build                     → ok (Vite)
```

Antes da fase: **355** testes. Depois: **363** (+8).

### 6.3 Git

```text
git diff --check                  → limpo
```

O assistente não fez commits; o usuário commitou a fase como `1d9b49e`,
já enviada para `origin/main`. A CI do push terminou com **sucesso**
(run `39868833778`).

---

## 7. Documentação atualizada

- **Nova:** `docs/decisions/0032-media-ponderada-e-frequencias.md`.
- `docs/architecture.md`:
  - visão do intent `statistics`;
  - linhas de `details` e opções;
  - limite de opções (500);
  - descrição do `StatisticsView`;
  - índice de ADRs.
- `docs/roadmap.md`:
  - fase marcada como concluída (aguardando revisão);
  - seção "Depois da Fase 12 — Média ponderada e tabela de frequências";
  - backlog atualizado.
- `CLAUDE.md`:
  - cabeçalho, tabela de status, arquitetura da estatística, decisões,
    próximos passos e histórico;
  - contagem 1 740 / 363.
- `README.md`:
  - recursos e exemplos de média ponderada e tabela de frequências;
  - ADRs 0031 e 0032 na lista de endurecimento.
- `docs/decisions/0011-estatistica-descritiva.md`:
  - `details` com `weighted` e `frequency`;
  - sugestões atualizadas.
- `docs/decisions/0031-quartis-e-iqr.md`:
  - nota dizendo que média ponderada e tabela foram feitas na ADR 0032.

---

## 8. Arquivos alterados nesta fase

### Backend

```text
backend/app/ai/prompt.py
backend/app/core/notices.py
backend/app/formatting/results.py
backend/app/interpreter/detect.py
backend/app/interpreter/language.py
backend/app/math_engine/statistics.py
backend/app/models/intents.py
backend/app/verification/statistics.py
backend/tests/ai/test_opencode_provider.py
backend/tests/api/test_calculate.py
backend/tests/math_engine/test_statistics.py
backend/tests/test_language.py
```

### Frontend

```text
frontend/src/components/Calculator.test.tsx
frontend/src/components/StatisticsView.tsx
frontend/src/test/fixtures/index.ts
frontend/src/test/fixtures/statistics-no-mode.json
frontend/src/test/fixtures/statistics-phrase.json
frontend/src/test/fixtures/statistics-single.json
frontend/src/test/fixtures/statistics-summary.json
frontend/src/test/fixtures/statistics-weighted.json   (novo)
frontend/src/test/fixtures/statistics-frequency.json  (novo)
frontend/src/utils/interpretation.test.ts
frontend/src/utils/interpretation.ts
frontend/src/utils/statistics.test.ts
frontend/src/utils/statistics.ts
```

### Documentação / raiz

```text
CLAUDE.md
README.md
docs/architecture.md
docs/decisions/0011-estatistica-descritiva.md
docs/decisions/0031-quartis-e-iqr.md
docs/decisions/0032-media-ponderada-e-frequencias.md  (novo)
docs/roadmap.md
docs/contexto-media-ponderada-e-frequencias.md         (este arquivo)
```

Total aproximado: **29 arquivos rastreados modificados + 3 novos**, com cerca
de 926 inserções e 107 remoções (sem contar este contexto).

---

## 9. Como usar / reproduzir

### 9.1 Pela frase (modo automático)

No frontend, deixe a operação em **Automático** e digite:

```text
média ponderada de 7, 8, 9 com pesos 2, 3, 5
```

ou:

```text
tabela de frequências de 1, 2, 2, 3
```

> **Atenção:** a operação **Estatística** do seletor envia `intent:
> "statistics"` e espera os dados brutos. Para usar a frase, utilize o modo
> **Automático** (sem selecionar operação) ou a API sem `intent`. Com
> `intent: "statistics"`, envie os valores e a opção `weights`.

### 9.2 Pela API com opções explícitas

```bash
curl -X POST http://localhost:8000/api/calculate \
  -H "Content-Type: application/json" \
  -d '{"input": "7, 8, 9", "intent": "statistics", "options": {"measure": "mean", "weights": "2, 3, 5"}}'
```

```bash
curl -X POST http://localhost:8000/api/calculate \
  -H "Content-Type: application/json" \
  -d '{"input": "1, 2, 2, 3", "intent": "statistics", "options": {"measure": "frequency"}}'
```

### 9.3 Testes

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run test -- --run
npm run build
```

---

## 10. Pendências e próximos passos

### 10.1 Desta fase

- [x] Revisão do usuário.
- [x] Commit das mudanças (`1d9b49e`, enviado para `origin/main`).
- [x] CI no Linux: sucesso (run `39868833778`).

### 10.2 Backlog de estatística

- dados irracionais;
- entrada agrupada `valor (frequência)` (ex.: `1 (2), 2 (3)`);
- pesos fracionários ou decimais;
- rótulo "Dados" no campo de entrada quando a operação é Estatística.

### 10.3 Pendência antiga do repositório

- O diretório `mathcode/` continua como gitlink rastreado; o
  `git rm --cached mathcode` ainda é uma ação pendente do usuário (não foi
  tocado nesta fase).

---

## 11. Observações e limitações

- **Pesos não são fracionários nesta fase.** A média ponderada usa a expansão,
  o que mantém a verificação simples e reaproveita o módulo `statistics`.
- **A tabela é sempre exibida no resumo**, mesmo sem repetição; o limite de 200
  valores controla o tamanho.
- **A relativa é uma fração exata**, não percentual. Ex.: `1/3`, `1/2`, `1/4`.
- **A tabela não é uma 16ª medida**: `details.measures` continua com 15
  entradas; `frequency` é uma seção e uma medida de apresentação.
- **O resumo não ganhou Q2**: a mediana continua sendo o segundo quartil
  (ADR 0031).
- **O limite de 500 caracteres da opção** é o mesmo da entrada; listas de pesos
  muito longas com espaços podem precisar de separadores compactos
  (`1,1,1,...`).
- **A frase ponderada precisa dos valores e dos pesos**; sem eles, o erro
  explica o formato.
- **Quartis seguem a ADR 0031**: Q1/Q3 são as medianas das metades, sem
  interpolação; com quantidade ímpar, o valor central fica fora das duas.
