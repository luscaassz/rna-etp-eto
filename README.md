# RNA ETP ETO - Plugin QGIS

Plugin PyQGIS para coletar dados Landsat e MapBiomas via Google Earth Engine e gerar um raster anual de evapotranspiracao estimada com uma Rede Neural Artificial.

O resultado principal é um GeoTIFF como:

```text
2024/Resultado/etp_eto_2024.tif
```

Cada pixel do raster representa uma estimativa anual de ET/ETP/ETo em `mm/ano`, conforme o dominio do modelo treinado.

> [!NOTE]
> Este plugin exige conta Google Earth Engine, um Project ID valido do Google Cloud/Earth Engine e dependencias Python externas instaladas no ambiente Python usado pelo QGIS.


---

## Funcionalidades

O plugin possui duas etapas principais:

1. **Coleta**: baixa dados Landsat e MapBiomas para uma area de interesse definida por shapefile.
2. **Execucao**: aplica o modelo RNA e gera um raster GeoTIFF com a estimativa anual de evapotranspiracao.

Ao final da execucao, o raster gerado e adicionado automaticamente ao canvas do QGIS.

---

## Estrutura do Plugin

Estrutura esperada para a versao limpa do plugin:

```text
rna_etp_eto/
├── metadata.txt
├── __init__.py
├── plugin.py
├── main_dialog.py
├── coleta_gee.py
├── executar_modelo.py
├── requirements.txt
├── README.md
├── LICENSE
├── modelo/
│   ├── modelo_etp.h5
│   ├── scaler_X.pkl
│   ├── scaler_y.pkl
│   └── feature_columns.json
└── ui/
    ├── __init__.py
    ├── ui_rna_mpl.py
    └── rna_mpl.ui
```

---

## Requisitos

- QGIS 3.28 ou superior.
- Python do QGIS com as dependencias externas instaladas.
- Conta Google Earth Engine ativa.
- Project ID valido do Google Cloud/Earth Engine.

Dependencias Python usadas pelo plugin:

```text
earthengine-api
geemap
tensorflow
scikit-learn
joblib
numpy
pandas
geopandas
rasterio
shapely
pyproj
fiona
```

> [!IMPORTANT]
> Instale as dependencias no Python do QGIS.

---

## Instalacao das Dependencias no QGIS

No Windows, abra o **OSGeo4W Shell** instalado junto com o QGIS.

Instale as dependencias principais:

```bat
python -m pip install earthengine-api geemap tensorflow scikit-learn joblib
```

Instale as dependencias geoespaciais, se ainda nao estiverem disponiveis no Python do QGIS:

```bat
python -m pip install rasterio geopandas fiona shapely pyproj
```

Evite instalar `gdal` via `pip` dentro do QGIS. O QGIS ja vem com uma instalacao propria do GDAL.

Teste os imports no Terminal Python do QGIS:

```python
import ee
import geemap
import tensorflow
import sklearn
import joblib
import rasterio
import geopandas
```

### Plugin Google Earth Engine do QGIS

Opcionalmente, instale tambem o plugin **Google Earth Engine** pelo proprio Gerenciador de Complementos do QGIS.

Ele nao substitui todas as dependencias deste plugin, mas ajuda o usuario a entender e configurar a autenticacao do Earth Engine, inclusive o uso do Project ID.

O pacote `geemap` continua sendo uma dependencia Python deste plugin e deve ser instalado via `pip` no ambiente Python do QGIS:

```bat
python -m pip install geemap
```

Depois de instalar as dependencias, confirme no Terminal Python do QGIS:

```python
import ee
import geemap
```

Se `import geemap` falhar, a coleta deste plugin tambem falhara.

---

## Instalacao do Plugin

### Opcao 1 - Copiar para a pasta de plugins

Copie a pasta do plugin para:

```text
C:\Users\SEU_USUARIO\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\rna_etp_eto
```

Se a pasta `python/plugins` nao existir dentro do perfil, crie manualmente.

No QGIS:

```text
Complementos > Gerenciar e Instalar Complementos
```

Ative o plugin **RNA ETP ETO**.

Apos ativar, abra o plugin pelo menu **Complementos** ou pelo botao criado na barra de ferramentas.

![Placeholder - plugin aberto no QGIS](docs/images/placeholder-tela-principal.png)

### Opcao 2 - Instalar por ZIP

Crie um arquivo `.zip` contendo uma pasta raiz chamada `rna_etp_eto`:

```text
rna_etp_eto.zip
└── rna_etp_eto/
    ├── metadata.txt
    ├── __init__.py
    ├── plugin.py
    └── ...
```

No QGIS:

```text
Complementos > Gerenciar e Instalar Complementos > Instalar a partir do ZIP
```

Selecione o arquivo `rna_etp_eto.zip`.

---

## Autenticacao do Google Earth Engine

O plugin nao usa um projeto fixo do Earth Engine. Cada usuario deve autenticar com a propria conta e informar o proprio Project ID.

Na aba **Coleta**:

1. Informe o **Projeto Earth Engine** no campo correspondente.
2. Clique em **Autenticar Earth Engine**.
3. Faca login no navegador quando solicitado.
4. Volte ao QGIS.
5. Execute a coleta.

O Project ID fica salvo nas configuracoes do QGIS para os proximos usos.

Exemplo de Project ID:

```text
abcd-123456
```

Se preferir configurar por variavel de ambiente, use uma das opcoes abaixo antes de abrir o QGIS:

```bat
setx EARTHENGINE_PROJECT seu-project-id
```

Tambem sao aceitas:

```text
EARTHENGINE_PROJECT
GOOGLE_CLOUD_PROJECT
EE_PROJECT
```

---

## Como Usar

### 1. Aba Coleta

Na aba **Coleta**, informe:

- shapefile da area de interesse;
- ano;
- colecao Landsat;
- porcentagem maxima de nuvem;
- pasta de saida;
- Project ID do Earth Engine.

![aba Coleta](docs/images/01-aba-coleta.png)

O shapefile deve representar uma area/poligono. Evite usar shapefiles de linhas ou pontos.

Arquivos auxiliares esperados:

```text
area.shp
area.shx
area.dbf
area.prj
```

Depois da coleta, a pasta de saida ficara assim:

```text
pasta_saida/
└── 2024/
    ├── AOI/
    │   └── aoi.shp
    ├── Landsat/
    │   ├── landsat_2024.tif
    │   └── landsat_2024_metadata.json
    └── Mapbiomas/
        └── mapbiomas_2024.tif
```

### 2. Aba Execucao

Na aba **Execucao**, selecione a pasta raiz onde os dados foram salvos.

Exemplo:

```text
C:\dados\projeto_et
```

Não selecione diretamente a pasta `2024`. Selecione a pasta que contem a pasta do ano.

Depois clique em **RODAR MODELO**.

![aba Execucao preenchida](docs/images/02-aba-execucao.png)

O resultado sera salvo em:

```text
2024/Resultado/etp_eto_2024.tif
```

O raster tambem sera adicionado automaticamente ao canvas do QGIS.

![raster carregado no canvas do QGIS](docs/images/03-resultado-qgis.jpeg)

---

## O Que Significa Nuvem Maxima?

A porcentagem de nuvem e um filtro aplicado nas imagens Landsat.

Exemplo:

```text
Nuvem maxima = 30%
```

significa que o plugin usara apenas cenas Landsat com menos de 30% de cobertura de nuvem.

Valores recomendados:

| Valor | Indicacao |
|---|---|
| 10% | Mais rigoroso; pode encontrar poucas imagens. |
| 20% | Boa qualidade, mas ainda restritivo. |
| 30% | Valor padrao recomendado. |
| 40% | Mais flexivel. |
| 50% ou mais | Usar se nao encontrar imagens suficientes. |

---

## Entradas do Modelo

O modelo usa 25 variaveis por pixel:

```text
b2, b3, b4, b5, b6, b7,
precip, Ano, X, Y,
uso_3.0, uso_9.0, uso_11.0, uso_12.0, uso_15.0,
uso_20.0, uso_21.0, uso_24.0, uso_25.0, uso_29.0,
uso_33.0, uso_39.0, uso_41.0, uso_46.0, uso_48.0
```

A ordem das variaveis esta em:

```text
modelo/feature_columns.json
```

Nao altere esse arquivo sem retreinar ou validar o modelo.

---

## Saida Gerada

Cada pixel do raster final representa uma estimativa anual de evapotranspiracao em `mm/ano`.

Exemplo:

```text
Valor do pixel = 850
```

significa:

```text
ET anual estimada naquele local = 850 mm/ano
```

---

## Visualizacao no QGIS

Para visualizar melhor o raster final:

1. Clique com o botao direito na camada.
2. Abra **Propriedades**.
3. Va em **Simbologia**.
4. Escolha **Banda simples falsa-cor**.
5. Carregue os valores minimo/maximo.
6. Escolha uma rampa de cor.

Interpretacao visual:

```text
valores menores -> menor ET
valores maiores -> maior ET
```

---

## Problemas Comuns

### O plugin nao aparece no QGIS

Verifique se a pasta foi copiada para o perfil correto:

```text
profiles/default/python/plugins/rna_etp_eto
```

Tambem confira se existem `metadata.txt`, `__init__.py` e `plugin.py` dentro da pasta do plugin.

### Erro: `No module named joblib`, `rasterio`, `tensorflow` ou `ee`

A dependencia nao esta instalada no Python do QGIS.

Instale pelo OSGeo4W Shell:

```bat
python -m pip install earthengine-api geemap tensorflow scikit-learn joblib rasterio geopandas fiona shapely pyproj
```

### Erro no Earth Engine: `no project found`

Informe o Project ID na aba **Coleta** e clique em **Autenticar Earth Engine**.

### Erro: `Project not found or deleted`

O Project ID informado nao existe ou sua conta nao tem permissao para usa-lo.

Use o ID real do projeto Google Cloud/Earth Engine, nao apenas o nome visual do projeto.

### Erro: nenhuma imagem Landsat encontrada

Aumente o limite de nuvem, por exemplo de `20%` para `40%`.

### Raster com valores muito estranhos

Possiveis causas:

- raster Landsat antigo, gerado antes da correcao de escala;
- precipitacao fallback pouco representativa;
- area muito diferente da regiao usada no treinamento;
- shapefile invalido ou com CRS incorreto.

Refaca a coleta com a versao atual do plugin.

---

## Observacoes Importantes

- O modelo atual usa coordenadas `X` e `Y`; por isso, pode funcionar melhor em regioes parecidas com a regiao usada no treinamento.
- A precipitacao ainda e usada como valor anual de referencia quando nao e informada manualmente.
- O pos-processamento remove valores fisicamente impossiveis, como ET negativa.
- Para resultados cientificos mais robustos, recomenda-se usar precipitacao real e validar a saida com dados independentes.



