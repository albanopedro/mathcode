# ADR 0023 — Resultado ao vivo

- **Status:** aceita
- **Data:** 2026-10-11

## Contexto

O usuário pediu uma interface mais dinâmica. Entre as ideias oferecidas
(resultado ao vivo, exemplos clicáveis, duas colunas e animações), ele escolheu
só o **resultado ao vivo**, numa única etapa.

## Decisão

O Mathcode calcula sozinho quando a digitação faz uma pausa de 600 ms. O botão
Calcular e o Enter continuam existindo.

- **Interruptor "Ao vivo":**
  - fica ao lado de "Editor visual", com `aria-pressed`;
  - vem **ligado** e a escolha fica lembrada no navegador (`mathcode.live.v1`,
    em `utils/live.ts`; ler e gravar nunca lançam erro).
- **O que dispara:** mudar o texto, a operação ou os campos extras. Um texto
  vazio limpa o resultado.
- **Nunca usa a IA.** O pedido ao vivo não envia `allow_ai`, mesmo com a caixa
  marcada, e a ajuda da caixa avisa isso. A IA só entra quando o usuário aperta
  Calcular ou Enter, então não há envio de texto para fora sem querer.
- **Não entra no histórico.** Só Calcular, Enter e "refazer" gravam, senão cada
  pausa viraria um item.
- **Sem repetir:** o último pedido feito é lembrado, então apertar Calcular
  logo depois, ou refazer um item do histórico, não dispara outra conta ao
  vivo para o mesmo texto.
- **Sem piscar:** durante um cálculo ao vivo o resultado anterior continua na
  tela, mais claro, até o novo chegar. Um cálculo novo cancela o anterior.
  - A transição respeita "reduzir movimento".
- **Entrada incompleta não é erro:**
  - ao vivo, "2 +" mostra uma dica discreta, "Ainda não dá para calcular: …",
    sem `role="alert"`, e o leitor de tela não a anuncia;
  - já o Calcular continua mostrando o erro completo, com a posição.
- **Anúncio:** o resultado ao vivo é anunciado com o mesmo aviso curto de
  antes, só quando dá certo.

## Consequências

- Cada pausa é uma requisição à API local. O custo é o do motor, que roda no
  próprio computador do usuário, e o pool já limita a fila (503 se encher).
- Quem preferir o jeito antigo desliga o interruptor.
- **Sugestões registradas:** exemplos clicáveis por assunto, layout em duas
  colunas no computador, animações dos passos do assistente e pré-visualização
  do gráfico enquanto se digita.
