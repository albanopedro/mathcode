# ADR 0028 — Lint do frontend: oxlint, e por que não o ESLint

- **Status:** aceita
- **Data:** 2026-10-20

## Contexto

O backend tem lint: o `ruff` roda no [ADR 0027](0027-integracao-continua.md) e
a regra 8 do `CLAUDE.md` exige o projeto formatado. O frontend tinha **nada**:
só o `tsc --noEmit`, que diz se o código compila, mas não se ele está certo
(um `useEffect` com dependência errada compila igual).

A ferramenta padrão para isso é o ESLint. Mas neste projeto ela **não pode
funcionar**, e não por um detalhe de versão:

> O TypeScript 7 (o porte nativo, em Go) **não expõe mais a API de JavaScript**.
> O pacote `typescript` exporta apenas `version` e `versionMajorMinor`:
> `createProgram` e `createSourceFile` não existem.

O `typescript-eslint` — o parser que o ESLint usa para ler TypeScript — precisa
dessas funções. Com o TypeScript 7, ele não tem como montar a árvore sintática.
Não é uma briga de *peer dependency*: o `npm install` até passa com
`--legacy-peer-deps`, mas o parser não funciona.

O projeto usa TypeScript 7 de propósito (`"typescript": "^7.0.2"`), então
voltar para a versão 5 não é uma opção.

## Decisão

O lint do frontend é feito pelo **oxlint**, e a verificação de tipos continua
com o `tsc` do próprio TypeScript 7.

### Por que o oxlint

- **Ele lê TypeScript sozinho.** É escrito em Rust e tem o próprio parser: não
  depende do pacote `typescript`, então o TypeScript 7 não é problema.
- **O formato de configuração é o do ESLint v8** (`.oxlintrc.json`), com os
  mesmos nomes de regra: quem conhece o ESLint reconhece o arquivo.
- **É rápido.** A suíte de lint do frontend inteiro leva menos de um segundo,
  o que permite rodar a cada save.

### O que é exigido

| Categoria/regra | Nível | Por quê |
|---|---|---|
| `correctness` | erro | O que está errado de fato |
| `suspicious` | erro | O que quase sempre é um bug |
| `react` | erro | As regras dos hooks (dependências, refs) |
| `jsx-a11y` | erro | Acessibilidade, que o projeto leva a sério ([ADR 0019](0019-tema-e-acessibilidade.md)) |
| `import` | erro | Problemas de import |
| `vitest` | erro | Problemas nos testes |
| `unicorn` | erro | Regras modernizadoras |

**Três regras desligadas**, cada uma com um motivo:

- `react/react-in-jsx-scope`: obsoleta. Com o JSX automático (React 19 e
  `"jsx": "react-jsx"` no `tsconfig.json`), o `React` não precisa estar no
  escopo. A regra acusaria as 399 linhas de JSX do projeto.
- `import/no-unassigned-import`: os imports sem atribuição são como o CSS e o
  setup dos testes são carregados (`import "./index.css"`). O caso é legítimo.
- `unicorn/consistent-function-scoping`: estilo. As duas funções que a regra
  aponta estão bem onde estão.

### O que o lint encontrou (e o que foi corrigido)

Nenhum bug de lógica. O que apareceu foi qualidade:

- **`role="status"` em vez de `<output>`** (3 lugares: `CopyButtons`,
  `ApiStatus`, `Calculator`). O `<output>` tem `role="status"` implícito: é o
  elemento certo, e os testes que procuram por `getByRole("status")` continuam
  valendo.
- **`role="group"` em vez de `<fieldset>`** (2 lugares: `ThemeSelector`,
  `ResultBody`). O `<fieldset>` é o agrupamento canônico de controles.
- **Escrita em uma ref durante o render** (`MathEditor`): o padrão de "ref
  mais recente" escrevia `callbacks.current` no corpo do componente. Agora a
  atualização vai para um efeito.
- **`vi.fn()` sem tipo** (9 lugares, nos testes). Agora cada mock diz o que
  faz: `vi.fn<typeof fetch>()`, `vi.fn<(text: string) => Promise<void>>()`.

Um caso foi **mantido de propósito**: o container do gráfico do Plotly usa
`role="img"`, porque um `<img>` não pode conter o desenho do Plotly. O caso
está comentado no código, com o motivo.

### O pool do Vitest

O aviso do Vitest reclamava que o jsdom era criado **25 vezes** (uma por
arquivo), e o ambiente consumia metade do tempo da suíte. Agora o pool é
`vmThreads`: um jsdom por worker, e o isolamento por arquivo continua.

```
antes:  17,99 s   (51% do tempo no ambiente)
depois: 13,62 s   (32% no ambiente)
```

## Alternativas consideradas

- **ESLint com `--legacy-peer-deps`:** instalaria, mas o parser do
  TypeScript não funciona com o TypeScript 7. Rejeitado.
- **Voltar o TypeScript para a versão 5:** resolveria o ESLint, mas o projeto
  está no 7 de propósito. Rejeitado.
- **Biome:** traria lint e formatação juntos, e a formatação dele é uma
  opinião forte sobre o código do projeto, que já tem a sua. Rejeitado.
- **Não ter lint no frontend:** o `tsc` já pega muita coisa, e seria
  consistente com o resto do projeto. Mas o ADR 0019 mostra que o frontend
  recebeu mais cuidado do que a maioria; um linter é o que impede o cuidado de
  voltar a escorregar. Rejeitado.

## Consequências

- A CI ganha um passo `npm run lint` no job do frontend.
- Quem abre um pull request recebe a lista dos problemas em segundos.
- As regras de `jsx-a11y` e de hooks passam a valer: quem escrever
  `role="status"` de novo recebe a objeção na hora.
- **O lint é do oxlint, não do ESLint.** Se um dia o `typescript-eslint`
  passar a suportar o TypeScript 7, dá para trocar: o formato da configuração
  é o mesmo, e só as regras desligadas precisariam ser revistas.
- O `oxlint` entra como dependência de desenvolvimento, mais 2,4 MB.
