# Plugin QGIS para Estimativa Espacial de Evapotranspiração com RNA

Este projeto implementa uma ferramenta em Python/PyQt5 para coleta de dados geoespaciais via Google Earth Engine e execução de um modelo de Rede Neural Artificial (RNA) para estimar evapotranspiração anual (`ET`) em formato raster GeoTIFF.

O fluxo principal do projeto é:

1. O usuário seleciona uma área de interesse em formato Shapefile.
2. O sistema coleta dados MapBiomas e Landsat pelo Google Earth Engine.
3. Os dados são organizados por ano.
4. O modelo RNA é executado pixel a pixel.
5. O resultado final é salvo como raster GeoTIFF recortado pela área de interesse.

---

## 1. Objetivo do projeto

O objetivo é gerar um mapa espacial de evapotranspiração anual estimada por modelo de aprendizado de máquina.

A saída do modelo é:

```text
ET anual estimada em mm/ano
```

Cada pixel do raster final representa uma estimativa de evapotranspiração anual naquele ponto da área analisada.

Exemplo de interpretação:

```text
Valor do pixel = 850
```

significa aproximadamente:

```text
ET anual estimada naquele pixel = 850 mm/ano
```

---

## 2. Estrutura do projeto

A estrutura da pasta principal é:

```text
real/
├── test_app.py
├── main_dialog.py
├── coleta_gee.py
├── executar_modelo.py
├── plugin.py
│
├── ui/
│   ├── ui_rna_mpl.py
│   └── rna_mpl.ui
│
└── modelo/
    ├── modelo_etp.h5
    ├── scaler_X.pkl
    ├── scaler_y.pkl
    └── feature_columns.json
```

### Função de cada arquivo

| Arquivo | Função |
|---|---|
| `test_app.py` | Executa a interface fora do QGIS para testes locais. |
| `main_dialog.py` | Controla a interface gráfica, botões, abas, logs e chamadas principais. |
| `coleta_gee.py` | Faz a coleta de MapBiomas e Landsat via Google Earth Engine. |
| `executar_modelo.py` | Carrega o modelo RNA, prepara as features, executa a predição e salva o raster. |
| `plugin.py` | Arquivo de integração para rodar como plugin dentro do QGIS. |
| `ui/ui_rna_mpl.py` | Interface convertida do Qt Designer para Python. |
| `ui/rna_mpl.ui` | Arquivo original da interface no Qt Designer. |
| `modelo/modelo_etp.h5` | Modelo treinado da RNA. |
| `modelo/scaler_X.pkl` | Normalizador das entradas usado no treinamento. |
| `modelo/scaler_y.pkl` | Normalizador da saída `ET` usado no treinamento. |
| `modelo/feature_columns.json` | Lista das variáveis na ordem exata usada pelo modelo. |

---

## 3. Dependências

### 3.1. Instalação recomendada com Conda

No Windows, a forma mais segura é usar Conda para bibliotecas geoespaciais:

```bash
conda create -n rna_qgis python=3.11 -y
conda activate rna_qgis

conda install -c conda-forge geopandas rasterio shapely pyproj fiona gdal numpy pandas -y

pip install earthengine-api geemap PyQt5 tensorflow scikit-learn joblib
```

### 3.2. Instalação apenas com pip

Caso prefira tentar somente com pip:

```bash
pip install numpy pandas geopandas shapely rasterio earthengine-api geemap PyQt5 tensorflow scikit-learn joblib
```

Se ocorrer erro com `geopandas`, `rasterio`, `fiona`, `pyproj` ou `gdal`, use a instalação com Conda.

### 3.3. Teste das dependências

Após instalar, rode:

```bash
python -c "import ee, geemap, geopandas, rasterio, tensorflow, sklearn, joblib, PyQt5; print('Tudo OK')"
```

---

## 4. Autenticação no Google Earth Engine

O projeto usa o Google Earth Engine para baixar dados Landsat e MapBiomas.

O código inicializa o Earth Engine com:

```python
ee.Initialize(project="qgis-493503")
```

Se ainda não estiver autenticado, o sistema chamará:

```python
ee.Authenticate()
```

### Problemas comuns

#### Earth Engine não autenticado

Rode:

```bash
earthengine authenticate
```

#### Projeto sem permissão

Verifique se o projeto usado no código está registrado e autorizado para Earth Engine.

#### Conta errada

Caso tenha autenticado com o e-mail errado:

```bash
earthengine authenticate --revoke
earthengine authenticate
```

---

## 5. Como executar fora do QGIS

Para testar a interface como aplicação PyQt5, o arquivo `test_app.py` deve conter:

```python
import sys
from PyQt5.QtWidgets import QApplication
from main_dialog import MainDialog

app = QApplication(sys.argv)
window = MainDialog()
window.show()
sys.exit(app.exec_())
```

---

## 6. Como usar a ferramenta

A interface possui duas etapas principais:

1. Coleta de dados;
2. Execução do modelo.

---

## 6.1. Aba Coleta

Na aba de coleta, o usuário seleciona:

- Shapefile da área de interesse;
- Ano;
- Coleção Landsat;
- Porcentagem máxima de nuvem;
- Pasta de saída.

### Entrada esperada

O shapefile deve ser preferencialmente **poligonal**, representando a área de estudo.

Evite usar:

```text
shapefile de ruas
shapefile de linhas
shapefile de pontos
camadas de logradouros
```

Use preferencialmente:

```text
limite municipal
área de estudo poligonal
bacia hidrográfica
talhão agrícola
```

### Arquivos auxiliares do Shapefile

O `.shp` deve estar junto com os arquivos auxiliares:

```text
arquivo.shp
arquivo.shx
arquivo.dbf
arquivo.prj
```

O `.prj` é importante porque define o sistema de coordenadas.

---

## 6.2. Porcentagem de nuvem

A porcentagem de nuvem selecionada pelo usuário é um filtro de qualidade das cenas Landsat.

No código, ela é usada assim:

```python
.filter(ee.Filter.lt("CLOUD_COVER", cloud))
```

Exemplo:

```text
Nuvem máxima = 30%
```

significa:

```text
usar apenas imagens Landsat com menos de 30% de cobertura de nuvem
```

### Importante

Esse valor se refere à cena Landsat inteira, não necessariamente somente à área de estudo.

Uma cena pode ter 20% de nuvem no total, mas a nuvem estar exatamente sobre a área analisada.

Por isso, o projeto também pode usar máscara por pixel com `QA_PIXEL`, reduzindo pixels ruins, sombras e nuvens residuais.

### Valores recomendados

| Valor | Uso recomendado |
|---|---|
| 10% | Mais rigoroso, mas pode encontrar poucas imagens. |
| 20% | Bom para áreas com muitas cenas disponíveis. |
| 30% | Valor padrão recomendado. |
| 40% | Mais flexível. |
| 50% ou mais | Usar apenas se o sistema não encontrar imagens suficientes. |

---

## 6.3. Dados coletados

Após a coleta, a pasta de saída fica organizada assim:

```text
pasta_saida/
└── 2024/
    ├── AOI/
    │   ├── aoi.shp
    │   ├── aoi.shx
    │   ├── aoi.dbf
    │   └── aoi.prj
    │
    ├── Landsat/
    │   ├── landsat_2024.tif
    │   └── landsat_2024_metadata.json
    │
    └── Mapbiomas/
        └── mapbiomas_2024.tif
```

---

## 6.4. Aba Execução

Na aba de execução, o usuário seleciona a pasta raiz da coleta e o ano.

Exemplo:

```text
Pasta selecionada:
C:/.../teste/shapes/sorocaba

Ano:
2024
```

O código procura automaticamente:

```text
C:/.../teste/shapes/sorocaba/2024/Landsat/landsat_2024.tif
C:/.../teste/shapes/sorocaba/2024/Mapbiomas/mapbiomas_2024.tif
C:/.../teste/shapes/sorocaba/2024/AOI/aoi.shp
```

---

## 7. Dados usados pelo modelo

O modelo foi treinado para prever a variável:

```text
ET
```

com as seguintes variáveis de entrada:

```text
b2
b3
b4
b5
b6
b7
precip
Ano
X
Y
uso_3.0
uso_9.0
uso_11.0
uso_12.0
uso_15.0
uso_20.0
uso_21.0
uso_24.0
uso_25.0
uso_29.0
uso_33.0
uso_39.0
uso_41.0
uso_46.0
uso_48.0
```

Total:

```text
25 variáveis de entrada
```

A ordem dessas variáveis deve ser preservada em:

```text
modelo/feature_columns.json
```

---

## 8. Significado das variáveis

| Variável | Significado |
|---|---|
| `b2` | Banda espectral Landsat processada. |
| `b3` | Banda espectral Landsat processada. |
| `b4` | Banda espectral Landsat processada. |
| `b5` | Banda espectral Landsat processada. |
| `b6` | Variável térmica/temperatura usada pelo treinamento. |
| `b7` | Banda espectral Landsat processada. |
| `precip` | Precipitação anual em mm. |
| `Ano` | Ano da observação. |
| `X` | Coordenada X em sistema projetado UTM. |
| `Y` | Coordenada Y em sistema projetado UTM. |
| `uso_*` | Classes MapBiomas transformadas por one-hot encoding. |

---

## 9. Pré-processamento aplicado

### 9.1. Landsat

O raster Landsat final deve ter 6 bandas na seguinte ordem:

```text
Banda 1 → b2
Banda 2 → b3
Banda 3 → b4
Banda 4 → b5
Banda 5 → b6
Banda 6 → b7
```

As bandas `b2`, `b3`, `b4`, `b5` e `b7` devem estar em escala de reflectância compatível com o treinamento.

A variável `b6` tem comportamento diferente e representa informação térmica/temperatura, não devendo ser tratada como reflectância simples.

---

### 9.2. MapBiomas

O MapBiomas é coletado como classe única por pixel.

Depois, durante a execução do modelo, ele é convertido em one-hot encoding.

Exemplo:

```text
MapBiomas = 24
```

gera:

```text
uso_24.0 = 1
todas as outras uso_* = 0
```

Exemplo:

```text
MapBiomas = 3
```

gera:

```text
uso_3.0 = 1
todas as outras uso_* = 0
```

---

### 9.3. Coordenadas X/Y

O modelo foi treinado com coordenadas projetadas, em metros.

Por isso, o sistema não usa diretamente latitude/longitude para `X` e `Y`.

O código estima automaticamente uma zona UTM adequada a partir do centroide da área de interesse.

Exemplo para Sorocaba:

```text
Longitude centroide: -47.446765
Latitude centroide: -23.464556
Zona UTM: 23
CRS usado para X/Y: EPSG:31983
```

Para outras regiões, o CRS é estimado automaticamente.

---

### 9.4. Precipitação

O modelo usa `precip` como variável de entrada.

A versão atual usa um valor anual de referência quando o usuário ainda não fornece um valor manual ou raster de precipitação.

Exemplo:

```text
Precipitação fallback para 2024: 1373.91 mm
```

Essa solução é melhor do que usar precipitação igual a zero, mas ainda é uma aproximação.

### Melhorias futuras

O ideal é substituir o fallback por:

1. Campo manual na interface para o usuário informar precipitação anual;
2. Arquivo CSV com precipitação por ano;
3. Raster anual de precipitação;
4. Download automático de precipitação via Earth Engine, por exemplo CHIRPS ou ERA5.

---

## 10. Saída do modelo

O resultado final é salvo em:

```text
pasta_saida/
└── ano/
    └── Resultado/
        └── etp_eto_ano.tif
```

Exemplo:

```text
C:/.../sorocaba/2024/Resultado/etp_eto_2024.tif
```

Embora o nome atual seja `etp_eto`, o modelo está prevendo a variável `ET`.

Nome recomendado para versões futuras:

```text
et_2024.tif
```

ou:

```text
evapotranspiracao_anual_2024.tif
```

---

## 11. Interpretação do raster final

O raster final representa:

```text
Evapotranspiração anual estimada em mm/ano
```

Cada pixel contém uma previsão da RNA.

Exemplo de estatísticas obtidas em teste:

```text
min = 1.97
média = 850.12
max = 1170.66
desvio = 77.77
```

Interpretação:

```text
A evapotranspiração anual estimada variou aproximadamente de 2 a 1171 mm/ano dentro da área analisada, com média próxima de 850 mm/ano.
```

---

## 12. Pós-processamento físico

Como a RNA é uma regressão livre, ela pode prever valores fisicamente impossíveis, como ET negativa.

Por isso, o código aplica uma correção física:

```text
ET < 0       → outlier físico
ET > 1600    → outlier físico
```

Esses valores são corrigidos por mediana espacial dos vizinhos.

Exemplo de log real:

```text
Pixels negativos: 234 (0.0466%)
Classe MapBiomas nos pixels negativos:
  Classe 24: 234 pixels (100.00%)

Correção física da predição:
  ET mínimo permitido: 0.00
  ET máximo permitido: 1600.00
  Pixels incoerentes encontrados: 234 (0.0466%)

Preenchimento por mediana:
  Iteração 1: 206 pixels corrigidos
  Iteração 2: 24 pixels corrigidos
  Iteração 3: 4 pixels corrigidos
```

Isso indica que os valores negativos eram outliers urbanos pontuais, não erro generalizado do mapa.

---

## 13. Visualização no QGIS

Ao abrir o raster no QGIS:

1. Clique com o botão direito na camada;
2. Vá em `Propriedades`;
3. Vá em `Simbologia`;
4. Use `Banda simples falsa-cor`;
5. Clique em carregar valores mínimo/máximo;
6. Escolha uma rampa de cor.

Sugestão:

```text
tons frios   → menor ET
tons quentes → maior ET
```

---

## 14. Gerar contornos e rótulos

Para deixar o mapa mais legível:

1. Abra a Caixa de Ferramentas do QGIS;
2. Procure `Contorno`;
3. Use `GDAL > Extração raster > Contorno`;
4. Selecione o raster `etp_eto_ano.tif`;
5. Defina intervalo, por exemplo:

```text
100 mm
```

6. Crie a camada vetorial de contornos;
7. Ative rótulos usando o campo de valor da linha.

Resultado recomendado:

```text
raster colorido + linhas de contorno rotuladas
```

---

## 15. Logs importantes

Durante a execução, o sistema gera logs como:

```text
CRS UTM estimado automaticamente
Diagnóstico das principais features
Pixels válidos
Estatísticas da predição
Diagnóstico dos pixels negativos
Correção física da predição
Estatísticas do raster final recortado
```

Esses logs são úteis para validar se o resultado está coerente.

---

## 16. Exemplo de log esperado

```text
Executando modelo RNA...
Metadados Landsat encontrados.
Bandas esperadas: b2, b3, b4, b5, b6, b7

CRS UTM estimado automaticamente:
  Longitude centroide: -47.446765
  Latitude centroide: -23.464556
  Zona UTM: 23
  CRS usado para X/Y: EPSG:31983

Carregando modelo RNA...
Modelo carregado.
scaler_X carregado.
scaler_y carregado.
Features carregadas com 25 variáveis.

Reprojetando raster de EPSG:4326 para EPSG:31983...
Raster reprojetado: 897 x 928

Precipitação fallback para 2024: 1373.91 mm

Entrada preparada: (832416, 25)
Pixels válidos: 502,446 / 832,416

Executando predição...
Estatísticas da predição antes do recorte:
min=-740.43, média=849.99, max=1170.66, desvio=80.66

Correção física da predição:
Pixels incoerentes encontrados: 234 (0.0466%)

Após correção:
min=1.97, média=850.26, max=1170.66, desvio=77.83

Raster recortado salvo.
Processamento finalizado.
```

---

## 17. Limitações atuais

### 17.1. O modelo pode ser regional

Como o modelo usa `X` e `Y`, ele pode aprender padrões espaciais específicos da região de treinamento.

Portanto, mesmo que o plugin aceite qualquer área de estudo, a confiabilidade do modelo depende da similaridade entre a nova área e os dados usados no treinamento.

### 17.2. Precipitação ainda é aproximada

A precipitação fallback é útil para evitar valores absurdos, mas ainda não substitui uma fonte real de precipitação espacial.

### 17.3. Dados urbanos podem gerar outliers

Pixels urbanos muito claros, quentes ou impermeabilizados podem gerar extrapolações locais. O código trata esses valores como outliers físicos.

### 17.4. A variável `b6` exige cuidado

A variável `b6` no treinamento tem comportamento térmico e não deve ser normalizada como simples reflectância.

---

## 18. Problemas comuns e soluções

### 18.1. Erro: `No module named PyQt5`

Instale:

```bash
pip install PyQt5
```

ou use o ambiente correto:

```bash
conda activate rna_qgis
```

---

### 18.2. Erro: Earth Engine sem permissão

Verifique:

```bash
earthengine authenticate
```

E confirme se o projeto está registrado no Earth Engine.

---

### 18.3. Erro: raster Landsat não foi criado

Possíveis causas:

- área grande demais;
- pasta em sincronização com OneDrive;
- falha do geemap;
- problema de permissão;
- nuvem máxima muito baixa.

Soluções:

- usar uma área menor;
- salvar fora do OneDrive;
- aumentar limite de nuvem;
- verificar autenticação do Earth Engine.

---

### 18.4. Erro: `Coluna de uso do solo inválida: uso_3.0`

A correção é tratar a classe como `float` antes de converter:

```python
class_value = float("3.0")
```

---

### 18.5. Erro: `all input arrays must have the same shape`

Significa que alguma variável tem formato diferente das outras.

Verifique:

- X/Y;
- MapBiomas alinhado;
- raster Landsat reprojetado;
- shape das bandas.

---

### 18.6. Valores de ET muito altos

Prováveis causas:

- bandas Landsat em escala errada;
- precipitação igual a zero;
- coordenadas em latitude/longitude em vez de UTM;
- `b6` tratada incorretamente.

---

### 18.7. Valores negativos

Valores negativos de ET não fazem sentido físico.

O código atual:

1. identifica pixels negativos;
2. diagnostica classe MapBiomas e bandas;
3. corrige por mediana espacial local.

---

## 19. Recomendações de melhoria

### Curto prazo

- Renomear o raster de saída para `et_ano.tif`;
- Exibir legenda automática no QGIS;
- Adicionar campo de precipitação anual manual na interface;
- Melhorar a mensagem de ajuda da porcentagem de nuvem.

### Médio prazo

- Baixar precipitação automaticamente via Earth Engine;
- Salvar relatório de execução em `.txt` ou `.json`;
- Exportar mapa estilizado automaticamente;
- Gerar camada de contorno automaticamente.

### Longo prazo

- Treinar um modelo sem `X/Y` absolutos para maior generalização;
- Treinar com múltiplas regiões;
- Usar dados climáticos reais por pixel;
- Validar com dados independentes de ET;
- Adicionar incerteza da predição.

