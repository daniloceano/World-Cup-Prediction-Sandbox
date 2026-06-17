# Materiais e Métodos

## Modelagem probabilística de resultados de partidas de futebol

Neste estudo, foram avaliadas duas versões de um modelo probabilístico semiempírico para previsão de resultados de partidas de futebol. Ambas as abordagens combinam informações contextuais pré-jogo, ponderação multicritério e simulação Monte Carlo para estimar as probabilidades de vitória do Time A, empate e vitória do Time B, bem como a distribuição dos placares mais prováveis.

O Modelo v1 foi formulado como uma abordagem de força relativa estática, na qual a diferença entre os times é convertida diretamente em gols esperados e simulada por distribuições de Poisson independentes. O Modelo v2 mantém a base probabilística do v1, mas adiciona uma camada estratégica condicionada ao plano de jogo esperado, ao valor do empate, ao estado do primeiro gol e ao risco de colapso após sofrer um gol. Essa segunda versão foi proposta para lidar melhor com jogos de Copa do Mundo, especialmente partidas de estreia e confrontos assimétricos entre favoritos e seleções que tendem a adotar bloco baixo.

## 1. Dados de entrada

Para cada partida, foram levantadas informações pré-jogo referentes aos dois times avaliados. As variáveis de entrada foram agrupadas em sete dimensões principais no Modelo v1 e posteriormente expandidas no Modelo v2.

### 1.1 Variáveis consideradas no Modelo v1

| Variável | Descrição | Peso bruto |
|---|---|---:|
| Ranking FIFA | Posição relativa das seleções no ranking FIFA mais recente | 1,5 |
| Forma recente curta | Desempenho nos últimos 5 jogos | 2,5 |
| Forma recente longa | Desempenho nos últimos 15 jogos | 1,0 |
| Lesões e desfalques | Disponibilidade de jogadores-chave, suspensões e limitações físicas | 1,5 |
| Clima e adaptação | Condições meteorológicas esperadas e adaptação relativa dos times | 1,0 |
| Fatores extracampo | Ruídos públicos, questões disciplinares, instabilidade institucional ou emocional | 1,0 |
| Similaridade tática | Desempenho recente contra adversários de perfil tático semelhante | 2,5 |

Os pesos foram definidos de forma heurística, com maior importância atribuída à forma recente curta e à similaridade tática, por serem considerados indicadores mais diretamente relacionados ao estado competitivo atual de cada seleção.

A normalização dos pesos foi dada por:

\[
\tilde{w}_i = \frac{w_i}{\sum_{i=1}^{n} w_i}
\]

em que \(w_i\) representa o peso bruto da variável \(i\), \(\tilde{w}_i\) é o peso normalizado e \(n\) é o número total de variáveis.

## 2. Modelo v1: força relativa estática + Poisson + Monte Carlo

### 2.1 Escore relativo dos times

Para cada variável \(i\), atribuiu-se um escore qualitativo relativo para os dois times. Os escores foram convertidos para uma escala padronizada, variando de vantagem clara para o Time A até vantagem clara para o Time B.

| Escore | Interpretação |
|---:|---|
| +1,0 | Vantagem forte do Time A |
| +0,5 | Vantagem moderada do Time A |
| 0,0 | Equilíbrio |
| -0,5 | Vantagem moderada do Time B |
| -1,0 | Vantagem forte do Time B |

A diferença ponderada de força entre os times foi calculada por:

\[
D = \sum_{i=1}^{n} \tilde{w}_i \left(S_{A,i} - S_{B,i}\right)
\]

em que \(D\) representa a força relativa agregada, \(S_{A,i}\) é o escore do Time A na variável \(i\), e \(S_{B,i}\) é o escore do Time B na mesma variável.

Valores positivos de \(D\) indicam vantagem agregada do Time A, enquanto valores negativos indicam vantagem agregada do Time B.

### 2.2 Conversão da força relativa em gols esperados

A força relativa foi convertida em gols esperados por meio de uma função linear simplificada:

\[
\lambda_A = \lambda_0 + \alpha D
\]

\[
\lambda_B = \lambda_0 - \alpha D
\]

em que \(\lambda_A\) e \(\lambda_B\) representam os gols esperados dos times A e B, respectivamente; \(\lambda_0\) é a taxa média basal de gols por equipe; e \(\alpha\) é um parâmetro de sensibilidade que controla o quanto a diferença de força altera os gols esperados.

Na implementação prática, os valores de \(\lambda\) foram ajustados para evitar taxas negativas ou excessivamente altas, preservando uma faixa realista para partidas de futebol internacional.

### 2.3 Simulação dos gols

Os gols de cada equipe foram simulados como variáveis aleatórias de Poisson independentes:

\[
G_A \sim Poisson(\lambda_A)
\]

\[
G_B \sim Poisson(\lambda_B)
\]

em que \(G_A\) e \(G_B\) representam, respectivamente, o número de gols marcados pelo Time A e pelo Time B.

A escolha da distribuição de Poisson segue uma tradição consolidada em modelos estatísticos de futebol, nos quais gols são tratados como eventos discretos de contagem. Modelos clássicos de previsão de placares, como os de Maher (1982) e Dixon e Coles (1997), também partem dessa estrutura, com extensões para dependência entre placares baixos e outros ajustes contextuais.

### 2.4 Simulação Monte Carlo

Para cada partida, foram realizadas \(N = 1000\) simulações independentes. Em cada simulação, foram sorteados os gols de ambos os times e classificado o resultado em uma das seguintes categorias:

\[
O_j \in \{\text{vitória do Time A}, \text{empate}, \text{vitória do Time B}\}
\]

As probabilidades dos outcomes foram estimadas pela frequência relativa:

\[
P(O_j) = \frac{n_j}{N}
\]

em que \(n_j\) é o número de simulações em que o outcome \(j\) ocorreu.

As probabilidades dos placares específicos foram estimadas por:

\[
P(G_A = x, G_B = y) = \frac{n_{x,y}}{N}
\]

em que \(n_{x,y}\) é o número de simulações nas quais o placar final foi \(x-y\).

### 2.5 Produtos do Modelo v1

Para cada partida, o Modelo v1 gerou:

1. Probabilidade de vitória do Time A;
2. Probabilidade de empate;
3. Probabilidade de vitória do Time B;
4. Placar modal geral;
5. Top 5 placares dentro do outcome mais provável;
6. Top 5 placares gerais, independentemente do outcome;
7. Placar final recomendado, definido por combinação entre outcome mais provável, placar modal e interpretação contextual.

## 3. Diagnóstico de limitação do Modelo v1

Após as primeiras rodadas simuladas, observou-se que o Modelo v1 apresentava tendência a superestimar favoritos, especialmente em jogos de estreia de fase de grupos. Esse comportamento ocorreu porque a força relativa era convertida diretamente em gols esperados, sem representar explicitamente o plano estratégico de equipes mais fracas.

Em jogos de Copa do Mundo, um empate contra o principal favorito do grupo pode representar um resultado altamente positivo para uma seleção considerada azarã. Nesses casos, o time inferior tende a adotar postura conservadora, bloco baixo, redução de ritmo e menor exposição ofensiva. O Modelo v1 não diferenciava adequadamente as seguintes situações:

- favorito dominando territorialmente, mas enfrentando bloco baixo;
- azarão sustentando 0–0 até fases avançadas do jogo;
- favorito marcando cedo e gerando colapso tático do adversário;
- jogo permanecendo empatado por tempo suficiente para aumentar o valor estratégico do empate.

Assim, a principal limitação do Modelo v1 foi tratar a partida como um processo estático, com intensidades de gols constantes durante todo o jogo.

## 4. Modelo v2: ajuste estratégico por estados do jogo

O Modelo v2 foi desenvolvido para incorporar uma camada estratégica à formulação original. A premissa central é que a intensidade ofensiva de cada time não depende apenas da sua força técnica, mas também do estado do jogo e do valor estratégico de cada resultado.

A estrutura conceitual do Modelo v2 pode ser resumida por:

\[
\text{Modelo v2} = \text{força relativa} + \text{valor estratégico do empate} + \text{plano provável} + \text{primeiro gol} + \text{risco de colapso}
\]

### 4.1 Novas variáveis estratégicas

Foram adicionadas cinco variáveis estratégicas ao modelo.

| Variável | Símbolo | Descrição |
|---|---|---|
| Valor estratégico do empate | \(V_E\) | Mede o quão positivo é o empate para o time mais fraco |
| Capacidade de sustentar bloco baixo | \(B_D\) | Representa a capacidade defensiva do azarão em manter jogo de baixa pontuação |
| Necessidade de vitória | \(N_V\) | Mede se algum time precisa se expor desde o início |
| Probabilidade de primeiro gol | \(P(G_1)\) | Estima qual equipe é mais provável de marcar primeiro, ou se o 0–0 tende a persistir |
| Risco de colapso pós-gol | \(C_g\) | Mede a chance de o time inferior se desorganizar após sofrer o primeiro gol |

### 4.2 Valor estratégico do empate

O valor estratégico do empate foi definido como um multiplicador aplicado à massa de probabilidade de empates, especialmente para placares 0–0 e 1–1.

\[
P(\text{empate})^{*} = P(\text{empate}) + \Delta_E
\]

em que:

\[
\Delta_E = f(V_E, B_D, \text{fase do torneio}, \text{força relativa})
\]

Na aplicação prática, \(\Delta_E\) variou entre 0,04 e 0,10 para partidas em que o empate possuía alto valor estratégico para o time mais fraco.

| Situação | Ajuste típico |
|---|---:|
| Empate pouco relevante | 0,00 a 0,03 |
| Empate moderadamente positivo | 0,04 a 0,06 |
| Empate altamente positivo | 0,07 a 0,10 |

### 4.3 Plano provável do azarão

Para jogos assimétricos, foi introduzido um fator de redução da conversão ofensiva do favorito quando o adversário tem incentivo e capacidade para defender em bloco baixo:

\[
\lambda_A^{(0)} = \lambda_A \cdot F_{\text{bloco}}
\]

em que \(F_{\text{bloco}}\) representa o fator de compressão defensiva imposto pelo time mais fraco.

| Perfil defensivo do azarão | \(F_{\text{bloco}}\) |
|---|---:|
| Bloco baixo forte e disciplinado | 0,70–0,85 |
| Bloco médio/defesa razoável | 0,85–0,95 |
| Defesa frágil ou jogo aberto | 0,95–1,10 |

Esse ajuste reduz a tendência do modelo de transformar superioridade técnica em goleadas automáticas.

### 4.4 Probabilidade do primeiro gol

O Modelo v2 divide a partida em dois momentos: estado inicial e estado condicionado ao primeiro gol. Define-se:

\[
P(G_1 = A), \quad P(G_1 = B), \quad P(G_1 = \varnothing)
\]

em que:

- \(P(G_1 = A)\) é a probabilidade de o Time A marcar primeiro;
- \(P(G_1 = B)\) é a probabilidade de o Time B marcar primeiro;
- \(P(G_1 = \varnothing)\) representa a probabilidade de nenhum gol ocorrer até uma fase avançada do jogo.

Essa etapa permite representar jogos em que o 0–0 prolongado aumenta a chance de empate, enquanto um gol cedo do favorito aumenta a probabilidade de placares elásticos.

### 4.5 Estado pós-primeiro gol

Quando o favorito marca primeiro, considera-se que o time inferior tende a abandonar parte do bloco baixo e se expor mais. Nesse caso, os gols esperados do favorito são reajustados por um fator de espaço:

\[
\lambda_A^{(1)} = \lambda_A \cdot F_{\text{espaços}}
\]

e os gols esperados do azarão são ajustados por um fator de risco ofensivo:

\[
\lambda_B^{(1)} = \lambda_B \cdot F_{\text{risco}}
\]

em que:

| Situação | Efeito |
|---|---|
| Favorito marca cedo | Aumenta chance de 2–0, 3–0 ou goleada |
| Azarão segura até o intervalo | Aumenta chance de 0–0, 1–0 ou 1–1 |
| Azarão marca primeiro | Aumenta pressão do favorito e chance de jogo caótico |
| Empate persiste até o fim | Reduz incentivo ao risco, dependendo do valor do ponto |

### 4.6 Risco de colapso pós-gol

O risco de colapso pós-gol foi introduzido para diferenciar seleções capazes de sustentar um plano defensivo mesmo após sofrerem o primeiro gol daquelas que tendem a se desorganizar.

\[
C_g = f(\text{experiência}, \text{qualidade defensiva}, \text{maturidade competitiva}, \text{assimetria técnica})
\]

Valores altos de \(C_g\) aumentam a probabilidade de placares amplos após o primeiro gol do favorito.

| Perfil | \(C_g\) |
|---|---:|
| Defesa experiente e resiliente | baixo |
| Defesa organizada, mas limitada | médio |
| Estreante ou time emocionalmente instável | alto |

### 4.7 Formulação ajustada dos gols esperados

No Modelo v2, os gols esperados iniciais são calculados por:

\[
\lambda_A^{*} = \lambda_A \cdot F_{\text{estreia}} \cdot F_{\text{bloco}} \cdot F_{\text{ritmo}}
\]

\[
\lambda_B^{*} = \lambda_B \cdot F_{\text{transição}} \cdot F_{\text{bola parada}}
\]

em que:

- \(F_{\text{estreia}}\) reduz a agressividade ofensiva em estreias de fase de grupos;
- \(F_{\text{bloco}}\) representa a resistência defensiva do time mais fraco;
- \(F_{\text{ritmo}}\) incorpora clima, viagem, desgaste e ritmo esperado;
- \(F_{\text{transição}}\) ajusta a capacidade do time mais fraco de gerar perigo em contra-ataques;
- \(F_{\text{bola parada}}\) incorpora ameaça em escanteios, faltas laterais e bolas aéreas.

A simulação final combina as probabilidades do estado inicial e do estado pós-primeiro gol. De forma simplificada:

\[
P(\text{placar}) =
P(S_0)P(\text{placar}|S_0) +
P(S_A)P(\text{placar}|S_A) +
P(S_B)P(\text{placar}|S_B)
\]

em que:

- \(S_0\) é o estado de jogo sem gol precoce;
- \(S_A\) é o estado condicionado ao Time A marcar primeiro;
- \(S_B\) é o estado condicionado ao Time B marcar primeiro.

## 5. Algoritmo de simulação

O procedimento aplicado em cada partida pode ser descrito pelas seguintes etapas:

1. Coletar informações pré-jogo;
2. Atribuir escores relativos para cada variável do Modelo v1;
3. Calcular a força relativa ponderada \(D\);
4. Converter \(D\) em gols esperados iniciais \(\lambda_A\) e \(\lambda_B\);
5. Identificar contexto estratégico da partida;
6. Calcular modificadores do Modelo v2;
7. Ajustar \(\lambda_A\) e \(\lambda_B\) para o estado inicial;
8. Simular 1000 partidas por Monte Carlo;
9. Reponderar placares conforme valor estratégico do empate e estados de primeiro gol;
10. Estimar probabilidades de outcomes e placares;
11. Reportar:
    - probabilidade de vitória do Time A;
    - probabilidade de empate;
    - probabilidade de vitória do Time B;
    - top 5 placares dentro do outcome mais provável;
    - top 5 placares gerais;
    - placar modal;
    - placar recomendado.

## 6. Critério de escolha do placar recomendado

O placar recomendado não foi definido automaticamente como o placar modal em todos os casos. A decisão final combinou três elementos:

1. outcome mais provável;
2. placar modal geral;
3. coerência estratégica do jogo.

Assim, quando o outcome mais provável era vitória de um favorito, mas o placar modal geral era empate, a recomendação final podia assumir uma postura conservadora, por exemplo, selecionando 1–0 em vez de 2–0 ou 3–0.

Esse critério foi adotado porque a distribuição de placares em futebol é frequentemente concentrada em resultados de baixa pontuação, e a soma das probabilidades de vários placares de vitória pode tornar a vitória o outcome mais provável, mesmo que o placar individual mais provável seja um empate.

## 7. Avaliação e recalibração

A avaliação do modelo foi realizada por comparação entre as previsões e os resultados observados. Foram considerados três níveis de acerto:

| Nível | Descrição |
|---|---|
| Acerto de outcome | Vitória, empate ou derrota corretamente previstos |
| Acerto de placar modal | Placar real coincide com o placar individual mais provável |
| Acerto de faixa estratégica | O jogo ocorre dentro do cenário esperado, mesmo sem acerto exato do placar |

A recalibração do Modelo v2 foi motivada pela observação de que o Modelo v1 superestimava favoritos em jogos de estreia e subestimava a probabilidade de empate. Em especial, resultados como 0–0 e 1–1 passaram a receber maior peso quando o time inferior tinha incentivo racional para defender o empate.

## 8. Limitações

Os modelos propostos possuem caráter semiempírico e dependem de avaliação qualitativa de variáveis contextuais. Apesar de usarem formulação probabilística e simulação Monte Carlo, os pesos e modificadores estratégicos não foram estimados por ajuste estatístico formal em uma base histórica ampla.

As principais limitações são:

- dependência de julgamento especialista para atribuição de escores;
- ausência de ajuste automático dos parâmetros por máxima verossimilhança;
- uso simplificado de distribuições de Poisson;
- independência parcial entre gols dos times no Modelo v1;
- dificuldade de incorporar eventos raros, como expulsões, falhas individuais e lesões durante o jogo;
- sensibilidade a informações pré-jogo incompletas ou imprecisas.

Apesar dessas limitações, o Modelo v2 fornece uma estrutura mais realista para partidas de torneios internacionais, pois incorpora explicitamente o comportamento estratégico esperado das equipes.

## 9. Referências metodológicas

DIXON, M. J.; COLES, S. G. Modelling association football scores and inefficiencies in the football betting market. *Journal of the Royal Statistical Society: Series C (Applied Statistics)*, v. 46, n. 2, p. 265–280, 1997.

MAHER, M. J. Modelling association football scores. *Statistica Neerlandica*, v. 36, n. 3, p. 109–118, 1982.

GILCH, L. A. Nested zero inflated generalized Poisson regression for FIFA World Cup 2022. *arXiv preprint*, 2022.

MAIA, L. F. G. N.; PENNANEN, T.; DA SILVA, M. A. H. B.; TARGINO, R. S. Stochastic modelling of football matches. *arXiv preprint*, 2023.

LAHVICKA, J. Using Monte Carlo simulation to calculate match importance. *Munich Personal RePEc Archive*, 2012.
