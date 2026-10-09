# Roadmap

Regras gerais:

- uma fase por vez;
- ao fim de cada fase: testes + build + relatório, e depois **parada até a
  autorização**;
- nenhum commit é feito pelo assistente;
- custo zero ([ADR 0001](decisions/0001-custo-zero.md)).

| Fase | Nome | Status |
|---|---|---|
| 0 | Auditoria e arquitetura | concluída |
| 1 | Foundation | concluída |
| 2 | Core matemático | concluída |
| 3 | API | concluída |
| 4 | Frontend básico | concluída |
| 5 | Álgebra | concluída |
| 6 | Cálculo | concluída |
| 7 | Gráficos | concluída |
| 8 | Linguagem natural / IA | concluída |
| 9 | Verification Engine | concluída |
| 10 | Matemática avançada | concluída |
| 11 | UX e histórico | em andamento: histórico, copiar e ajuda feitos (aguardando revisão); faltam exato ↔ aproximado, dark mode e acessibilidade, MathLive |
| 12 | Assistente matemático | — |

## Fase 0 — Auditoria e arquitetura

Entregou `docs/architecture.md`, este roadmap e os ADRs de 0001 a 0005.
Nenhum código foi escrito.

## Fase 1 — Foundation

- **Backend (porta 8100):**
  - `pyproject.toml` com FastAPI, Uvicorn, Pydantic e pydantic-settings, mais
    pytest, httpx2 e ruff como dependências de desenvolvimento;
  - `app/main.py` (`create_app`) e `GET /api/health` (status, versão e
    ambiente);
  - `core/config.py` lendo variáveis `MATHCODE_*` e o `.env` da raiz;
    `/api/docs` fica desligado em produção;
  - testes do health check e da configuração; avisos contam como erro no
    pytest.
- **Frontend (porta 5180):**
  - Vite + React + TypeScript + Tailwind;
  - o Vite encaminha `/api` para o backend, então não é preciso CORS;
  - a página inicial mostra apenas o status da API, com botão "Tentar de novo",
    sem recursos falsos; a resposta da API é validada antes de ser usada;
  - Vitest + Testing Library.
- **Raiz:** `README.md`, `.env.example`, `.gitignore`, `LICENSE` (MIT).
- **Fora do projeto:** entradas `mathcode-api` e `mathcode-web` no
  `codes(dw)/.claude/launch.json`.
- **Compatibilidade conferida:** FastAPI, SymPy 1.14, NumPy 2.5 e SciPy 1.18
  têm versão para Python 3.14 (as três últimas só serão instaladas nas fases
  em que forem usadas).
- **Critério de saída:** `pytest`, `ruff check`, `npm test` e `npm run build`
  passando, e o health check visível no navegador.

## Fase 2 — Core matemático (sem API e sem IA)

- `parsing/` completo para a gramática do ADR 0002, com limites.
- Intents: `arithmetic`, `simplify` (básico) e `solve_equation` (linear, uma
  variável).
- Verificação conforme o ADR 0003, para esses três intents.
- `MathResult` e os códigos de erro.
- **Critério de saída:** testes unitários com casos normais, inválidos e
  maliciosos.
- **Entregue:**
  - parser sem `eval`, com posições de erro no texto original e avisos de
    ambiguidade;
  - os três intents, cada um com verificador independente (mpmath);
  - `calculate()` devolvendo `MathResult`;
  - 342 testes no backend, incluindo resultados adulterados que a verificação
    precisa pegar e uma checagem de que `eval`/`sympify` não aparecem no código.
- **Decidido durante a fase** (registrado nos ADRs 0002, 0003 e 0005):
  - limite de 4 000 dígitos, por causa da proteção do Python 3.14;
  - precisão adaptativa e tolerância de 30 algarismos na verificação;
  - `0^0` é indeterminação;
  - raiz real para índice ímpar;
  - aviso em `f(x)` e erro em `1e5`.

## Fase 3 — API

- `POST /api/calculate` → `MathResult`.
- Pool de processos com timeout (ADR 0002, seção 4).
- Mapeamento de erros para HTTP. Todo erro de matemática é `200` com
  `success: false`; `422` fica reservado para requisições malformadas.
- Testes de integração.
- **Entregue:**
  - `app/api/calculate.py`, com validação Pydantic (`extra="forbid"`, `intent`
    como enum, `input` até 2 000 caracteres);
  - `app/core/workers.py`: workers `spawn` aquecidos, timeout com SIGKILL e
    substituição, `TIMEOUT`, `INTERNAL_ERROR` (500) e `SERVER_BUSY` (503);
  - configuração `MATHCODE_WORKERS`, `MATHCODE_CALCULATION_TIMEOUT` e
    `MATHCODE_QUEUE_TIMEOUT`;
  - 30 testes de integração com processos reais (timeout, worker morto e
    substituído, fila cheia, pedidos em paralelo, 422).
- **Descoberto:** entradas válidas como `(x+1)^1000*(x+2)^1000` levavam minutos
  no SymPy. Agora são cortadas em 5 s.

## Fase 4 — Frontend básico

- Campo de entrada, botão Calcular e exibição do resultado com KaTeX.
- Estados de carregamento, erro e verificação.
- Testes de componentes.
- **Entregue:**
  - interface com resultado em KaTeX (fontes locais), aproximação, operação
    detectada, "Entendido como", verificação com "Como foi verificado" e avisos;
  - erro com a posição destacada na entrada, além de timeout, falha de
    verificação e API inacessível;
  - acessibilidade: `aria-live`, `role="alert"`, MathML do KaTeX e rótulo no
    campo;
  - 60 testes Vitest (eram 13), com fixtures que são respostas reais da API.
- **Descoberto no navegador:** `2^10000` ficava cortado (uma linha de cerca de
  36 000 px). Resultados longos agora aparecem como texto que quebra linha.

## Fase 5 — Álgebra

Fatoração, expansão, polinômios, equações gerais (quadráticas, polinomiais e
racionais) e sistemas. Cada item tem testes e uma estratégia de verificação.

- **Escopo decidido com o usuário** ([ADR 0006](decisions/0006-escopo-da-algebra.md)):
  - seletor de operação na interface;
  - "polinômios" = divisão de polinômios;
  - sistemas só lineares.
- **Entregue:**
  - `factor` (sobre ℚ; inteiros viram fatoração em primos);
  - `expand`;
  - `polynomial_division` (quociente e resto);
  - `solve_equation` geral (polinomial de qualquer grau, racional e outras);
  - `solve_system` linear (única, infinitas ou nenhuma).
- **Verificação:**
  - a completude das equações polinomiais e racionais é provada pelo
    **teorema de Sturm**;
  - nos sistemas, pelos postos das matrizes;
  - raízes estranhas são pegas pelo avaliador independente;
  - quando a completude não pode ser provada, o status é `partial`.
- **Frontend:**
  - seletor de operação com exemplo próprio;
  - legendas a partir de `details`;
  - sistemas exibidos com chave e raízes uma por linha.
- **Testes:** 507 no backend (eram 372) e 105 no frontend (eram 60).
- **Descoberto durante a fase:**
  - a verificação da divisão reprovava resultados certos, porque fazia contas
    fora do contexto de alta precisão do mpmath;
  - uma raiz faltando dava `partial` em vez de `failed`;
  - várias raízes numa linha estouravam a tela do celular.

## Fase 6 — Cálculo

Derivadas, integrais indefinidas e definidas, e limites. A verificação segue a
tabela do ADR 0003.

- **Decidido com o usuário:** os parâmetros vêm de **campos na interface**, não
  de sintaxe no texto ([ADR 0007](decisions/0007-calculo.md)).
- **Entregue:**
  - `derivative` (ordem 1 a 10, qualquer variável);
  - `integral`, indefinida (com ln|u| em ℝ) ou definida (limites infinitos,
    divergência como resposta);
  - `limit`, com lados, infinito, "não existe" e domínio real;
  - `options` na API, com tipos estritos;
  - campos condicionais na interface.
- **Verificação:**
  - diferenças finitas de 80 dígitos para derivadas;
  - derivar a primitiva (e exigir que ela seja real) para integrais
    indefinidas;
  - quadratura tanh-sinh para integrais definidas;
  - aproximação até 10⁻²⁴ para limites, com status no máximo `partial`.
- **Testes:** 642 no backend (eram 507) e 137 no frontend (eram 105).
- **Descoberto durante a fase:**
  - o SymPy dá ∫1/x = log(x), que só vale para x > 0;
  - o SymPy calcula √x à esquerda de 0 com números complexos;
  - uma sondagem exata travava em (1 + 1/x)^x;
  - o verificador aceitava a primitiva log(x), porque só conferia a derivada;
  - a API aceitava um texto numérico longo como inteiro gigante;
  - a mensagem de "verificação parcial" falava em completude, o que não serve
    para limites.

## Fase 7 — Gráficos

- Funções cartesianas, com amostragem pelo NumPy no backend.
- Domínio e descontinuidades: os pontos fora do domínio são cortados, não
  ligados por uma linha.
- Múltiplas funções e pontos relevantes (raízes, interceptos).
- Plotly.js no frontend.

- **Decidido com o usuário** ([ADR 0008](decisions/0008-graficos.md)):
  Plotly.js básico, carregado sob demanda; faixa de x por campos (padrão −10 a
  10).
- **Entregue:**
  - várias funções (`;`) e `y = f(x)`, com detecção automática;
  - 801 amostras por função pelo avaliador independente (sem NumPy);
  - cortes no domínio e nas assíntotas, e eixo y robusto;
  - raízes (exatas ou numéricas) e intercepto, conferidos;
  - gráfico interativo (zoom, arrastar) e pontos listados em texto.
- **Testes:** 696 no backend (eram 642) e 162 no frontend (eram 137).
- **Descoberto durante a fase:**
  - `0` como raiz perdida quando cai exatamente numa amostra;
  - raízes nas pontas da faixa;
  - **falsas raízes perto de polos**, aceitas também pelo verificador;
  - o status `not_applicable` sem mensagem, que quebrava o pipeline;
  - o botão do Plotly que **envia o gráfico para a nuvem**, ligado por padrão;
  - a legenda cortada no celular.

## Fase 8 — Linguagem natural / IA

- `AIProvider` com os provedores `none`, `mock`, `opencode` e `ollama`
  (ADR 0004).
- Interpretador por regras para frases comuns em português.
- Testes só com o mock. Uma chamada real só acontece com autorização.

- **Decidido com o usuário** ([ADR 0009](decisions/0009-linguagem-natural-e-ia.md)):
  caixa "Permitir IA" por pedido, desmarcada por padrão; poucas chamadas reais
  com frases fictícias; Ollama adiado até ser instalado.
- **Entregue:**
  - regras locais em português (derivada, integral, limite, raízes, resolver,
    fatorar, expandir, simplificar, gráfico, dividir, porcentagem e o aviso de
    "ainda não suportado"), com a posição dos erros no texto digitado;
  - provedor `opencode` isolado (diretório vazio, agente sem permissões, só
    modelos gratuitos) e `mock` para os testes;
  - IA no processo da API, com no máximo 2 consultas simultâneas e timeout
    próprio; a resposta passa pelo mesmo parser, schema e verificação;
  - campo `interpretation` no `MathResult`, mostrado na interface (com
    "Confira" quando veio da IA);
  - erros `AI_UNAVAILABLE` e `AI_FAILED`, e `AMBIGUOUS_INPUT` com a pergunta
    da IA.
- **Testes:** 822 no backend (eram 696) e 181 no frontend (eram 162). Foram 5
  chamadas reais autorizadas.
- **Descoberto durante a fase:**
  - o OpenCode v2 não tem mais `--dir` (agora há `--standalone`) e não informou
    custo nos eventos;
  - no prompt inicial, o modelo **calculou** a resposta, em vez de traduzir;
  - frases que só começam com "qual" ou "quanto vale" nunca chegariam à IA
    (corrigido: o que precisa passar no parser é a parte matemática);
  - "integral dupla de x" não é barrada pelas regras (a regra de integral
    fica com "dupla de x"); com a IA, o prompt agora manda recusar o que não é
    suportado, em vez de trocar por uma operação parecida.

## Fase 9 — Verification Engine

Formalizar e expandir a verificação: comparação de métodos, relatórios
detalhados e cobertura de todos os intents.

- **Decidido com o usuário** ([ADR 0010](decisions/0010-verification-engine.md)):
  checagens estruturadas; quatro comparações de métodos; resultado não
  verificável aparece como "não verificado", com o motivo, e não como erro.
- **Entregue:**
  - relatório com checagens tipadas (simbólica, substituição, numérica,
    comparação de métodos, completude, domínio, execução), resultado de cada
    uma, estratégias usadas e motivo; regras de coerência entre status e
    checagens validadas pelo modelo;
  - comparação de métodos: frações exatas (aritmética), derivador próprio
    (derivadas), continuidade (limites) e Newton–Leibniz (integrais definidas
    de polinômios e racionais);
  - prazos aninhados para a verificação (SIGALRM no worker): estourar o prazo
    ou quebrar deixa o resultado `unverified`, com o motivo;
  - interface com ✓, ✗ ou ? e o tipo de cada checagem;
  - matriz de adulteração que cobre todos os intents.
- **Testes:** 950 no backend (eram 822) e 189 no frontend (eram 181).
- **Descoberto durante a fase:**
  - a verificação de `x^20 - 3x^7 + 1 = 0` levava mais de 20 s (o
    `simplify` de raízes `CRootOf`) e virava `TIMEOUT`; agora usa
    divisibilidade e leva 44 ms;
  - a 10ª derivada de `sin(x)^10 cos(x)^10` era **reprovada** por imprecisão
    das diferenças finitas; a precisão agora cresce com a ordem;
  - a integral definida de `1/(x^5 + x + 1)` trava no cálculo (limitação do
    SymPy, anterior a esta fase);
  - o texto simples dos resultados escreve o logaritmo natural como `log`, que
    na entrada é base 10 (anterior a esta fase; registrado como pendência).

## Fase 10 — Matemática avançada

Estatística, probabilidade, matrizes/vetores, geometria e trigonometria, **um
domínio por alteração**.

### 10.1 — Estatística descritiva (feita)

- **Decidido com o usuário** ([ADR 0011](decisions/0011-estatistica-descritiva.md)):
  estatística primeiro; média, mediana, moda, variância, desvio, mínimo,
  máximo, amplitude, soma e n; σ populacional como resposta, com s amostral
  junto; resumo completo pela operação, medida destacada pela frase.
- **Entregue:**
  - intent `statistics` (opção `measure`) e operação "Estatística";
  - listas de números no parser só nesse modo;
  - frases ("qual a média de 10, 20 e 30?", "desvio padrão amostral de…",
    "maior valor de…");
  - cálculo exato com frações; verificação por releitura dos valores, pelo
    módulo `statistics` do Python e por propriedades exatas;
  - tabela de resumo na interface.
- **Testes:** 1 016 no backend (eram 950) e 201 no frontend (eram 189).

### 10.2 — Matrizes (feita)

- **Decidido com o usuário** ([ADR 0012](decisions/0012-matrizes.md)):
  determinante, inversa, transposta, traço, posto e aritmética de matrizes;
  só números exatos (até 8×8); sintaxe `[[1, 2], [3, 4]]`; operação
  "Matrizes" com o campo "Cálculo".
- **Entregue:**
  - colchetes no parser e o nó `Matrix`;
  - intent `matrix` (opção `operation`), detectado no Automático;
  - frases ("determinante de [[…]]", "inversa de…", "traço da matriz…");
  - verificação exata (frações e álgebra própria) ou numérica (mpmath), com
    determinante por Gauss, A·A⁻¹ = I nos dois lados, transposição, traço e
    posto refeitos;
  - resultado em KaTeX e a matriz A exibida.
- **Testes:** 1 089 no backend (eram 1 016) e 213 no frontend (eram 201).

### 10.3 — Vetores (feita)

- **Decidido com o usuário** ([ADR 0013](decisions/0013-vetores.md)): soma,
  subtração e múltiplo; escalar, norma, unitário e ângulo; vetorial (3D);
  matriz × vetor; operação "Vetores" com o campo "Cálculo"; ângulo em
  radianos exatos e em graus.
- **Entregue:**
  - `[1, 2, 3]` no parser;
  - avaliador de álgebra linear comum a matrizes e vetores (vetor = coluna);
  - intent `vector` e frases ("produto escalar de [1, 2] e [3, 4]", "ângulo
    entre os vetores…", "norma de…");
  - verificação exata ou numérica por outro caminho (‖u‖² = u·u,
    ortogonalidade e Lagrange no vetorial, cos θ);
  - "u = (…)", "v = (…)" na interface.
- **Testes:** 1 160 no backend (eram 1 089) e 225 no frontend (eram 213).

### 10.4 — Geometria (feita)

- **Decidido com o usuário** ([ADR 0014](decisions/0014-geometria.md)): figuras
  planas, sólidos, geometria analítica, Pitágoras e classificação; operação
  "Geometria" com Figura e Cálculo e medidas `r = 5`; pontos `(1, 2)`; sem
  unidades.
- **Entregue:**
  - catálogo de 14 figuras e 10 cálculos, com erros explicados;
  - pontos no parser;
  - frases ("qual a área de um círculo de raio 5?", "hipotenusa de um
    triângulo de catetos 3 e 4", "distância entre (1, 2) e (4, 6)");
  - verificação por outro método (vértices e cadarço, integração e sólidos de
    revolução, coordenadas no lugar de Heron, leque de triângulos);
  - fórmula usada e tipo de grandeza na interface.
- **Testes:** 1 275 no backend (eram 1 160) e 239 no frontend (eram 225).

### 10.5 — Probabilidade e contagem (feita)

- **Decidido com o usuário** ([ADR 0015](decisions/0015-probabilidade.md)): os
  dois domínios restantes, um por alteração, a probabilidade primeiro; todos os
  conteúdos (contagem, anagramas, eventos, binomial); `5!`, `C(10, 3)` e
  `A(6, 2)` na linguagem; eventos como `P(A) = 1/2`; fração + porcentagem
  (aceita `30%`); operação "Probabilidade" + Cálculo.
- **Entregue:**
  - fatorial, arranjo e combinação em qualquer expressão (`C(4, 2)/C(52, 2)`),
    com ambiguidades recusadas (`3!!`, `C(10,3)`);
  - catálogo de 16 cálculos em três grupos, com erros explicados e coerência
    dos eventos conferida;
  - frases ("combinação de 10 tomados 3 a 3", "quantos anagramas tem a palavra
    BANANA?", "binomial com n = 5, k = 3 e p = 1/2", "probabilidade de A ou B
    com…");
  - verificação por outro caminho (definições com inteiros, listagem uma a uma,
    regiões de Venn, recorrência da binomial);
  - porcentagem com vírgula e a fórmula usada na interface.
- **Testes:** 1 451 no backend (eram 1 275) e 257 no frontend (eram 239).

### 10.6 — Trigonometria (feita)

- **Decidido com o usuário** ([ADR 0016](decisions/0016-trigonometria.md)):
  todos os conteúdos (valores e conversões, equações, identidades,
  triângulos); operação "Trigonometria" + Cálculo, com as equações onde já
  estavam; solução geral + as soluções de [0, 2π) (ou do intervalo dado);
  `a = 5; b = 7; C = 60°` → triângulo completo; identidade com prova ou
  contraexemplo.
- **Entregue:**
  - sec, csc e cot na linguagem;
  - equações periódicas em famílias (junção, domínio, intervalo, até 100
    listadas), com completude provada por redução a um polinômio em
    sin/cos/tan (Sturm) ou evidência por varredura;
  - conversão, redução ao 1º quadrante, identidades e triângulos (inclusive
    o caso ambíguo), verificados por outro caminho (avaliador independente,
    exponenciais, triângulo no plano);
  - frases e os campos "Soluções de / até";
  - um bug do SymPy contornado: `tan(2kπ + 2π/3)` com k inteiro.
- **Testes:** 1 563 no backend (eram 1 451) e 274 no frontend (eram 257).
- **Próxima fase:** 11 (UX e histórico).

## Fase 11 — UX e histórico

Histórico local, copiar resultado, alternar entre exato e aproximado, teclado
MathLive, acessibilidade, responsividade e dark mode. **Decidido com o usuário:
todos os itens, um por etapa.**

### 11.1 — Histórico, copiar e ajuda (feita)

- **Decidido** ([ADR 0017](decisions/0017-ux-historico.md)): os últimos 50
  cálculos só neste navegador; copiar em texto e LaTeX; ajuda recolhível.
- **Entregue:** painel "Histórico" (refazer com operação e campos, apagar,
  limpar com confirmação); botões de copiar com confirmação acessível; ajuda
  em uma linha + exemplos por assunto.
- **Testes:** 1 563 no backend (sem mudança) e 286 no frontend (eram 274).
- **Próximas etapas:** exato ↔ aproximado; dark mode e acessibilidade; MathLive.

## Fase 12 — Assistente matemático

Pedidos compostos ("raízes, vértice e gráfico de f(x)") viram um
`ExecutionPlan` com vários passos. Cada passo é executado e verificado de forma
determinística.

## Sugestões registradas (fora do escopo atual)

- Domínio complexo como opção explícita.
- Sistemas não lineares; divisão de polinômios com várias variáveis.
- Passos de resolução gerados por regras próprias.
- `docker-compose.yml`, quando houver Docker para testar.
- Provedor de IA Ollama (local), quando estiver instalado.
- Regras locais para frases frequentes ("o dobro de", "a metade de").
- Comparação de métodos para integrais com limites irracionais (0 a π) e
  funções trigonométricas; continuidade lateral em pontos de borda (`sqrt(x)`
  em 0⁺).
- Corrigir o texto simples do logaritmo natural (`log` → `ln`).
- Estatística: quartis e IQR (com convenção explicada), média ponderada,
  tabela de frequências, dados irracionais, rótulo "Dados" no campo de entrada.
- Matrizes: autovalores e autovetores (tratar complexos), matrizes com letras,
  editor em grade (Fase 11).
- Vetores: projeção, produto misto, vetor × matriz (linha), vetores com letras.
- Geometria: unidades, perímetro do trapézio, polígonos regulares, setor
  circular, pirâmide e prisma, distância de ponto a reta, pontos com nome
  (`A(1, 2)`); resumir o texto de ajuda da calculadora (Fase 11).
- Probabilidade: fatorial com variáveis (`(n + 1)!/n!`), fatorial duplo,
  permutação circular, outras distribuições (geométrica, Poisson, normal),
  tabela e gráfico da binomial, mais de dois eventos, probabilidades
  irracionais.
- Trigonometria: inequações trigonométricas; completude provada para equações
  como sin(x) = cos(x); graus, minutos e segundos; área do triângulo pelos
  senos; filtrar por intervalo as equações com soluções finitas.
- Histórico: exportar/importar, busca, favoritos.
- Atalho para iniciar o projeto no macOS (como o `DevAI.command`), se fizer
  sentido.
