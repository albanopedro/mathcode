# ADR 0032 — Média ponderada e tabela de frequências

- **Status:** aceita
- **Data:** 2026-10-21

## Contexto

A ADR 0011 deixou a média ponderada e a tabela de frequências no backlog. As
duas são a mesma ideia vista de dois ângulos: cada valor pode aparecer várias
vezes. A média ponderada dá um número; a tabela de frequências mostra quantas
vezes cada valor aparece, a fração do total e o acumulado.

O projeto precisava de uma convenção simples, exata e verificável por um
caminho independente. Pesos fracionários, dados agrupados sem expansão e uma
operação separada para a tabela foram considerados e descartados (abaixo).

## Decisão

### Pesos são frequências

- `StatisticsParams` ganhou `weights`, uma lista de **inteiros positivos**, um
  para cada valor. Cada peso diz quantas vezes o valor entra no cálculo.
- O motor **expande** os dados: `7, 8, 9` com pesos `2, 3, 5` vira
  `7, 7, 8, 8, 8, 9, 9, 9, 9, 9`. Todas as medidas existentes são calculadas
  sobre essa lista, sem fórmula nova.
- A soma dos pesos é o `count` (n) e não pode passar de **200**, o mesmo
  limite de valores da estatística (`MAX_DATA_VALUES`). Sem esse limite, um
  peso grande criaria uma lista enorme e a expansão deixaria de ser segura.
- Pesos precisam ser **positivos**: zero eliminaria o valor e negativo não é
  frequência. Decimais como `2,5` são recusados; frações que valem um inteiro
  (`6/2`) são aceitas porque o valor final é inteiro.
- A quantidade de pesos tem de ser igual à quantidade de valores.
- Sem pesos, o comportamento é exatamente o de antes.

### A média e a soma ponderadas

- Pedir `mean` com pesos devolve a média da lista expandida, isto é,
  `Σ(w·x) / Σw`.
- No resumo, a linha da média vira **"Média ponderada"** (`\bar{x}_w`) e a da
  soma vira **"Soma ponderada"** (`\sum wx`); as demais mantêm os rótulos.
- As medidas amostrais usam `n = Σw`, não a quantidade de valores digitados.
- O aviso `WEIGHTED_DATA` explica que os pesos são frequências e que
  `n = Σw`.

### Tabela de frequências

- Todo resultado de estatística traz `details.frequency`, uma linha por valor
  distinto, em ordem crescente:
  - `value`: o valor como foi digitado (decimal finito ou fração);
  - `frequency`: quantas vezes ele aparece (`w`, ou 1 sem pesos);
  - `relative`: `frequency / n`, fração exata (por exemplo `"1/3"`);
  - `cumulative`: a soma das frequências até ali.
- A tabela é construída a partir da lista expandida, então valores repetidos
  digitados separadamente são combinados, e os pesos viram as frequências.
- O resumo continua com **15 medidas numéricas**. A tabela é uma seção à
  parte, não uma 16ª medida.
- `Measure` ganhou `"frequency"` para pedir a tabela explicitamente. Nesse
  caso a manchete é "tabela de frequências (n = …)", sem um número único, e o
  frontend destaca a tabela em vez de uma linha do resumo.

### Frases

- `média ponderada de 7, 8, 9 com pesos 2, 3, 5` → `measure: "mean"` e
  `weights: "2, 3, 5"`.
- Também aceita `média com pesos …` e a forma `média ponderada: 7, 8 e 9;
  pesos: 2, 3 e 5` (o `e` final é separador, como no resto da estatística).
- `média ponderada de 7, 8, 9` sem pesos dá erro explicado: a frase precisa
  dos valores e dos pesos.
- `tabela de frequências de 1, 2, 2, 3`, `frequências de …` e
  `qual a tabela de frequências de …?` pedem `measure: "frequency"`.
- Sem números, a orientação de formato já inclui o exemplo da tabela.
- A API aceita `weights` em `INTENT_OPTIONS`; o prompt da IA lista a opção e
  a medida `frequency`.

### Verificação (`verification/statistics.py`)

1. Os valores **e os pesos** são relidos da árvore do parser com frações
   exatas (`exact_value`, sem SymPy) e comparados com os do motor.
2. A lista expandida é **reconstruída** a partir dos valores e dos pesos
   relidos; se ela não for a usada no cálculo, a verificação falha.
3. As medidas são recalculadas pelo módulo `statistics` do Python sobre a
   lista expandida, como antes.
4. A tabela de frequências é conferida contra `Counter(expanded)`: valores,
   frequências, relativas exatas (`frequency / n`) e acumuladas; a soma das
   relativas precisa ser exatamente 1.
5. A matriz de adulteração ganhou pesos alterados, expansão alterada, tabela
   alterada e média alterada por `1/10⁹`.
6. Pesos que não são frações simples (por exemplo `sqrt(4)`) deixam a
   releitura inconclusiva, como já acontece com valores assim; as medidas
   continuam conferidas a partir do que o motor leu.

Status: `verified_symbolic`, como o resto da estatística.

### Frontend

- `StatisticsDetails` ganhou `weighted` e `frequency`; o validador confere
  cada linha (tipos e inteiros).
- `StatisticsView` mostra sempre a tabela de frequências (Valor, Frequência,
  Relativa, Acumulada) abaixo do resumo.
- Com dados ponderados, a linha de dados vira "Dados agrupados (n = …):
  7 (×2); 8 (×3); …".
- Quando `measure` é `"frequency"`, a seção da tabela fica destacada
  (`aria-current`), e nenhuma linha do resumo é destacada.
- A interpretação mostra "pesos: 2, 3, 5" e, com pesos, "medida: média
  ponderada"; `frequency` aparece como "tabela de frequências".
- Os quatro fixtures antigos foram recapturados e dois novos foram criados
  (média ponderada e tabela de frequências), todos da API real.

## Alternativas descartadas

- **Pesos fracionários ou decimais** (`Σwx / Σw` sem expandir): é a fórmula
  geral, mas impede a expansão, separa "pesos" de "frequências" e exigiria
  uma segunda estratégia de verificação. Fica para o futuro se aparecer um
  caso escolar real.
- **Cálculo agrupado sem expansão**, para permitir pesos grandes: medianas e
  quartis teriam de ser achados por frequência acumulada, e a verificação
  deixaria de reaproveitar o módulo `statistics`. O limite de 200 observações
  totais mantém a expansão simples, exata e independente.
- **Uma operação separada para a tabela**: duplicaria o parsing, a
  verificação e a tela. A tabela é uma apresentação do mesmo conjunto de
  dados, então virou uma medida pedida (`frequency`) dentro de `statistics`.
- **Entrada agrupada `1 (2), 2 (3)`**: mais uma sintaxe para aprender e
  testar; a frase "média ponderada … com pesos …" já cobre o mesmo caso, e a
  tabela é derivada dos dados. Fica registrado no backlog.
- **Mostrar a tabela só quando houver repetição**: o usuário escolheu vê-la
  no resumo sempre; com o limite de 200 valores, o tamanho fica controlado.

## Consequências

- A API aceita, por exemplo,
  `{"intent": "statistics", "input": "7, 8, 9", "options": {"measure": "mean",
  "weights": "2, 3, 5"}}` e
  `{"intent": "statistics", "input": "1, 2, 2, 3", "options": {"measure":
  "frequency"}}`.
- O resumo não ganhou uma linha nova: as 15 medidas continuam iguais; a
  tabela é uma seção adicional.
- `details` ganhou `weighted` e `frequency`; o frontend e os fixtures foram
  atualizados.
- O prompt da IA e `docs/architecture.md` refletem `weights`, `frequency` e a
  convenção.
- O limite das opções de texto da API subiu de 100 para **500 caracteres** (o
  mesmo da entrada), para que uma lista de pesos caiba; o teste de "opção
  longa" passou a usar 501.
- Testes: **1 740** no backend (eram 1 713) e **363** no frontend (eram 355).
- Continuam no backlog: dados irracionais, entrada agrupada
  `valor (frequência)`, pesos fracionários e o rótulo "Dados" no campo de
  entrada.
