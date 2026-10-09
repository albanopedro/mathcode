# ADR 0018 — Exato ↔ aproximado (Fase 11, etapa 2)

- **Status:** aceita
- **Data:** 2026-10-09

## Decisões do usuário

1. **Botão na manchete:** "Exato | Aproximado" troca a manchete (π/6 ↔ 0,523599).
   A escolha fica lembrada no navegador para os próximos resultados, e o botão
   só aparece quando há forma aproximada.
2. **Algarismos:** de 2 a 15, padrão 6. São algarismos significativos, e o
   backend não muda: a API já manda a aproximação com 15.
3. **Vírgula decimal** na forma aproximada (0,5236). "Copiar texto" continua
   copiando a forma exata na sintaxe da entrada, com ponto.

## Decisão

- **`utils/approximation.ts`:**
  - `formatApprox(approx, digits)` arredonda **cada número** do texto da API e
    troca o ponto pela vírgula;
  - as listas ("−1,41; 1,41") e os pontos ("(0,5, 1,73)") mantêm os seus
    separadores;
  - zeros finais somem (0,375, e não 0,375000);
  - expoentes viram potências de dez (1,235·10²⁰);
  - os algarismos são limitados a 2–15.
- **Preferência:** `{mode, digits}` no `localStorage` (`mathcode.display.v1`),
  lida e gravada sem nunca lançar erro (`hooks/useDisplay.ts`).
- **`ResultView`:**
  - **modo aproximado:** a manchete é "≈ 0,523599", e a forma exata aparece
    abaixo, menor;
  - **modo exato:** a manchete é a fórmula, e a linha "≈" aparece abaixo, já com
    os algarismos e a vírgula;
  - os botões usam `aria-pressed`, num grupo "Forma do resultado".
- **Fora do escopo desta etapa:** as aproximações que ficam dentro de fórmulas
  (graus de triângulos, a σ da binomial) e as da tabela de estatística
  continuam como o backend manda.

## Consequências

- O separador decimal da linha "≈" passou a ser a vírgula; dois testes antigos
  foram atualizados.
- **Sugestão registrada:** mais de 15 algarismos, o que exigiria a API
  devolver mais dígitos.
