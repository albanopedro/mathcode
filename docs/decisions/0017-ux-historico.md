# ADR 0017 — UX: histórico, copiar e ajuda (Fase 11, etapa 1)

- **Status:** aceita
- **Data:** 2026-10-09

## Contexto

A Fase 11 (UX) tem quatro itens independentes. O usuário escolheu fazer todos,
**um por etapa**, como na Fase 10:

1. histórico, copiar e ajuda recolhível (esta etapa);
2. exato ↔ aproximado;
3. dark mode e acessibilidade;
4. teclado MathLive.

## Decisões do usuário

- **Histórico:** os últimos **50** cálculos, **só neste navegador**
  (`localStorage`). Nada vai para o servidor. Há um botão "Limpar histórico".
- **Copiar:** o resultado em texto e em LaTeX.
- **Ajuda:** o texto de ajuda, que estava longo, vira uma linha curta e um "Ver
  exemplos" agrupado por assunto.

## Decisão

- **`utils/history.ts`:**
  - **O que fica salvo:** cada item guarda a entrada, a operação (`intent`), os
    campos extras como estavam (`FieldValues`), a caixa "Permitir IA", se deu
    certo e um resumo (o resultado em texto, ou a mensagem de erro).
  - **Chave:** `mathcode.history.v1`.
  - **Ordem:** o mais novo vem primeiro, e o mesmo cálculo refeito sobe em vez de
    se repetir.
  - **Sem falhas:** ler e gravar nunca lançam erro. Numa janela privada ou com o
    armazenamento bloqueado, simplesmente não há histórico. Entradas malformadas
    são ignoradas, e campos que não existiam numa versão anterior recebem o valor
    padrão.
- **`hooks/useHistory.ts`:** guarda a lista e grava a cada mudança. O `submit` do
  `useCalculator` agora devolve o `MathResult` (ou `null`), e o `Calculator`
  registra o cálculo depois que a resposta chega. Erros de matemática também
  entram; falhas de rede, não.
- **`components/HistoryPanel.tsx`:**
  - painel recolhível "Histórico (N)";
  - **refazer:** clicar num item preenche o formulário (operação, campos, texto) e
    calcula de novo;
  - "✕" apaga um item;
  - "Limpar histórico" pede confirmação na própria tela, com "Confirmar: apagar
    tudo".
- **`components/CopyButtons.tsx`:** "Copiar texto" (o `plain`, na sintaxe da
  entrada) e "Copiar LaTeX", pela API de área de transferência. Uma linha
  `role="status"` confirma, ou avisa quando o navegador bloqueia.
- **`components/HelpText.tsx`:** a linha curta é a descrição do campo
  (`aria-describedby`). Os exemplos ficam num `<details>`, em 10 assuntos.

## Consequências

- O histórico depende do navegador: outro aparelho ou outro navegador não o vê.
- Os testes do frontend limpam o `localStorage` depois de cada caso
  (`test/setup.ts`).
- **Sugestões registradas:**
  - exportar ou importar o histórico;
  - busca no histórico;
  - fixar cálculos favoritos.
