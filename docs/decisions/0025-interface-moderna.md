# ADR 0025 — Interface moderna

- **Status:** aceita
- **Data:** 2026-10-13

## Contexto

O usuário pediu uma interface mais "moderna". Ele escolheu entre três direções
(limpo com cor de destaque, gradiente e vidro, ferramenta em duas colunas):

- **Estilo:** limpo, com uma cor de destaque (índigo);
- **Animações:** sim, discretas;
- **Fonte:** Inter, servida pelo próprio app.

## Decisão

### Identidade

- **Cor de destaque:** índigo, no botão Calcular, nas pílulas ativas, nos
  interruptores ligados, no foco do teclado e nos selos. O resto continua
  neutro (slate), e as cores de estado (verde, âmbar, vermelho) não mudaram.
- **Tema escuro:** o índigo entrou no bloco espelhado do `index.css`, com a
  mesma regra do ADR 0019 (50↔950 … 600→300). Assim, no escuro, o botão vira
  índigo claro com texto escuro, e o contraste continua igual ao do claro.
- **Fonte:** Inter variável (`@fontsource-variable/inter` 5.3.0, licença OFL,
  versão fixa).
  - Os arquivos vão dentro do pacote do app. Nada vem do Google Fonts nem de
    CDN, e tudo funciona offline (ADR 0001).
  - O navegador baixa só os subconjuntos usados. Para o português, isso é o
    latino, com 48 kB.
- **Cabeçalho:** uma marca (∑ num quadrado índigo) e um brilho índigo bem
  suave atrás do topo, só decorativo.

### Peças compartilhadas (`index.css`, `@utility`)

Cada peça é definida uma vez e usada em todo lugar, para tudo ter a mesma
cara: `card`, `btn-primary`, `btn-secondary`, `field`, `pill`, e as cores
`pill-off` e `pill-on`.
- **Cantos e sombras:** cantos maiores (`rounded-2xl` nos cartões) e sombras
  leves.
- **Bordas dos campos:** continuam em slate-500, para manter 3:1 contra a
  página (ADR 0019).

### Formulário

- **Operações em pílulas:** Automático, Assistente, Equação, Derivar, Integrar
  e Gráfico. São um grupo de rádio nativo ("Operações frequentes"), então as
  setas do teclado funcionam sem código próprio.
- **Mais operações:** as outras ficam na lista "Mais operações…", que ainda
  tem todas e continua sendo o controle chamado "Operação". Quando uma operação
  da lista está ativa, ela fica destacada.
- **Campo como barra de busca:** o campo e o botão Calcular ficam numa caixa
  só, e o foco aparece na caixa inteira.
- **Interruptores:** "Ao vivo" e "Editor visual" viraram pequenas pílulas com
  uma luz que acende quando estão ligados.
- **Exemplos:** os cartões ganharam borda índigo ao passar o mouse, e o assunto
  aparece em índigo.

### Resultado

- **Destaque:** o resultado fica num painel suave, e a operação aparece num
  selo índigo.
- **Assistente:** os passos têm um número num círculo. O nome acessível do
  passo continua "1. Raízes", definido por `aria-label`.
- **Enquanto o primeiro cálculo não chega:** aparece um esqueleto do cartão,
  pulsando de leve.

### Animações

- **Entrada:** `animate-fade-up` faz o elemento aparecer subindo 6 px em
  220 ms.
- **Onde:** cada resultado novo entra assim, porque `seq` em `useCalculator`
  muda a chave a cada resposta. Os passos do assistente entram em sequência,
  com 70 ms entre um e outro, e o erro e a dica do modo ao vivo também.
- **Movimento reduzido:** a regra global de `prefers-reduced-motion` (ADR 0019)
  desliga tudo.

## Verificação

- **Contraste:** auditoria no navegador, pelo canvas e pela fórmula WCAG, com
  um resultado do assistente e todos os detalhes abertos. Nenhuma falha no
  claro (132 textos checados) e nenhuma no escuro.
- **Celular (375 px):** sem rolagem lateral. O seletor de tema passa para a
  linha de baixo do título. Esse corte apareceu na conferência no navegador e
  foi corrigido.
- **Nada externo:** a fonte e o resto vêm só do `localhost`.

## Consequências

- O pacote principal tem 294 kB (eram 289), e a fonte latina tem 48 kB.
- **Para manter a cara:** uma cor nova precisa entrar no bloco espelhado
  (ADR 0019), e componentes novos devem usar as peças compartilhadas.
- **Sugestões registradas:** layout em duas colunas no computador, e a
  pré-visualização do gráfico enquanto se digita.
