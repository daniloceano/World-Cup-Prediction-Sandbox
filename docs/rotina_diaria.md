# Rotina diária — como alimentar o modelo

**Resumo:** 2 prompts no ChatGPT + 2 colagens no app. ~3 minutos, 1× por dia.
Tudo acontece dentro do app — **você não edita nenhum arquivo na mão.**

Antes de começar, abra o app:

```bash
streamlit run streamlit_app.py
```

---

## O que fazer toda manhã

### Passo 1 — Resultados de ontem (opcional, mas recomendado)

Serve para medir os acertos dos modelos. Pule se não quiser avaliação.

1. Copie o conteúdo de **`docs/prompt_b.txt`** e mande no ChatGPT.
2. Copie os objetos do array `"results"` que ele responder.
3. Cole-os no array `"results"` de **`data/results/actual_results.json`**
   (adicionando aos que já estão lá) e salve o arquivo no repositório.

→ Esse JSON é o **registro versionado** dos resultados reais — fica no Git e
pode ser reavaliado a qualquer momento. A página **History** lê na hora.

> Alternativa (sem editar arquivo): no app, página **History** →
> **"➕ Add actual results"** → cole → **Save results**. Grava no mesmo arquivo.

### Passo 2 — Contexto e previsões de hoje

1. Copie o conteúdo de **`docs/prompt_a.txt`** e mande no ChatGPT.
2. Copie o JSON que ele responder.
3. No app: página **Daily Context** → cole → **Validate** → **Save & generate predictions**.

→ Os jogos de hoje são cadastrados sozinhos e as previsões são geradas.

### Passo 3 — Ver os resultados

Vá para o **Dashboard**, escolha a data de hoje e veja os cards. Clique em
**🔍 Details** em qualquer jogo para o detalhamento completo (v1, v2, ensemble,
placares, distribuições).

---

## Resumo em uma tabela

| Quando | Prompt | Onde colocar a saída | Resultado |
|---|---|---|---|
| Manhã (opcional) | `prompt_b.txt` | `data/results/actual_results.json` (no repo) | Acertos de ontem atualizados |
| Manhã | `prompt_a.txt` | App → Daily Context → Save & generate | Previsões de hoje prontas |

---

## O que você **NÃO** precisa fazer

- ❌ Dizer a data ao ChatGPT — ele descobre "hoje" e "ontem" sozinho.
- ❌ Cadastrar os jogos do dia — o app cria a partir do contexto colado.
- ❌ Editar `matches.json` ou `teams.json` na mão (gerados automaticamente).
- ❌ Rodar scripts ou mexer em código.

O **único** arquivo que você edita à mão é `data/results/actual_results.json`
(os placares reais) — e mesmo esse tem a opção de colar pelo app.

---

## Observações úteis

- **"Dia" = das 06:00 às 06:00** (horário de Brasília), então jogos de madrugada
  entram na rodada certa. O ChatGPT já segue isso pelos prompts.
- O **arquivo de contexto** de cada dia é salvo em `data/context/AAAA-MM-DD.json`
  e preservado — é seu histórico/auditoria. Não precisa gerenciar nada.
- Se um dia faltar contexto, o app avisa e gera mesmo assim com hipóteses
  neutras (marcado como incompleto).
- Para **refazer** as previsões de um dia (ex.: corrigiu o contexto), use o botão
  **🔄 Regenerate** no Dashboard.
- Os prompts em si estão em [`docs/daily_context_prompt.md`](daily_context_prompt.md)
  (referência) e nos arquivos [`docs/prompt_a.txt`](prompt_a.txt) /
  [`docs/prompt_b.txt`](prompt_b.txt) (para copiar e colar).

> Lembrete: o WCPS é um simulador probabilístico recreativo, para análise e
> visualização. Não é aposta nem recomendação financeira.
