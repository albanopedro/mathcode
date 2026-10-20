# ADR 0027 — Integração contínua: o que roda em cada push

- **Status:** aceita
- **Data:** 2026-10-20

## Contexto

O projeto tem 1 668 testes no backend e 354 no frontend, todos passando. Mas
eles rodavam **só na máquina de desenvolvimento**: nada impedia um commit que
quebrasse o build, e nada impedia um commit que reintroduzisse um bug de
segurança.

O [ADR 0026](0026-redos-e-event-loop.md) é o exemplo: um regex com backtracking
exponencial que derrubava o servidor inteiro estava no código desde a Fase 10, e
**nenhum teste falhou**, porque os testes cobriam o resultado, não o tempo de
resposta. O bug só apareceu numa auditoria.

Um segundo exemplo, na mesma auditoria: a verificação da área da esfera levava
1,04 s contra um orçamento de 1,5 s, e o teste da geometria falhava **2 em 5**
vezes com a máquina ocupada. Nada acusava isso: o teste era "verde" na maioria
das vezes, e a máquina de desenvolvimento quase nunca fica ocupada.

Faltava, portanto, a rede de segurança que essas duas situações pedem: rodar
tudo a cada push, em uma máquina limpa, e dizer o que quebrou.

## Decisão

Uma CI no GitHub Actions, com **dois jobs independentes** e nada além disso.

### 1. Dois jobs, sem serviço nenhum

| Job | Versão | Passos |
|---|---|---|
| `backend` | Python 3.14 | `pip install -e "backend[dev]"` → `ruff check .` → `ruff format --check .` → `pytest -q` |
| `frontend` | Node 22.12 e 26 | `npm ci` → `npm run typecheck` → `npm test` → `npm run build` |

- Os dois jobs são **independentes**: o frontend não precisa do backend, e
  vice-versa. Rodam em paralelo e um não espera o outro.
- **Nenhum segredo, nenhum serviço, nenhum deploy.** A CI só lê o repositório
  (`permissions: contents: read`) e roda testes. Isso mantém o custo zero
  ([ADR 0001](0001-custo-zero.md)) e evita que a CI vire mais uma coisa para
  manter.
- `npm ci` usa o `package-lock.json` e roda o `postinstall`, que copia o Swagger
  UI do npm para o backend: nada vem de CDN na CI também.

### 2. O frontend roda na versão mínima e na atual

O README pede Node 22.12+ e diz "testado com 26". A CI roda as duas:

- **22.12 (a mínima):** onde a incompatibilidade aparece. Se uma dependência
  subir de versão e parar de funcionar na mínima, a CI avisa antes de um
  usuário descobrir.
- **26 (a atual):** o que se usa no dia a dia.

As duas foram verificadas localmente antes de a CI existir (typecheck, 354
testes e build, nas duas versões).

### 3. A CI exige o projeto inteiro formatado

`ruff format --check .` roda no **projeto inteiro**, não só nos arquivos da
fase. A regra local continua sendo "formatar só os arquivos da fase" — para não
mexer em código que não é da fase —, mas o **estado final** passa a ser
exigido: se um arquivo estiver fora do formato, a CI falha e diz qual.

Isso vale para o ruff porque o projeto já está 100% formatado (123 arquivos) e
o `ruff format` é rápido e determinístico.

### 4. Detalhes que importam

- **Concorrência:** um push novo cancela a rodada anterior do mesmo branch.
  Nenhuma fila se acumula, e o resultado que interessa é o do último commit.
- **Tempo limite:** 15 minutos por job. A suíte do backend leva ~35 s e a do
  frontend ~25 s; o limite existe para um travamento não segurar a fila.
- **`fail-fast: false`** na matriz do Node: uma versão falhando não esconde o
  resultado da outra.
- **Roda em:** push na `main`, todo pull request, e na mão (aba Actions).

### 5. O que a CI **não** faz

- Não faz deploy, não publica nada, não cria release.
- Não roda o Docker: o `docker-compose.yml` continua adiado (ADR/roadmap), e a
  CI não é o lugar para testar um arquivo que não pode ser testado.
- Não mede cobertura de código. Os testes são de comportamento e de
  segurança; uma porcentagem de cobertura seria um número sem significado
  aqui.

## Alternativas consideradas

- **Um job só, com os dois.** Um job que falhasse no frontend esconderia o
  resultado do backend. Jobs separados dão o diagnóstico direto.
- **Só na `main`.** Um pull request só descobriria o problema no merge, e o
  merge já estaria feito.
- **Só `ruff check`, sem `ruff format --check`.** O lint pega erros; a
  formatação é o que impede que duas pessoas editem o mesmo arquivo de formas
  diferentes. O custo é zero e o projeto já está formatado.
- **Matriz de Python também.** O projeto exige `>=3.14` e usa recursos do 3.14
  (PEP 758). Testar 3.15 só valeria quando ela saísse; é uma linha para
  adicionar depois.
- **Rodar a CI em cada push de qualquer branch.** Muita notificação para um
  projeto que muda de branch uma vez por fase.

## Consequências

- A regra 8 do `CLAUDE.md` muda: formatar só os arquivos da fase continua
  sendo o costume local, mas a CI passa a exigir o projeto inteiro formatado.
- Cada push ganha um selo: verde significa que o parser segue sem `eval`, que
  a verificação segue funcionando, que o event loop segue livre e que a API
  segue respondendo como o contrato promete.
- O repositório passa a depender de `actions/checkout`, `actions/setup-python`
  e `actions/setup-node`. São ações oficiais, sem chave e sem conta.
- Se a CI ficar vermelha por um problema do ambiente (uma dependência que
  quebrou, por exemplo), o conserto é do lado do projeto — e o
  [ADR 0022](0022-pendencias-e-inicializador.md) mostra que o ambiente do
  projeto já é reproduzível.
