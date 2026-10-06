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
texto → normalize → tokenize → parse (Pratt) → AST → build (SymPy)
```

- **normalize** (`parsing/normalize.py`): `²`/`³`/`⁻¹` → `^2`/`^3`/`^(-1)`,
  `×`/`·` → `*`, `÷` → `/`, `−` → `-`, `π` → `pi`, `º` → `°`, e NFKC no resto
  (por exemplo, dígitos de largura total). Cada caractere guarda a posição de
  origem, então **os erros apontam para o que o usuário digitou**.
- **tokenize** (`parsing/tokenizer.py`): números, identificadores, operadores,
  parênteses, `√` e `°`. Qualquer caractere fora desse alfabeto gera
  `PARSE_ERROR` com a posição.
- **parse** (`parsing/parser.py`): um parser Pratt escrito à mão, sem
  dependências. Os nomes passam por uma lista fechada (`parsing/vocabulary.py`),
  e os aliases em português (`sen`, `tg`, `raiz`, `arcsen`...) viram o nome
  canônico. O resultado é uma AST própria, feita de dataclasses imutáveis.
- **build** (`parsing/build.py`): cada nó da AST vira um construtor SymPy
  chamado de forma explícita (`Rational`, `Symbol`, `+`, `*`, `**`, `sin`...).
  **Em nenhum momento um texto vira código.** O teste `tests/test_security.py`
  falha se `eval`, `exec`, `sympify`, `parse_expr` ou `lambdify` aparecerem em
  `app/`.

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
| `f(x)` | `f*x`, com o mesmo aviso: notação de função ainda não existe |
| Número depois de um termo | `x2`, `(x)2` e `2 3` são `PARSE_ERROR` (ambíguos: `x*2` ou `x^2`?) |
| `√` | prefixo que pega só o próximo átomo: `√2x` = `sqrt(2)*x` |
| `1e5`, `2e-3` | `AMBIGUOUS_INPUT`: notação científica ou `1·e·5`? |
| Variáveis | **uma letra só**; `xy` gera `UNKNOWN_SYMBOL` com a sugestão `x*y` |
| Constantes | `pi`, `e` |
| `i` | reservado; gera "números complexos ainda não suportados" |
| Funções | `sqrt abs sin cos tan asin acos atan exp ln log`, sempre com parênteses |
| Graus | `30°` → `30·pi/180` (pós-fixo; ver [ADR 0005](0005-dominio-e-exatidao.md)) |
| Equação | um único `=` (ex.: `2x + 5 = 17`) |

**Vírgula decimal:** uma vírgula entre dígitos, sem espaço e uma única vez no
número, é decimal (`3,5` → `3.5`), e o resultado traz o aviso `DECIMAL_COMMA`.
Uma sequência como `1,2,3` é ambígua e gera `AMBIGUOUS_INPUT`. Para separar
argumentos, use `; ` ou `, ` com espaço: `log(8; 2)`. Atenção: `log(100,10)`,
sem espaço, é lido como `log(100.10)`. O aviso e a forma normalizada
(`normalized_input`) deixam isso visível.

### 3. Limites (a primeira barreira)

Os limites ficam em `core/limits.py`, como constantes. Eles passam a ser
configuráveis quando houver necessidade.

| Limite | Valor |
|---|---|
| Tamanho da entrada | 500 caracteres |
| Aninhamento (parênteses, potências, sinais) | 100 níveis |
| Dígitos de um número exato (resultado ou intermediário) | 4 000 |
| Expoente inteiro sobre base com variável, como `(x+1)^n` | 1 000 |

**Por que 4 000 dígitos:** a proposta inicial era de 10 000, mas o Python 3.14
recusa converter inteiros com mais de 4 300 dígitos em texto. Essa é uma
proteção do próprio interpretador, que não vale a pena desligar. Com 4 000, todo
resultado aceito ainda pode ser exibido.

Antes de calcular `a^b` com números, o sistema estima `|b|·log10|a|` e recusa a
operação se ela passar do limite. Assim, `9^9^9^9` é recusado **sem ser
calculado**. Somas longas e sem aninhamento, como `1+1+...+1`, ficam limitadas
pelo tamanho da entrada.

### 4. Execução isolada (a segunda barreira)

Os limites acima não pegam todos os casos: `simplify` e `integrate` podem
demorar sem que nenhum número cresça. Medido na Fase 3: simplificar
`(x+1)^1000*(x+2)^1000` ou `sin(x)^1000 + cos(x)^1000` leva **vários minutos**,
e as duas entradas estão dentro de todos os limites. Por isso
(`app/core/workers.py`, implementado na Fase 3):

- o cálculo roda num **pool de processos "aquecidos"**, que importam o SymPy uma
  única vez. O processo do servidor nunca carrega o SymPy;
- os processos são criados com `spawn`, que é seguro num servidor com threads
  (`fork` não é);
- cada cálculo tem um **timeout** (`MATHCODE_CALCULATION_TIMEOUT`, padrão 5 s).
  Quando ele estoura, o worker é **morto (SIGKILL) e substituído**, e a resposta
  é o erro `TIMEOUT`. Uma thread não serviria, porque não pode ser interrompida;
- se um worker morre inesperadamente, a resposta é `INTERNAL_ERROR` (HTTP 500),
  e ele também é substituído;
- se todos os workers estão ocupados por mais de `MATHCODE_QUEUE_TIMEOUT`
  (padrão 10 s), a resposta é `SERVER_BUSY` (HTTP 503), e o pedido não fica na
  fila indefinidamente;
- o número de workers é `MATHCODE_WORKERS` (padrão 2);
- a comunicação usa `Pipe` da biblioteca padrão e transporta só texto e o
  `MathResult` serializado. Nenhum código passa entre os processos.

**Limitações conhecidas:**

- Não há limite de memória por worker: no macOS, `RLIMIT_AS` não é aplicado. O
  timeout limita o tempo, não a memória.
- O tamanho do corpo HTTP só é limitado depois da leitura: o campo `input`
  aceita no máximo 2 000 caracteres (422 acima disso). Basta para uso local, mas
  precisaria de um limite no servidor web se a API fosse exposta.

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
