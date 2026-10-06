# Mathcode

Calculadora matemática que entende expressões e, mais adiante, perguntas em
linguagem natural. Os cálculos são feitos por um motor determinístico (SymPy)
e **todo resultado informa o quanto foi verificado**. A IA, quando existir,
só interpreta o pedido: nunca é ela que calcula.

> **Estado: Fase 4 (frontend básico).** Já é possível usar pelo navegador:
> aritmética, simplificação e equações do 1º grau, com o resultado em LaTeX, a
> verificação, os avisos e os erros apontando onde está o problema. Os próximos
> passos estão no [roadmap](docs/roadmap.md).

## Princípios

- **Custo zero.** Tudo o que o projeto usa é gratuito e de código aberto
  ([ADR 0001](docs/decisions/0001-custo-zero.md)).
- **Nenhuma entrada vira código.** Sem `eval`; o parser é próprio
  ([ADR 0002](docs/decisions/0002-parser-sem-eval.md)).
- **Verificação explícita.** Cada resultado diz se foi verificado, e como
  ([ADR 0003](docs/decisions/0003-verificacao.md)).

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

Abra <http://localhost:5180> e digite, por exemplo, `2x + 5 = 17`,
`x² + 2x + x²` ou `sen(30°)`. Em desenvolvimento, o Vite encaminha `/api` para
o backend na porta 8100, então rode os dois juntos.

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
