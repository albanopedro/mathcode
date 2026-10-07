# ADR 0010 — Verification Engine formal (Fase 9)

- **Status:** aceita
- **Data:** 2026-10-07
- **Complementa:** [ADR 0003](0003-verificacao.md) (estratégia e níveis de
  verificação)

## Contexto

A Fase 9 pede para expandir e formalizar a verificação simbólica, a
substituição, a verificação numérica, a comparação de métodos e o tratamento de
resultados não verificáveis. A auditoria encontrou quatro lacunas:

1. **Relatórios em texto livre:** `method` era um texto ("symbolic+numeric") e
   `checks` uma lista de frases. Nada dizia, de forma estruturada, o que foi
   checado e com qual resultado.
2. **Pouca comparação de métodos:** derivadas ficavam no máximo em
   `verified_numeric`, aritmética exata também, limites no máximo em `partial`
   e integrais definidas só tinham a quadratura.
3. **Verificação lenta virava erro:** em `x^20 - 3x^7 + 1 = 0`, a conta levava
   19 ms e a verificação mais de 20 s (o `simplify` de raízes `CRootOf` calcula
   polinômios mínimos de grau ~400). O resultado se perdia num `TIMEOUT`.
4. **Exceção num verificador virava `INTERNAL_ERROR`:** o resultado calculado
   também se perdia.

## Decisões do usuário

1. **Checagens estruturadas**, com tipo, resultado e texto; o relatório ganha
   as estratégias usadas e o motivo quando não verifica.
2. **Quatro comparações de métodos:** derivador próprio, frações exatas,
   continuidade nos limites e Newton–Leibniz.
3. **Não verificável vira "não verificado" com motivo**, e não erro.

## Decisão

### 1. Relatório estruturado (`models/result.py`)

```text
VerificationReport
├── status: verified_symbolic | verified_numeric | partial | unverified
│           | not_applicable | failed
├── methods: list[CheckKind]       calculado: os tipos das checagens, em ordem
├── checks: list[VerificationCheck] (pelo menos uma)
│   ├── kind: symbolic | substitution | numeric | comparison | completeness
│   │         | domain | execution
│   ├── outcome: passed | failed | inconclusive
│   └── message: str
├── message: str                    a manchete, por status (e por motivo)
└── reason: ReasonCode | null       só em partial e unverified
```

| `kind` | O que é |
|---|---|
| `symbolic` | Álgebra exata: uma diferença se reduz a 0, um produto exato |
| `substitution` | Uma solução colocada de volta na equação original |
| `numeric` | O avaliador independente, quadratura, diferenças finitas |
| `comparison` | Um segundo método, diferente, chega ao mesmo resultado |
| `completeness` | Nada falta: Sturm, postos, primalidade, grau do resto |
| `domain` | O resultado existe onde o original existe |
| `execution` | A própria verificação: prazo esgotado ou erro interno |

`reason`: `completeness_not_proved`, `numeric_evidence_only`, `few_points`,
`too_large`, `inconclusive`, `no_strategy`, `deadline`, `internal_error`.

**Regras de consistência**, validadas pelo modelo (um relatório incoerente nem
chega a ser criado):

- `failed` exige uma checagem `failed`;
- `verified_*` exige alguma checagem `passed` e nenhuma `failed` (uma
  comparação inconclusiva pode acompanhar);
- `partial` exige checagens `passed` **e** `inconclusive`, e nenhuma `failed`;
- `unverified` e `not_applicable` não têm checagem `failed`;
- `partial` e `unverified` têm `reason`; os outros status, não.

Uma consequência da regra do `partial`: "nenhuma solução real encontrada, sem
prova" (como `sqrt(x) = -1`) passa de `partial` para `unverified`, porque nada
de positivo foi conferido.

### 2. Comparação de métodos

Cada comparação tem prazo próprio (1,5 s). Se ele acabar, a checagem fica
`inconclusive` e o resto da verificação continua. Quando os dois métodos
discordam **numericamente**, o resultado é `failed`; quando a igualdade apenas
não é provada, a checagem fica inconclusiva, e não reprova um resultado certo.

| Intent | Segundo método | Escopo | Status com a comparação |
|---|---|---|---|
| arithmetic | Aritmética racional exata (`Fraction`, sem SymPy) | Só racionais, + − × ÷ e potências inteiras | `verified_symbolic` |
| derivative | Derivador próprio (`verification/differentiate.py`): soma, produto, potência, cadeia e tabela de funções, sem o `diff` do SymPy (um teste garante) | Funções do vocabulário; `sign` (2ª derivada de `abs`) fica fora | `verified_symbolic` |
| limit | Continuidade no ponto: nenhum denominador nulo, `sqrt`/`ln` com argumento positivo, `tan` longe dos polos, `asin`/`acos` em (−1, 1), base positiva em potência com expoente variável. Decidido de forma exata no ponto. | Pontos finitos | `verified_symbolic` |
| integral definida | Newton–Leibniz: F(b) − F(a), com F' = f provado e F suave em [a, b] (Sturm em todo denominador, argumento de ln\|u\| e denominador de `atan`) | Polinômios e funções racionais com coeficientes e limites racionais | `verified_symbolic` |

Fora do escopo, nada muda: a verificação anterior continua valendo.

### 3. Prazos (`verification/deadline.py`)

- O worker dá à verificação até **80% do timeout** do cálculo (4 s de 5 s);
  o resto fica para formatar a resposta.
- O prazo é um timer `SIGALRM` (o SymPy não pode ser interrompido por outra
  thread). Os prazos se aninham: o total, o de cada comparação (1,5 s) e o de
  cada `simplify` (1 s, que vale como "não provado").
- `VerificationTimeout` herda de `BaseException`, como `KeyboardInterrupt`,
  para que nenhum `except Exception` de biblioteca o engula.
- Fora da thread principal, os prazos não fazem nada; o timeout duro do pool
  continua valendo.

### 4. Não verificável não é erro (`calculator.py`)

- Prazo esgotado: o resultado aparece com `unverified`, `reason: deadline` e
  uma checagem `execution` que diz que a conta foi feita, mas não conferida.
- Exceção num verificador: o mesmo, com `reason: internal_error`, e a exceção
  vai para o log.

### 5. Ajustes no que já existia

- **Raízes `CRootOf`** são substituídas por divisibilidade: a raiz é de um
  polinômio irredutível Q; ela satisfaz a equação exatamente quando Q divide o
  numerador e não divide o denominador. É exato e leva milissegundos.
- **Substituição não decidida** (a diferença não se reduziu a 0) deixa de
  reprovar: a checagem fica inconclusiva, o avaliador independente decide, e o
  status máximo passa a ser `verified_numeric`.
- **Diferenças finitas de ordem alta:** com passo fixo de 10⁻⁵, a 10ª
  derivada de `sin(x)^10 cos(x)^10` errava 3,5 × 10⁻⁷ (acima da tolerância de
  10⁻⁸) e um resultado certo era reprovado. Agora a precisão cresce com a ordem
  (80 + 10·n dígitos e passo 10^−k, com k = (40 + 10·n)/n; na ordem 10, 180 dígitos e passo 10⁻¹⁴), e o avaliador independente aceita
  uma precisão mínima.
- **Zero simbólico** (`verification/symbolic.py`): expandir, juntar frações e
  simplificar, nessa ordem, dizendo qual deles provou.

### 6. Cobertura

`tests/verification/test_tampering.py` adultera o resultado de **cada** intent
registrado e exige `failed`; um intent novo sem caso de adulteração faz o teste
falhar.

## Consequências

- O contrato da API mudou (`checks` virou objeto, `method` virou `methods`,
  entrou `reason`); o frontend foi atualizado e os fixtures recapturados.
- A interface mostra cada checagem com o tipo e ✓, ✗ ou ?, e o leitor de tela
  ouve "Passou", "Falhou" ou "Inconclusiva".
- Limitação conhecida: a integral definida de `1/(x^5 + x + 1)` em [0, 1] trava
  no **cálculo** (o `integrate` do SymPy), antes da verificação, e continua
  dando `TIMEOUT`.
- Sugestões registradas: comparação para integrais com limites irracionais
  (como 0 a π) e para funções trigonométricas; continuidade lateral em pontos
  de borda (como `sqrt(x)` em 0⁺).
