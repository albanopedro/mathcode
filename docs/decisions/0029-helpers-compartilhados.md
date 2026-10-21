# ADR 0029 — Helpers compartilhados em módulos folha

- **Status:** aceita
- **Data:** 2026-10-20

## Contexto

Uma auditoria do backend encontrou a mesma lógica escrita em vários módulos:

| Lógica | Onde estava |
|---|---|
| `fold` (minúsculas sem acento) | `interpreter/language.py` e `math_engine/probability.py` |
| `simplified` (simplifica, salvo se já for racional) | `math_engine/geometry.py`, `matrices.py` e `vectors.py` |
| `Fraction` → `sp.Rational` | `math_engine/statistics.py` e `verification/vectors.py` |
| `sp.Rational` → `Fraction` | `verification/probability.py` |
| graus ↔ radianos | `parsing/build.py`, `math_engine/trigonometry.py`, `formatting/results.py` e `verification/trigonometry.py` |

Duas delas eram piores do que repetição:

- `interpreter/planner.py` importava **`_fold`**, um nome privado, de
  `interpreter/language.py`. Um nome privado importado de outro módulo é um
  convite para quebrar a encapsulation.
- `math_engine/statistics.py` e `verification/numeric.py` tinham duas funções
  chamadas **`rational`**, com assinaturas diferentes: uma levava `Fraction`, a
  outra levava `str`. Quem importasse a errada quebraria.

E a duplicação **já tinha cobrado**: ao extrair a lista de figuras da regra de
geometria, digitei `paralepipedo` (faltou um "l") e quebrei a geometria
inteira. Com a lista vindo de um único dicionário, isso não acontece mais
([ADR 0028](0028-lint-do-frontend.md) registra a fase do lint, onde isso
apareceu).

## Decisão

Os helpers compartilhados moram em **módulos folha**: módulos que não
importam nada do projeto. Assim, qualquer camada pode usá-los sem criar
ciclo nem inverter a hierarquia.

| Módulo | O que tem | Quem usa |
|---|---|---|
| `core/text.py` | `fold` | `interpreter/language.py`, `interpreter/planner.py`, `math_engine/probability.py` |
| `parsing/angles.py` | `degrees_of`, `radians_of` | `parsing/build.py`, `math_engine/trigonometry.py`, `formatting/results.py`, `verification/trigonometry.py` |
| `math_engine/values.py` | `simplified`, `to_rational`, `to_fraction` | `math_engine/geometry.py`, `matrices.py`, `vectors.py`, `statistics.py`, `verification/vectors.py`, `verification/probability.py`, `verification/numeric.py` |

### Três decisões que vieram junto

**1. `core/text.py` é só texto.** `core/` não importa SymPy, e continua sem
importar: o processo do servidor nunca carrega o SymPy
([ADR 0002](0002-parser-sem-eval.md)), e `core/` é a base que ele importa.
Por isso `fold`, que é só texto, foi para `core/`, e os que usam SymPy foram
para baixo ou para dentro da camada do motor.

**2. `parsing/angles.py` é folha, e não `core/`.** A conversão de graus é
SymPy, e `core/` não pode carregar SymPy. `parsing/` é a camada mais baixa
que pode: o `parsing/build.py` já importa SymPy (é o passo "AST → SymPy") e é
importado só pelo worker. Um módulo folha não cria ciclo, então a conversão
pode ser usada pelo motor, pela formatação e pela verificação sem problema.

**3. Os nomes são `degrees_of` e `radians_of`, e não `to_degrees` e
`to_radians`.** O domínio já usa `to_degrees` para o sinalizador que diz se a
resposta é em graus (`TrigonometryOutcome.to_degrees`). Com o mesmo nome, a
variável local sombreava a função importada — e o erro só apareceu porque os
testes rodaram. `degrees_of` ("os graus deste ângulo") não colide.

### O que **não** foi unificado

- **Os renderizadores de número.** `approx()` (15 dígitos), `_six()` (6
  dígitos), `_short_float()` e `_round()` (`.10g`) e `show()` (mpmath) têm
  precisões e propósitos diferentes. São APIs, não cópias.
- **Os separadores de lista.** O parser e a probabilidade seemed ter regras
  diferentes, mas não têm: os dois aceitam `;` e `, ` (com espaço), e a vírgula
  sem espaço é decimal nos dois casos. A diferença que existia era na
  linguagem, não no motor.
- **`sp.simplify` repetido na trigonometria** e o **`approx()` recalculado** na
  formatação: são desperdício de tempo, não duplicação de código. Ficam para
  uma fase própria, que mexe no tempo de resposta e por isso precisa de
  medição.

## Consequências

- Nenhum nome privado é importado de outro módulo.
- Não há mais duas funções `rational` com nomes iguais e assinaturas
  diferentes: a que lê texto virou `exact_rational`, e a de fração virou
  `to_rational`.
- Um teste novo protege o invariante de que o processo do servidor não carrega
  SymPy: `tests/test_security.py::test_the_server_process_never_loads_sympy`.
- A conversão de graus tem um lugar só. Um bug de grau ou radiano agora
  aparece em um teste, e não em um dos quatro lugares.
- Três módulos novos, todos pequenos e sem dependência do projeto.
