# ADR 0030 — Tempo de resposta: o que era gargalo, e o que não era

- **Status:** aceita
- **Data:** 2026-10-20

## Contexto

Depois das fases de segurança, lint e duplicação, o projeto tinha 1 687 testes
passando e nenhuma medição de tempo. A auditoria tinha apontado dois
candidatos a otimização — o `sp.simplify` repetido na trigonometria e o
`approx()` recalculado na formatação — e nenhum dos dois tinha sido medido.

Esta fase mediu antes de mexer. O resultado foi diferente do esperado: **os
dois candidatos do relatório não eram gargalo**, e o gargalo real era outro.

## Decisão

### 1. O integrando da superfície de revolução

A verificação da área da esfera levava **441 ms** — e o orçamento é de 1,5 s
([ADR 0010](0010-verification-engine.md)), então o teste da geometria falhava
de 2 em 5 vezes com a máquina ocupada (o sintoma medido na
[ADR 0027](0027-integracao-continua.md)).

O tempo inteiro estava em `sp.integrate`. O integrando era
`f √(1 + f'²)`, e o SymPy não consegue cancelar as raízes: para a esfera,
`√(9 − x²) · √(9/(9 − x²))` continua escrito assim, e o integrador heurístico
do SymPy gira meio segundo tentando.

A mesma coisa escrita como **`√(f² + f²f'²)`** cancela o denominador na
álgebra — `(9 − x²) + x²` — e o SymPy resolve em 1 ms. É o mesmo número
(o raio é um comprimento, positivo no intervalo) e o mesmo resultado exato.

```
441 ms  ->  30 ms   (14,8 vezes)
```

### 2. A precisão do avaliador independente

O avaliador numérico (`verification/numeric.py`) é a **segunda via** de
conferir cada resultado: ele lê a AST e avalia com mpmath, sem tocar no
SymPy ([ADR 0003](0003-verificacao.md)).

Ele começa com a precisão pedida (`digits`) e, se o valor tiver um
intermediário grande, refaz a conta com mais dígitos. O problema: um valor de
1 ou mais precisa de **um dígito a mais** do que a precisão inicial — então
**toda avaliação percorria a árvore duas vezes**, e a segunda não acrescentava
nada.

Agora a precisão começa com a margem que já existia no código
(`GUARD_DIGITS`):

```python
precision = digits + GUARD_DIGITS
```

Com isso, valores de até 10¹⁰ são avaliados numa passada só; os maiores
continuam precisando da segunda, como antes. O limite de erro reportado fica
**mais apertado** (10⁻⁵⁹ em vez de 10⁻⁵⁰), porque a conta foi feita com mais
dígitos — e a tolerância relativa (10⁻³⁰) continua mandando na comparação.

```
0,801 s  ->  0,243 s   (3,3 vezes)   num conjunto de 17 cálculos
```

### 3. O que **não** era gargalo (e por isso não mudou)

- **O `sp.simplify` repetido na trigonometria.** As expressões chegam
  simplificadas aos dois lados, mas o SymPy **cacheia** o resultado: a segunda
  chamada é quase de graça. Medido: 5,4 ms com as duas chamadas, 5,7 ms sem
  nenhuma. Não há ganho, e mexer seria mexer à toa.
- **O `approx()` recalculado na formatação.** Custa ~1 ms por raiz, e o
  `CRootOf` mais caro do projeto custa 1 ms. O retrabalho é real, mas é de
  0,1% do tempo.

Esses dois foram medidos e deixados como estão, de propósito: são cheiros de
código, não problemas de velocidade.

## Alternativas consideradas

- **Avaliar com SymPy em vez do avaliador independente.** Descartado: o
  valor da verificação é justamente ser outra via (ADR 0003).
- **Diminuir a precisão para ganhar velocidade.** Descartado: a precisão
  adaptativa é o que permite `10^3999 + 1 − 10^3999` ser exato
  (ADR 0010).
- **Trocar o orçamento de 1,5 s por um maior.** Descartado: o problema não era
  o orçamento, era a conta. E um orçamento maior tornaria o teste da geometria
  ainda mais instável.
- **Cachear as avaliações entre requisições.** Descartado: o avaliador é
  chamado com pontos diferentes a cada verificação, e o cache do SymPy já
  cobre o resto.

## Consequências

- O pior caso medido (a área da esfera) cai de 441 ms para 30 ms, e o p95 do
  conjunto de 17 cálculos fica em 63 ms.
- **A verificação continua igualmente rigorosa:** a matriz de adulteração
  (os testes que corrompem o resultado e esperam que a verificação pegue)
  passa inteira, e o limite de erro reportado ficou mais apertado, não mais
  largo.
- Dois testes novos em `tests/verification/test_numeric.py` fixam o
  comportamento: um valor simples é avaliado numa passada, e um valor enorme
  continua levando duas.
- As medições ficaram registradas aqui de propósito: quem achar o
  `simplify` duplicado ou o `approx()` recalculado não deve mexer neles sem
  medir antes.
