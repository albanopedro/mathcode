# Mathcode

Calculadora matemática que entende expressões e frases em português. Os
cálculos são feitos por um motor determinístico (SymPy) e **todo resultado
informa o quanto foi verificado**. A IA, que é opcional, só interpreta o
pedido: nunca é ela que calcula.

> **Estado: Fase 10 (matemática avançada): estatística, matrizes, vetores,
> geometria e probabilidade.**
> Pelo navegador ou pela API, o Mathcode já: calcula; simplifica, fatora e expande; resolve equações
> (polinomiais, racionais e outras) e sistemas lineares; divide polinômios;
> deriva, integra e calcula limites; desenha gráficos com raízes e intercepto;
> calcula média, mediana, moda e desvio padrão de uma lista; opera com
> matrizes (determinante, inversa, transposta, traço, posto, produto) e
> vetores (escalar, vetorial, norma, ângulo); calcula áreas, perímetros e
> volumes, Pitágoras e geometria analítica; conta (fatorial, arranjo,
> combinação, anagramas) e calcula probabilidades de eventos e da binomial;
> e entende frases como "qual a derivada de x^3?". Com "Permitir IA", frases
> mais livres são traduzidas por um modelo gratuito. Tudo vem com verificação
> independente, que diz quando provou o resultado, quando só tem evidência e
> quando não conseguiu conferir, e mostra cada checagem feita: substituição,
> avaliação numérica, comparação com um segundo método, completude.
> Os próximos passos estão no [roadmap](docs/roadmap.md).

## Princípios

- **Custo zero.** Tudo o que o projeto usa é gratuito e de código aberto
  ([ADR 0001](docs/decisions/0001-custo-zero.md)).
- **Nenhuma entrada vira código.** Sem `eval`; o parser é próprio
  ([ADR 0002](docs/decisions/0002-parser-sem-eval.md)).
- **Verificação explícita.** Cada resultado diz se foi verificado, e como:
  cada checagem tem um tipo e um resultado, e um segundo método confere o
  primeiro sempre que possível ([ADR 0003](docs/decisions/0003-verificacao.md),
  [ADR 0010](docs/decisions/0010-verification-engine.md)).

## Requisitos

- Python 3.14+
- Node.js 22.12+ (testado com 26) e npm

## Como rodar

### Backend (porta 8100)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --port 8100
```

- Health check: <http://127.0.0.1:8100/api/health>
- Documentação interativa: <http://127.0.0.1:8100/api/docs> (fora de produção)

### Frontend (porta 5180)

```bash
cd frontend
npm install
npm run dev
```

Abra <http://localhost:5180> e experimente, por exemplo:

| Operação | Entrada |
|---|---|
| Automático | `x² - 5x + 6 = 0`, `x + y = 3; x - y = 1`, `sen(30°)` |
| Fatorar | `x^4 - 1` ou `360` |
| Expandir | `(x + 1)^3` |
| Dividir polinômios | `(x^3 - 1)/(x - 1)` |
| Derivar (ordem 2) | `x² sen(x)` |
| Integrar (de `-inf` até `inf`) | `e^(-x^2)` |
| Limite (ponto `0`) | `sen(x)/x` ou `abs(x)/x` |
| Automático (vira gráfico) | `y = x² - 4x + 3` ou `sen(x); cos(x)` |
| Gráfico (x de `-2pi` até `2pi`) | `tan(x)` |
| Estatística | `2, 4, 4, 4, 5, 5, 7, 9` (resumo completo) |
| Matrizes (cálculo: Inversa) | `[[2, 1, 0], [1, 3, 1], [0, 1, 4]]` |
| Automático (matrizes) | `[[1, 2], [3, 4]] * [[5, 6], [7, 8]]` |
| Vetores (cálculo: Produto vetorial) | `[1, 2, 3]; [4, 5, 6]` |
| Geometria (Cone, Volume) | `r = 3; h = 4` |
| Probabilidade (cálculo: A ou B) | `P(A) = 1/2; P(B) = 1/3; P(A e B) = 1/6` |
| Calcular | `C(4, 2)/C(52, 2)` ou `5!` |
| Automático (frase) | `qual a derivada de x^3 - 2x?`, `15% de 780`, `integral de x^2 de 0 a 1`, `qual a média de 10, 20 e 30?`, `determinante de [[1, 2], [3, 4]]`, `ângulo entre os vetores [1, 0] e [1, 1]`, `qual a área de um círculo de raio 5?`, `quantos anagramas tem a palavra BANANA?` |

Em desenvolvimento, o Vite encaminha `/api` para o backend na porta 8100, então
rode os dois juntos.

### Usar a API

Com o backend rodando:

```bash
curl -s http://127.0.0.1:8100/api/calculate -H "Content-Type: application/json" -d '{"input": "2x + 5 = 17"}'
```

A resposta é um `MathResult`: resultado em texto, LaTeX e decimal, além da
verificação, dos avisos e do erro, se houver. Os detalhes e os códigos HTTP
estão em [docs/architecture.md](docs/architecture.md), seção 5.

### Configuração

Copie `.env.example` para `.env` na raiz. Todas as variáveis são opcionais.

### IA opcional (gratuita)

Por padrão, tudo roda localmente: frases comuns são entendidas por regras
próprias. Para frases mais livres ("resolva x mais 3 igual a 10"), dá para
ligar um modelo **gratuito** do [OpenCode](https://opencode.ai), já instalado e
com login feito:

```bash
MATHCODE_AI_PROVIDER=opencode .venv/bin/uvicorn app.main:app --port 8100
```

- A IA só é consultada nos pedidos em que o usuário marca **"Permitir IA"**.
  Nesses casos, a frase vai para o serviço do modelo.
- Só são aceitos modelos gratuitos (`opencode/<nome>-free`); o padrão é
  `opencode/space-bunny-free`.
- O OpenCode roda num diretório vazio, sem permissão para ler arquivos ou
  executar comandos.
- A resposta da IA passa pelo mesmo parser e pela mesma verificação, e a tela
  mostra como a frase foi interpretada.

Detalhes em [ADR 0009](docs/decisions/0009-linguagem-natural-e-ia.md).

## Testes e verificações

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

```bash
cd frontend
npm test
npm run build
```

## Estrutura

```
Mathcode/
├── backend/    FastAPI + Pydantic (Python)
│   ├── app/    api/ core/ models/ parsing/ interpreter/ math_engine/
│   │           verification/ formatting/ calculator.py main.py
│   └── tests/
├── frontend/   React + TypeScript + Vite + Tailwind
│   └── src/    components/ hooks/ services/ types/ utils/ test/
└── docs/       arquitetura, roadmap e decisões (ADRs)
```

As pastas das próximas fases (`planner/`, `ai/`...)
são criadas quando tiverem código. A estrutura completa planejada está em
[docs/architecture.md](docs/architecture.md).

## Documentação

- [Arquitetura](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Decisões (ADRs)](docs/decisions/)

## Licença

[MIT](LICENSE) © 2026 Pedro Albano
