# ADR 0007 — Cálculo: derivadas, integrais e limites (Fase 6)

- **Status:** aceita
- **Data:** 2026-10-07

## Contexto

Derivadas, integrais e limites precisam de parâmetros além da expressão: a
variável, a ordem da derivada, os limites de integração e o ponto e o lado do
limite. O SymPy também adota convenções que não valem em ℝ.

## Decisões

### 1. Parâmetros em campos, não no texto (decisão do usuário)

- A interface mostra campos conforme a operação:
  - Derivar: variável e ordem (1 a 10);
  - Integrar: variável, "de" e "até", que são opcionais (sem eles, a integral
    é indefinida);
  - Limite: variável, ponto e lado.
- A API recebe esses valores em `options`, por exemplo
  `{"input": "x^2", "intent": "integral", "options": {"lower": "0", "upper": "inf"}}`.
  É o mesmo formato tipado que a IA vai produzir na Fase 8.
- `options` só vale com `intent` explícito, e cada intent declara os campos que
  aceita (`INTENT_OPTIONS`).
- **Valores inválidos** são respostas, não falhas: HTTP 200 com
  `INVALID_INPUT_FOR_INTENT` e mensagem em português, como "A ordem da derivada
  precisa ser um número inteiro de 1 a 10.".
- **Tipos fora do formato** recebem 422, porque a API usa tipos estritos.
  `StrictStr` aceita até 100 caracteres; `StrictInt` aceita de −1000 a 1000.
  Sem isso, o Pydantic converteria um texto numérico longo num inteiro gigante.
- Limites de integração e pontos são texto e passam pelo mesmo parser seguro. Por
  isso aceitam `0`, `pi/2` ou `1,5`, além de `inf`, `∞`, `oo`, `infinito` e
  seus negativos. Os erros nesses campos dizem qual campo está errado e não
  trazem posição, porque ela apontaria para outro campo.

### 2. Convenções de ℝ que o SymPy não aplica

- **ln|u| nas primitivas.** O SymPy dá ∫1/x dx = log(x), que só vale para x > 0.
  Toda `log(u)` da primitiva vira `log(|u|)`, porque d/dx ln|u| = u'/u para todo
  u ≠ 0. O resultado é a forma dos livros, ln|x| + C, e vem com o aviso
  `ABSOLUTE_VALUE_IN_LOG`.
- **Limites só pelos lados em que a função é real.** O SymPy calcula lim √x
  (x→0) pela esquerda usando números complexos. Aqui cada lado é sondado
  numericamente. Se só um lado existe em ℝ, o limite pedido "pelos dois lados"
  vira o limite lateral, com o aviso `ONE_SIDED_DOMAIN`. Se nenhum lado existe, é
  `DOMAIN_ERROR`. A sondagem usa ponto flutuante, porque com valores exatos o
  SymPy tentava calcular (1 + 10⁻¹²)^(10¹²) e travava.
- **Laterais diferentes** resultam em "não existe" (`\nexists`), e os dois
  valores aparecem em `details`, como em |x|/x em 0. **Oscilação**
  (`AccumBounds`, como sin(1/x) em 0) também vira "não existe".
- **Integrais:**
  - divergentes (∫₁^∞ 1/x dx) são uma resposta: ∞, com `converges: false`;
  - integrais que não convergem (∫₋₁¹ 1/x dx, ∫₀^∞ sin x dx) e funções não
    reais no intervalo (∫₋₁¹ √x dx) são `DOMAIN_ERROR`.
- **Derivada de |u|:** o SymPy dá `sign(u)`, que vale 0 em u = 0, onde a
  derivada não existe. Por isso há o aviso `NOT_DIFFERENTIABLE_POINTS`.

### 3. Verificação (complementa o ADR 0003)

| Operação | Método independente | Status máximo |
|---|---|---|
| Derivada | Diferenças finitas com 80 dígitos (`mpmath.diff`) sobre o avaliador independente; erro relativo de até 10⁻⁸ (a ordem 10 ainda dá cerca de 10 dígitos) | `verified_numeric` |
| Integral indefinida | A primitiva precisa ser **real** onde o integrando é definido, e sua derivada precisa ser igual ao integrando (exato e em pontos). Derivar é um algoritmo diferente de integrar | `verified_symbolic` |
| Integral definida | Quadratura tanh-sinh (`mpmath.quad`, 30 dígitos), erro de até 10⁻¹⁰; quadratura imprecisa resulta em "inconclusivo" | `verified_numeric` |
| Integral divergente | — | `unverified` |
| Limite | Avaliar aproximando-se até 10⁻²⁴ do ponto (ou até 10²⁴). Isso é evidência, não prova | `partial` |

- **`mpmath.quad` no lugar do SciPy:** o mpmath já estava instalado, trabalha
  com precisão arbitrária e aceita intervalos infinitos. Isso adia uma
  dependência que só faz sentido na Fase 10.
- **A primitiva precisa ser real:** os testes mostraram que `log(x)` para ∫1/x
  passava, porque só a derivada era conferida. Agora isso é `failed`.
- Um limite só é `failed` quando a sequência de aproximação **estabiliza** longe
  do valor indicado. A convergência lenta (1/log x → 0) dá `unverified`, não um
  falso `failed`.

## Consequências

- Os campos de `details` de cada operação estão em
  [architecture.md](../architecture.md), seção 4, e as legendas da interface são
  montadas só a partir deles.
- Ficam como sugestão:
  - integrais definidas e limites com outras variáveis (parâmetros);
  - integrais sem forma fechada calculadas só numericamente;
  - domínio complexo.
