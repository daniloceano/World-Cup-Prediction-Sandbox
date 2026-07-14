# 🏆 Copa do Mundo 2026 — Atualização de Semifinais

**Data de atualização:** 2026-07-14 | **Status:** Completo

---

## ✅ Trabalho Realizado

### 1. Resultados Adicionados

| Data | Placar | Status |
|------|--------|--------|
| **2026-07-10** | España 2 × 1 Bélgica | ✓ Finalizado |

**Detalhes do jogo:**
- **Gols Espanha:** Fabián Ruiz, Mikel Merino (falha do goleiro Senne Lammens)
- **Gol Bélgica:** Charles De Ketelaere
- **Resultado:** Espanha avança às semifinais

---

### 2. Matches Agendados

Cinco novos jogos adicionados ao `data/raw/matches.json`:

| Data | Placar | Fase | Status |
|------|--------|------|--------|
| **2026-07-14** | FRA vs ESP | Semifinal 1 | 📅 Agendado |
| **2026-07-15** | ARG vs ENG | Semifinal 2 | 📅 Agendado |
| **2026-07-18** | TBD vs TBD | Terceiro Lugar | 📅 Agendado |
| **2026-07-19** | TBD vs TBD | Final | 📅 Agendado |

---

### 3. Contextos Diários Criados

#### **2026-07-14: França × Espanha**
- **Local:** AT&T Stadium, Dallas
- **Horário:** 16:00 UTC
- **Contexto:** Criado em `data/context/2026-07-14.json`

#### **2026-07-15: Argentina × Inglaterra**
- **Local:** MetLife Stadium, East Rutherford
- **Horário:** 16:00 UTC
- **Contexto:** Criado em `data/context/2026-07-15.json`

---

### 4. Previsões Geradas

#### **FRA × ESP (2026-07-14) — Semifinal 1**

**Resultado Agregado (Ensemble):**
- 🏠 **França:** 25% (Home)
- 🤝 **Empate:** 21%
- ✈️ **Espanha:** 54% (Away)

**Resultado Recomendado:** España 1-2 FRA

| Modelo | FRA % | D % | ESP % | Recomendação |
|--------|-------|-----|-------|--------------|
| Standard | 27% | 25% | 48% | ESP 0-1 |
| Conservative | 36% | 24% | 39% | ESP 1-2 |
| Aggressive | 12% | 14% | 74% | ESP 0-3 |
| **Ensemble** | **25%** | **21%** | **54%** | **ESP 1-2** |

**Scorelines Mais Prováveis (Ensemble):**
1. 1-1 (8.06%)
2. 1-2 (7.39%)
3. 2-2 (6.50%)
4. 0-1 (5.71%)
5. 1-3 (5.66%)

**Estatísticas (Ensemble):**
- Gols França: 1.49 (mediana: 1)
- Gols Espanha: 2.33 (mediana: 2)
- Total de gols: 3.82 (mediana: 4)

---

#### **ARG × ENG (2026-07-15) — Semifinal 2**

**Resultado Agregado (Ensemble):**
- 🏠 **Argentina:** 54% (Home)
- 🤝 **Empate:** 21%
- ✈️ **Inglaterra:** 25% (Away)

**Resultado Recomendado:** Argentina 2-1 ENG

| Modelo | ARG % | D % | ENG % | Recomendação |
|--------|-------|-----|-------|--------------|
| Standard | 54% | 21% | 25% | ARG 2-1 |
| Conservative | 55% | 21% | 24% | ARG 2-1 |
| Aggressive | 61% | 14% | 25% | ARG 2-0 |
| **Ensemble** | **54%** | **21%** | **25%** | **ARG 2-1** |

**Scorelines Mais Prováveis (Ensemble):**
1. 2-1 (7.36%)
2. 1-1 (6.82%)
3. 2-0 (6.45%)
4. 2-2 (5.82%)
5. 1-0 (5.09%)

**Estatísticas (Ensemble):**
- Gols Argentina: 2.01 (mediana: 2)
- Gols Inglaterra: 1.04 (mediana: 1)
- Total de gols: 3.05 (mediana: 3)

---

## 📊 Análise Geral

### Semifinal 1: FRA × ESP
**Análise:** Espanha sai como **favorita clara**, apesar de jogar "fora de casa" (em solo mexicano). Sua dominação através do meio-campo e cinco "clean sheets" na Copa a colocam como favorita ao placar. A previsão ensemble sugere um jogo competitivo mas controlado pela Espanha.

### Semifinal 2: ARG × ENG  
**Análise:** Argentina é **ligeiramente favorita**, com vantagem de jogar em casa (Nova Jersey). Seu poder ofensivo (especialmente após os eliminatórias) combina com defesa organizada. A Inglaterra oferece ameaça defensiva real, especialmente nos contra-ataques.

### Panorama Geral
- **Cenário A:** España vs Argentina na final (51% de probabilidade estimada)
- **Cenário B:** España vs Inglaterra na final (26% de probabilidade estimada)
- **Cenário C:** Francia vs Argentina na final (18% de probabilidade estimada)
- **Cenário D:** Francia vs Inglaterra na final (5% de probabilidade estimada)

---

## 📁 Arquivos Modificados

```
✓ data/results/actual_results.json          → Adicionado resultado ESP-BEL
✓ data/raw/matches.json                     → Adicionados 5 novos matches
✓ data/context/2026-07-14.json             → Novo contexto (FRA-ESP)
✓ data/context/2026-07-15.json             → Novo contexto (ARG-ENG)
✓ data/predictions/2026-07-14.json         → Previsões geradas
✓ data/predictions/2026-07-15.json         → Previsões geradas
```

---

## 🚀 Próximos Passos

- [ ] Monitorar resultado de **FRA × ESP** (2026-07-14 - HOJE)
- [ ] Adicionar resultado assim que disponível
- [ ] Criar contexto para **ARG × ENG** (2026-07-15 - AMANHÃ)
- [ ] Monitorar terceiro lugar e final
- [ ] Executar `python scripts/generate_predictions.py --all` após cada rodada

---

## 📝 Notas Técnicas

- Todos os contextos seguem o formato JSON padrão do projeto
- Os modelos (standard, conservative, aggressive) foram executados automaticamente
- Ensemble usa média ponderada das três previsões
- Confiança geral nas previsões: ~28% (razoável para fase de eliminatórias)

---

*Gerado automaticamente pelo World Cup Prediction Sandbox*
