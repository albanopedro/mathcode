# ADR 0002 — Parser próprio, sem `eval`, e execução com limites

- **Status:** aceita
- **Data:** 2026-10-06

## Contexto

O usuário digita expressões livres. As formas mais diretas de transformar texto
em objetos SymPy são `sympify()` e `sympy.parsing.sympy_parser.parse_expr()`.
**As duas usam `eval()` internamente**, e a documentação do SymPy avisa que não
devem receber entrada não confiável. Isso viola a regra de segurança do projeto.

Mesmo com um parser seguro, uma expressão válida pode travar o servidor: por
exemplo `9^9^9^9`, um fatorial enorme ou uma integral patológica.

## Decisão

### 1. Pipeline de entrada

```
texto → normalize → tokenize → parse (Pratt) → AST → validate → build (SymPy)
```

- **normalize:** NFKC, `²`/`³` → `^2`/`^3`, `×`/`·` → `*`, `÷` → `/`, `−` → `-`,
  `π` → `pi`, `√` → `sqrt`, aliases em português (`sen` → `sin`,
  `tg` → `tan`, `raiz` → `sqrt`).
- **tokenize:** números, identificadores, operadores e parênteses. Qualquer
  caractere fora do alfabeto permitido gera um erro com a **posição**.
- **parse:** um parser Pratt escrito à mão, sem dependências. Ele produz uma AST
  própria (dataclasses imutáveis).
- **validate:** limites de profundidade e de tamanho, e uma lista fechada de
  funções e constantes.
- **build:** cada nó da AST vira um construtor SymPy chamado de forma explícita
  (`Add`, `Mul`, `Pow`, `sin`...). **Em nenhum momento um texto vira código.**

### 2. Gramática inicial (Fase 2)

| Elemento | Regra |
|---|---|
| Números | `12`, `3.5`; `3,5` é decimal (ver abaixo) |
| Operadores | `+ - * / ^` (`**` é normalizado para `^`) |
| Precedência | `^` > unário `-` > `* /` e multiplicação implícita > `+ -` |
| Associatividade | `^` à direita (`2^3^2 = 2^9`); os demais à esquerda |
| `-x^2` | `-(x^2)` |
| Multiplicação implícita | `2x`, `2(x+1)`, `(x+1)(x-1)`, `2pi` |
| `1/2x` | `(1/2)*x`, com o aviso `AMBIGUOUS_IMPLICIT_MULTIPLICATION` |
| Variáveis | **uma letra só**; `xy` gera `UNKNOWN_SYMBOL` com a sugestão `x*y` |
| Constantes | `pi`, `e` |
| `i` | reservado; gera "números complexos ainda não suportados" |
| Funções | `sqrt abs sin cos tan asin acos atan exp ln log` |
| Graus | `30°` → `30·pi/180` (pós-fixo; ver [ADR 0005](0005-dominio-e-exatidao.md)) |
| Equação | um único `=` (ex.: `2x + 5 = 17`) |

**Vírgula decimal:** uma vírgula entre dígitos, sem espaço e uma única vez no
número, é decimal (`3,5` → `3.5`). Uma sequência como `1,2,3` é ambígua e gera
`AMBIGUOUS_INPUT`. A vírgula seguida de espaço continua livre para separar
argumentos e listas nas fases futuras.

### 3. Limites (a primeira barreira)

Os limites ficam em `core/limits.py` e podem ser configurados.

| Limite | Valor inicial |
|---|---|
| Tamanho da entrada | 500 caracteres |
| Profundidade da AST | 100 |
| Dígitos estimados de uma potência inteira | 10 000 |
| Argumento de fatorial (quando existir) | 1 000 |

Antes de calcular `a^b`, o sistema estima `b·log10(a)` e recusa a operação se o
resultado passar do limite.

### 4. Execução isolada (a segunda barreira)

Os limites acima não pegam todos os casos: `simplify` e `integrate` podem
demorar sem que nenhum número cresça. Por isso:

- o cálculo roda num **pool de processos "aquecidos"**, que importam o SymPy uma
  única vez;
- cada tarefa tem um **timeout** (5 s no início);
- quando o timeout estoura, o worker é **encerrado e substituído**. Uma thread
  não serve, porque não pode ser interrompida.

O código é próprio, com `multiprocessing` da biblioteca padrão, e entra na
Fase 3, junto com a API. Na Fase 2, os testes exercitam os limites da seção 3.

## Alternativas consideradas

- **`parse_expr` com transformações restritas:** continua usando `eval`.
  Rejeitada.
- **Lark (gramática declarativa):** é segura, mas acrescenta uma dependência
  para uma gramática pequena. Pode ser reavaliada se a gramática crescer muito.
- **`parse_latex` do SymPy:** depende de antlr4 ou Lark, e cobre apenas a entrada
  em LaTeX. Para a Fase 11 (MathLive), a ideia é converter o MathJSON ou o texto
  do MathLive para a mesma AST.

## Consequências

- O projeto tem mais código próprio para manter, e esse código precisa de testes
  extensos (casos válidos, inválidos e maliciosos).
- As mensagens de erro podem apontar a posição exata do problema.
- A IA (Fase 8) também entrega expressões como texto, e esse texto passa **pelo
  mesmo parser**.
