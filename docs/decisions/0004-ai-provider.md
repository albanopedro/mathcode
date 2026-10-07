# ADR 0004 — Camada de IA (`AIProvider`)

- **Status:** aceita; implementada na Fase 8, com os ajustes do
  [ADR 0009](0009-linguagem-natural-e-ia.md)
- **Data:** 2026-10-06

> Este é o desenho original. O que foi implementado (interface, campos,
> provedores e comportamento em falhas) está no ADR 0009, seção "Diferenças em
> relação ao ADR 0004".

## Contexto

A IA serve para entender pedidos em linguagem natural ("qual a derivada de
x² + 3x?"). Ela **não é a autoridade matemática** e nunca calcula. O projeto não
pode ter custo ([ADR 0001](0001-custo-zero.md)) e não pode ficar preso a um
único fornecedor.

## Decisão

### Interface

```python
class AIProvider(Protocol):
    name: str
    def interpret(self, text: str, context: InterpretContext) -> IntentCandidate: ...
```

`IntentCandidate` é um modelo Pydantic com estes campos:

- `intent`: valor de um `enum` fechado de intents;
- `parameters`: validados pelo schema daquele intent;
- `confidence`;
- `clarification_needed`: pergunta ao usuário quando o pedido for ambíguo.

### Regras

1. A resposta do modelo é **validada com Pydantic**. Um JSON inválido, um intent
   desconhecido ou um parâmetro fora do schema faz a resposta ser rejeitada, sem
   tentativa de "consertar".
2. As expressões vindas da IA são **texto** e passam pelo mesmo parser seguro
   ([ADR 0002](0002-parser-sem-eval.md)).
3. Qualquer resultado numérico que o modelo "sugira" é **ignorado**. Quem calcula
   é o Math Engine.
4. Nenhum código fora de `app/ai/` conhece um fornecedor específico.

### Provedores (somente gratuitos)

| Provedor | Uso | Observação |
|---|---|---|
| `none` (**padrão**) | — | Só o interpretador por regras. O sistema funciona sem IA. |
| `mock` | testes | Respostas fixas. Os testes nunca chamam rede. |
| `opencode` | IA gratuita | Roda `opencode run` com modelos marcados como gratuitos. Se a resposta indicar custo > 0, é erro. |
| `ollama` | IA local | É opcional e precisa ser instalado. Tudo roda no Mac. |

A escolha é feita por configuração (`MATHCODE_AI_PROVIDER`). Um provedor pago
**não está previsto**: incluir um exigiria revisar o ADR 0001.

### Privacidade

Com o `opencode`, o texto digitado vai para o servidor do modelo gratuito. Por
isso a IA é **opcional e desligada por padrão**. Durante o desenvolvimento, toda
chamada real a um modelo exige autorização prévia e usa exemplos fictícios.

## Consequências

- O interpretador por regras precisa cobrir bem os casos comuns, porque ele é o
  caminho padrão.
- Modelos gratuitos podem sair do ar. O sistema degrada para o modo `none`, com
  um aviso, e não para com erro.
