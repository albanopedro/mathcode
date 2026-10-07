# ADR 0011 — Estatística descritiva (Fase 10, 1º domínio)

- **Status:** aceita
- **Data:** 2026-10-07

## Contexto

A Fase 10 adiciona matemática avançada **um domínio por alteração**. O prompt
mestre pede, entre os objetivos, "qual a média de 10, 20, 30?". Antes desta
etapa, frases de estatística caíam na regra "ainda não suportado" e uma lista
de números dava erro de vírgula.

## Decisões do usuário

1. **Primeiro domínio: estatística descritiva.** Matrizes, geometria,
   probabilidade, vetores e trigonometria ficam para as próximas etapas.
2. **Medidas:** média, mediana, moda, variância, desvio padrão, mínimo,
   máximo, amplitude, soma e quantidade. Quartis ficam como sugestão, porque há
   várias convenções (calculadoras, planilhas e livros dão valores diferentes).
3. **Desvio padrão principal: o populacional (σ, ÷ n)**, o do ensino médio
   para "um conjunto de dados". O amostral (s, ÷ n − 1) aparece junto,
   rotulado, com um aviso explicando a diferença.
4. **Resultado:** a operação "Estatística" mostra o resumo completo; uma frase
   ("média de 10, 20, 30") destaca a medida pedida, com o resumo embaixo.

## Decisão

### Entrada

- Intent `statistics`, com `StatisticsParams(data, measure?)`. A opção
  `measure` aceita `count`, `sum`, `mean`, `median`, `mode`, `min`, `max`,
  `range`, `variance`, `std`, `sample_variance` e `sample_std`; sem ela, o
  pedido é o resumo.
- Os dados são números separados por `; ` ou `, ` (com espaço, porque `1,5` é
  decimal), lidos pelo parser seguro com `parse(texto, number_list=True)`.
  Fora desse modo, uma lista só de números continua sendo erro (provável
  vírgula decimal com espaço), e a mensagem agora aponta a operação
  Estatística.
- Cada valor precisa ser **racional**: inteiro, decimal ou fração, inclusive
  negativo. `sqrt(2)`, `pi` e variáveis são recusados com a posição do valor.
- No máximo 200 valores (`MAX_DATA_VALUES`); o limite de 500 caracteres de
  entrada vem antes.

### Frases (`interpreter/language.py`)

- `média`, `mediana`, `moda`, `variância (amostral|populacional)`, `desvio
  padrão (amostral|populacional)`, `amplitude`, `soma`, `máximo`/`maior
  valor`, `mínimo`/`menor valor`, e `estatísticas`/`resumo estatístico` (o
  resumo).
- Até quatro palavras entre a medida e os números ("média das notas 7, 8 e
  9,5"); um "e" antes do último número vira separador.
- A regra só vale se o que vem depois for uma lista de números. Assim,
  "máximo de x^2 − 4x" continua sendo uma funcionalidade futura (máximo de
  função), e "média das idades da turma", sem números, recebe uma orientação
  de formato.
- O prompt da IA ganhou o intent `statistics` e deixou de listar estatística
  como "não suportada". Nenhuma chamada real foi feita nesta etapa; os testes
  usam o mock.

### Cálculo (`math_engine/statistics.py`)

- Tudo com `Fraction` (exato). Só os desvios padrão, raízes das variâncias,
  podem ser irracionais: ficam exatos no SymPy (`√6`) e têm aproximação.
- **Mediana** com quantidade par: média dos dois valores centrais.
- **Moda:** todos os valores com a maior frequência; se nenhum valor se
  repete, não há moda (amodal). Em `1, 1, 2, 2`, as modas são 1 e 2.
- **Amostrais** com um só valor: não definidas. No resumo aparecem como "—",
  com aviso; pedidas diretamente, dão erro explicado.

### Verificação (`verification/statistics.py`)

Nada vem do cálculo do motor:

1. os valores são **relidos** da árvore com frações exatas
   (`verification/exact.py`, sem SymPy) e comparados com os usados;
2. todas as medidas são **recalculadas pelo módulo `statistics`** do Python,
   que é exato com frações (comparação de métodos);
3. propriedades exatas: a soma dos desvios em relação à média é 0; a mediana
   divide os dados (pelo menos metade ≤ Md e pelo menos metade ≥ Md); σ² e s²
   são as variâncias, e σ e s são não negativos.

Status: `verified_symbolic`. A matriz de adulteração ganhou o caso de
estatística (média, mediana, moda, variâncias, soma, extremos e um valor mal
lido são pegos).

### Apresentação

- Resultado principal: a medida pedida (`σ = 2`, `\sigma = 2`) ou, no resumo,
  a média (`média = 20`).
- `details`: `measure`, `count`, `data` e `sorted` (decimais finitos aparecem
  como decimais: 9.5, não 19/2), `modes` e `measures` (as 12 medidas, cada uma
  com rótulo, símbolo, `plain`, `latex` e `approx`; `null` quando não
  definida).
- O frontend mostra uma tabela (Medida, Valor, Aproximado) com a medida pedida
  destacada (`aria-current`) e os dados em ordem.

## Consequências

- Há um intent novo; a API aceita `{"intent": "statistics", "options":
  {"measure": "std"}}`.
- Sugestões registradas: quartis e IQR (com uma convenção escolhida e
  explicada), média ponderada, tabela de frequências, dados com irracionais e
  rótulo do campo de entrada por operação ("Dados" em vez de "Expressão ou
  equação").
