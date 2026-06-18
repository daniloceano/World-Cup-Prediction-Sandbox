# Materiais e Métodos — Modelo Agressivo de Previsão de Partidas

## 1. Contexto geral

Este documento complementa a seção metodológica dos modelos de previsão probabilística utilizados no WCPS — *World Cup Prediction Sandbox*. A partir da calibração inicial dos modelos anteriores, foram definidos três regimes de previsão:

| Nome operacional | Nome técnico | Descrição resumida |
|---|---|---|
| Modelo padrão | `model_standard` / antigo `model_v1` | Força relativa estática + Poisson + Monte Carlo |
| Modelo conservador | `model_conservative` / antigo `model_v2` | Modelo estratégico com valor do empate, bloco baixo, primeiro gol e risco de colapso |
| Modelo agressivo | `model_aggressive` / novo modelo | Modelo orientado à amplificação da superioridade técnica e à probabilidade de vitórias amplas dos favoritos |

O Modelo Agressivo foi proposto para representar cenários em que seleções tecnicamente superiores convertem sua vantagem em placares mais elásticos, especialmente quando há diferença relevante de elenco, poder ofensivo, intensidade física e capacidade de sustentar pressão após o primeiro gol. Esse modelo é particularmente útil para capturar situações como vitórias amplas de favoritos, por exemplo França, Argentina, Noruega, Alemanha ou Portugal contra adversários de menor capacidade defensiva ou menor profundidade competitiva.

Diferentemente do Modelo Conservador, que aumenta a probabilidade de empates e placares curtos quando o time mais fraco possui incentivo racional para se defender, o Modelo Agressivo considera que o plano defensivo do azarão pode falhar cedo. Nesses casos, o primeiro gol do favorito altera drasticamente o estado do jogo, aumenta os espaços disponíveis e desloca massa probabilística para placares como 2–0, 3–0, 3–1, 4–0 e 4–1.

## 2. Relação entre os três modelos

A estrutura geral dos três modelos pode ser resumida da seguinte forma:

\[
\text{Modelo Padrão} = \text{força relativa} + \text{Poisson} + \text{Monte Carlo}
\]

\[
\text{Modelo Conservador} = \text{Modelo Padrão} + \text{valor do empate} + \text{bloco baixo} + \text{estado do primeiro gol}
\]

\[
\text{Modelo Agressivo} = \text{Modelo Padrão} + \text{amplificação do favorito} + \text{pressão acumulada} + \text{cauda de goleada}
\]

Assim, os três modelos não devem ser interpretados como substitutos mutuamente excludentes, mas como regimes probabilísticos distintos. Eles representam hipóteses diferentes sobre o comportamento esperado da partida.

| Situação esperada | Modelo mais adequado |
|---|---|
| Jogo equilibrado, sem assimetria extrema | Modelo padrão |
| Azarão com alto incentivo para defender e capacidade de sustentar bloco baixo | Modelo conservador |
| Favorito com grande superioridade técnica e alta chance de transformar pressão em gols | Modelo agressivo |
| Favorito forte contra azarão com risco de colapso após sofrer o primeiro gol | Modelo agressivo |
| Estreia de Copa com favorito dominante, mas adversário muito organizado | Comparar conservador e agressivo |

## 3. Modelo padrão

O Modelo Padrão, anteriormente chamado de `model_v1`, utiliza uma estrutura estática de força relativa. Para cada partida, calcula-se um escore agregado de vantagem entre Time A e Time B com base em variáveis pré-jogo, como ranking, forma recente, elenco, desfalques, clima, contexto extracampo e similaridade tática.

A força relativa agregada é dada por:

\[
D = \sum_{i=1}^{n} \tilde{w}_i \left(S_{A,i} - S_{B,i}\right)
\]

em que:

- \(D\) é a diferença de força agregada;
- \(\tilde{w}_i\) é o peso normalizado da variável \(i\);
- \(S_{A,i}\) é o escore do Time A na variável \(i\);
- \(S_{B,i}\) é o escore do Time B na variável \(i\).

Os gols esperados são calculados por:

\[
\lambda_A = \lambda_0 + \alpha D
\]

\[
\lambda_B = \lambda_0 - \alpha D
\]

Os gols simulados seguem distribuições de Poisson independentes:

\[
G_A \sim Poisson(\lambda_A)
\]

\[
G_B \sim Poisson(\lambda_B)
\]

O modelo realiza \(N = 1000\) simulações Monte Carlo e calcula as probabilidades de vitória do Time A, empate e vitória do Time B por frequência relativa.

## 4. Modelo conservador

O Modelo Conservador, anteriormente chamado de `model_v2`, foi desenvolvido para reduzir o excesso de favoritismo observado no Modelo Padrão em partidas de estreia ou jogos assimétricos em que o time mais fraco possui alto incentivo para defender o empate.

A lógica central é:

\[
\text{Probabilidade de empate} \uparrow
\]

\[
\lambda_{\text{favorito}} \downarrow
\]

\[
P(0-0), P(1-1), P(1-0) \uparrow
\]

Esse modelo incorpora fatores como:

| Variável | Símbolo | Efeito esperado |
|---|---|---|
| Valor estratégico do empate | \(V_E\) | Aumenta probabilidade de empate |
| Capacidade de bloco baixo | \(B_D\) | Reduz gols esperados do favorito |
| Estado do primeiro gol | \(G_1\) | Altera o jogo após o primeiro gol |
| Risco de colapso | \(C_g\) | Controla a chance de goleada após gol sofrido |
| Ritmo esperado | \(F_{\text{ritmo}}\) | Ajusta intensidade da partida |

Os gols esperados ajustados são definidos por:

\[
\lambda_A^{*} = \lambda_A \cdot F_{\text{estreia}} \cdot F_{\text{bloco}} \cdot F_{\text{ritmo}}
\]

\[
\lambda_B^{*} = \lambda_B \cdot F_{\text{transição}} \cdot F_{\text{bola parada}}
\]

Esse modelo desloca probabilidade para placares de baixa pontuação, principalmente quando o empate é racionalmente positivo para o azarão.

## 5. Modelo agressivo

### 5.1 Objetivo

O Modelo Agressivo foi criado para representar cenários nos quais a superioridade do favorito tende a se traduzir em vitória ampla. Ele parte do Modelo Padrão, mas modifica a distribuição dos gols de forma a aumentar a probabilidade de placares elásticos quando determinadas condições são satisfeitas.

Seu objetivo não é simplesmente aumentar artificialmente os gols do favorito, mas representar um estado de jogo em que:

1. o favorito possui vantagem técnica clara;
2. o adversário tem dificuldade de sustentar bloco baixo por 90 minutos;
3. o primeiro gol do favorito tende a quebrar o plano defensivo;
4. o favorito mantém pressão mesmo após abrir vantagem;
5. o time mais fraco precisa se expor para buscar o resultado;
6. há diferença relevante de profundidade de elenco, intensidade e repertório ofensivo.

### 5.2 Hipótese central

A hipótese central do Modelo Agressivo é que, em jogos assimétricos, a distribuição de placares não é bem representada por um único processo de Poisson estático. Quando o favorito marca primeiro, a partida entra em um novo regime, com maior exposição do azarão e maior chance de sequência de gols.

Assim, o modelo assume uma mistura de estados:

\[
P(\text{placar}) =
P(S_0)P(\text{placar}|S_0) +
P(S_F)P(\text{placar}|S_F) +
P(S_C)P(\text{placar}|S_C)
\]

em que:

- \(S_0\) é o estado inicial, antes do primeiro gol;
- \(S_F\) é o estado em que o favorito marca primeiro e amplia pressão;
- \(S_C\) é o estado de colapso parcial ou total do azarão.

No Modelo Agressivo, aumenta-se o peso relativo de \(S_F\) e \(S_C\) quando o favorito possui superioridade clara.

## 6. Variáveis adicionais do Modelo Agressivo

O Modelo Agressivo introduz seis variáveis específicas.

| Variável | Símbolo | Descrição |
|---|---|---|
| Índice de superioridade ofensiva | \(A_F\) | Mede o poder ofensivo relativo do favorito |
| Fragilidade defensiva do azarão | \(D_U\) | Mede a probabilidade de o time inferior conceder múltiplas chances |
| Probabilidade de gol cedo | \(G_E\) | Mede a chance de o favorito marcar antes de o bloco baixo se estabilizar |
| Intensidade pós-gol | \(I_P\) | Mede a tendência do favorito de continuar atacando após abrir vantagem |
| Exposição do azarão após sofrer gol | \(E_U\) | Mede quanto o azarão precisa se abrir após sair atrás |
| Cauda de goleada | \(T_G\) | Aumenta a probabilidade de placares com margem de 3 ou mais gols |

### 6.1 Índice de superioridade ofensiva

O índice de superioridade ofensiva é calculado a partir de fatores como qualidade dos atacantes, criação de chances, forma recente ofensiva e diferença técnica entre os elencos.

\[
A_F = f(\text{ranking}, \text{forma ofensiva}, \text{elenco}, \text{similaridade tática})
\]

Na prática, \(A_F\) atua como um multiplicador sobre os gols esperados do favorito:

\[
\lambda_F^{aggr} = \lambda_F \cdot (1 + \beta A_F)
\]

em que \(\beta\) controla a intensidade da amplificação.

### 6.2 Fragilidade defensiva do azarão

A fragilidade defensiva do azarão representa a capacidade limitada de resistir à pressão contínua do favorito.

\[
D_U = f(\text{gols sofridos recentes}, \text{nível dos adversários enfrentados}, \text{experiência internacional}, \text{capacidade de recomposição})
\]

Quanto maior \(D_U\), maior a probabilidade de o favorito criar volume suficiente para placares amplos.

### 6.3 Probabilidade de gol cedo

A probabilidade de gol cedo é central no Modelo Agressivo. Um gol do favorito no início da partida aumenta substancialmente a chance de o jogo se abrir.

\[
G_E = P(G_1 = F \mid t < 35')
\]

em que \(G_1 = F\) representa o favorito marcando o primeiro gol, e \(t < 35'\) indica que esse gol ocorre antes dos 35 minutos.

Quando \(G_E\) é alto, o modelo desloca massa de probabilidade de placares como 1–0 e 1–1 para placares como 2–0, 3–0 e 3–1.

### 6.4 Intensidade pós-gol

Alguns favoritos administram o resultado após abrir o placar; outros continuam pressionando. O Modelo Agressivo aumenta a chance de goleada apenas quando o time favorito possui alta intensidade pós-gol.

\[
I_P = f(\text{perfil do treinador}, \text{necessidade de saldo}, \text{profundidade do elenco}, \text{estilo ofensivo})
\]

A intensidade pós-gol atua como multiplicador no segundo estado da partida:

\[
\lambda_F^{(1)} = \lambda_F^{aggr} \cdot F_{\text{pressão}}
\]

### 6.5 Exposição do azarão

Quando o azarão sofre o primeiro gol, pode precisar abandonar parte do plano defensivo. Isso aumenta simultaneamente sua chance de marcar e de sofrer novos gols.

\[
\lambda_U^{(1)} = \lambda_U \cdot F_{\text{risco}}
\]

\[
\lambda_F^{(1)} = \lambda_F^{aggr} \cdot F_{\text{espaços}}
\]

em que:

- \(F_{\text{risco}}\) aumenta a chance de o azarão marcar ao se expor;
- \(F_{\text{espaços}}\) aumenta a chance de o favorito marcar novos gols.

### 6.6 Cauda de goleada

A cauda de goleada é o mecanismo que diferencia o Modelo Agressivo do Modelo Padrão. Ela aumenta a probabilidade de placares com margem ampla quando há grande assimetria técnica e alto risco de colapso.

Define-se a margem de vitória do favorito por:

\[
M = G_F - G_U
\]

A cauda de goleada é ativada quando:

\[
M \geq 3
\]

O ajuste aplicado é:

\[
P(M \geq 3)^{aggr} = P(M \geq 3) \cdot (1 + \gamma T_G)
\]

em que \(\gamma\) é o parâmetro de intensidade da cauda e \(T_G\) representa o índice de goleada.

Após esse ajuste, as probabilidades são renormalizadas para que a soma total continue igual a 1.

## 7. Formulação dos gols esperados no Modelo Agressivo

O favorito recebe um ajuste positivo em seus gols esperados:

\[
\lambda_F^{aggr} =
\lambda_F \cdot
F_{\text{sup}} \cdot
F_{\text{pressão}} \cdot
F_{\text{colapso}}
\]

O azarão pode receber dois tipos diferentes de ajuste:

1. redução inicial, caso comece em bloco baixo;
2. aumento posterior, caso precise se expor após sofrer gol.

Estado inicial:

\[
\lambda_U^{(0)} = \lambda_U \cdot F_{\text{bloco}}
\]

Estado após gol do favorito:

\[
\lambda_U^{(1)} = \lambda_U \cdot F_{\text{risco}}
\]

Em geral:

\[
F_{\text{bloco}} < 1
\]

\[
F_{\text{risco}} > 1
\]

\[
F_{\text{sup}}, F_{\text{pressão}}, F_{\text{colapso}} > 1
\]

## 8. Exemplo conceitual

Considere uma partida em que o Modelo Padrão calcula:

\[
\lambda_F = 1{,}80
\]

\[
\lambda_U = 0{,}80
\]

No Modelo Conservador, caso o azarão tenha alto valor estratégico no empate, poderíamos ter:

\[
\lambda_F^{cons} = 1{,}55
\]

\[
\lambda_U^{cons} = 0{,}70
\]

No Modelo Agressivo, caso o favorito tenha alta chance de marcar cedo e o azarão tenha risco de colapso, poderíamos ter:

\[
\lambda_F^{aggr} = 2{,}25
\]

\[
\lambda_U^{aggr} = 0{,}90
\]

A diferença aparece na distribuição de placares.

| Placar | Tendência no conservador | Tendência no padrão | Tendência no agressivo |
|---|---:|---:|---:|
| 0–0 | Alta | Média | Baixa |
| 1–0 | Alta | Alta | Média |
| 1–1 | Alta | Média | Média |
| 2–0 | Média | Alta | Alta |
| 3–0 | Baixa | Média | Alta |
| 3–1 | Baixa | Média | Alta |
| 4–0 | Muito baixa | Baixa | Média/alta |

## 9. Critérios para ativação do Modelo Agressivo

O Modelo Agressivo não deve ser aplicado indiscriminadamente. Ele é indicado quando pelo menos quatro das seguintes condições forem satisfeitas:

| Critério | Interpretação |
|---|---|
| Grande diferença técnica | Favorito possui vantagem clara de elenco e ranking |
| Ataque em boa fase | Favorito vem marcando com frequência |
| Adversário defensivamente vulnerável | Azarão sofre muitas chances ou tem baixa experiência |
| Risco de gol cedo | Favorito costuma começar pressionando |
| Necessidade de saldo | Favorito pode buscar vitória ampla por critério de grupo |
| Banco forte | Favorito mantém intensidade com substituições |
| Fragilidade emocional/tática | Azarão pode se desorganizar após sofrer gol |
| Histórico de dificuldade contra pressão alta | Azarão tem problemas na saída de bola |

Se menos de quatro critérios forem satisfeitos, recomenda-se usar o Modelo Padrão ou o Modelo Conservador.

## 10. Saídas do Modelo Agressivo

Assim como os demais modelos, o Modelo Agressivo retorna:

1. probabilidade de vitória do Time A;
2. probabilidade de empate;
3. probabilidade de vitória do Time B;
4. gols esperados ajustados;
5. placar modal geral;
6. top 5 placares gerais;
7. top 5 placares dentro do outcome mais provável;
8. placar recomendado;
9. probabilidade de vitória ampla;
10. índice de cauda de goleada.

Define-se vitória ampla como:

\[
M \geq 2
\]

e goleada como:

\[
M \geq 3
\]

Assim, o modelo também pode reportar:

\[
P(M \geq 2)
\]

\[
P(M \geq 3)
\]

Essas métricas são úteis para diferenciar uma previsão de vitória simples de uma previsão de domínio amplo.

## 11. Interpretação das previsões

O Modelo Agressivo deve ser interpretado como um cenário de máxima conversão da superioridade do favorito. Ele não substitui o Modelo Conservador, mas complementa a análise ao responder à seguinte pergunta:

> Se o favorito conseguir impor seu plano, marcar primeiro e manter pressão, qual é a distribuição de placares mais provável?

Essa interpretação é especialmente relevante em partidas nas quais a diferença técnica é grande e o time mais fraco pode ser forçado a abandonar seu plano defensivo cedo.

## 12. Comparação entre os regimes

| Elemento | Modelo conservador | Modelo padrão | Modelo agressivo |
|---|---:|---:|---:|
| Probabilidade de empate | Maior | Média | Menor |
| Gols esperados do favorito | Reduzidos | Neutros | Amplificados |
| Chance de 0–0 / 1–1 | Alta | Média | Baixa/média |
| Chance de 2–0 | Média | Alta | Alta |
| Chance de 3–0 / 3–1 | Baixa | Média | Alta |
| Sensibilidade ao primeiro gol | Alta | Baixa | Muito alta |
| Risco de goleada | Controlado | Moderado | Ampliado |
| Uso ideal | Jogos travados | Cenário médio | Favoritos dominantes |

## 13. Protocolo recomendado para o WCPS

Para cada partida, recomenda-se gerar três previsões paralelas:

1. `model_conservative`;
2. `model_standard`;
3. `model_aggressive`.

Em seguida, a ferramenta pode comparar os três cenários.

### 13.1 Estrutura sugerida de decisão

| Situação | Modelo priorizado |
|---|---|
| Todos os modelos apontam o mesmo vencedor | Alta confiança no outcome |
| Conservador aponta empate, padrão e agressivo apontam favorito | Favorito provável, mas com risco de jogo travado |
| Padrão aponta vitória curta e agressivo aponta goleada | Favorito deve vencer; amplitude depende do primeiro gol |
| Conservador e padrão apontam empate, agressivo aponta favorito | Jogo depende fortemente de gol cedo |
| Modelos divergem entre três outcomes | Alta incerteza |

### 13.2 Escolha do placar final

O placar final recomendado pode seguir três níveis:

| Tipo de previsão | Critério |
|---|---|
| Placar conservador | Usar quando o empate tem alto valor estratégico |
| Placar padrão | Usar como previsão central |
| Placar agressivo | Usar quando há forte chance de colapso do azarão |

## 14. Limitações

O Modelo Agressivo aumenta a capacidade de representar vitórias amplas, mas também eleva o risco de superestimar favoritos. Ele deve ser usado com cautela em partidas nas quais o time mais fraco possui:

- defesa bem organizada;
- goleiro de alto desempenho;
- boa capacidade física;
- experiência em torneios;
- baixo incentivo para se expor;
- capacidade de retardar o jogo;
- ameaça real em transições.

Além disso, como os parâmetros ainda são heurísticos, o modelo deve ser recalibrado continuamente a partir dos resultados observados.

## 15. Conclusão

O Modelo Agressivo adiciona ao WCPS um terceiro regime interpretativo. Enquanto o Modelo Conservador responde ao cenário “e se o azarão conseguir travar o jogo?”, o Modelo Agressivo responde ao cenário oposto: “e se o favorito marcar cedo e transformar superioridade em goleada?”.

A combinação dos três modelos permite uma leitura mais rica da partida:

\[
\text{Previsão robusta} =
\text{conservador} +
\text{padrão} +
\text{agressivo}
\]

Esse sistema permite avaliar não apenas o outcome mais provável, mas também a sensibilidade do jogo ao primeiro gol, ao valor estratégico do empate e à capacidade do favorito de sustentar pressão ofensiva.
