# Plugin QGIS – RNA MPL para Estimativa de ETP/ETO

## Visão Geral

Este projeto consiste em um plugin para QGIS capaz de:

1. Coletar dados do Google Earth Engine (MapBiomas e Landsat);
2. Organizar automaticamente os dados em uma estrutura padronizada;
3. Executar um modelo de RNA (Rede Neural Artificial) para gerar um raster de saída;
4. Adicionar o resultado ao QGIS (na versão final do plugin).

Atualmente o projeto possui uma versão de testes onde a inferência da RNA foi substituída por uma operação simples sobre uma banda Landsat para validar todo o fluxo.

---

# Objetivo

Automatizar o processo de:

- Seleção da área de interesse (AOI) via shapefile;
- Download de dados de sensoriamento remoto;
- Preparação das entradas do modelo;
- Execução da inferência;
- Geração do raster final ETP/ETO.

---

# Fluxo Geral

## Etapa 1 – Coleta

Usuário informa:

- Shapefile (.shp)
- Ano
- Coleção Landsat
- Percentual máximo de nuvens
- Pasta de saída

O plugin:

1. Lê o shapefile;
2. Converte para geometria do Earth Engine;
3. Baixa o MapBiomas;
4. Baixa o Landsat;
5. Salva os rasters localmente.

Estrutura criada:

```text
PastaSaida/
│
├── 2024/
│   ├── Mapbiomas/
│   │   └── mapbiomas_2024.tif
│   │
│   ├── Landsat/
│   │   └── landsat_2024.tif
```

---

## Etapa 2 – Execução

Usuário informa:

- Pasta de dados
- Ano

O plugin:

1. Localiza a pasta do ano;
2. Carrega MapBiomas;
3. Carrega Landsat;
4. Executa a inferência;
5. Salva o resultado.

Estrutura final:

```text
PastaSaida/
│
├── 2024/
│   ├── Mapbiomas/
│   ├── Landsat/
│   └── Resultado/
│       └── etp_eto_2024.tif
```

---

# Estrutura dos Arquivos

## main_dialog.py

Responsável pela interface.

Funções:

- Conectar botões
- Validar entradas
- Exibir logs
- Acionar coleta
- Acionar execução

---

## coleta_gee.py

Responsável pela coleta.

Funções:

### initialize_ee()

Inicializa o Google Earth Engine.

### shapefile_to_ee_geometry()

Converte shapefile para geometria EE.

### baixar_mapbiomas()

Baixa o raster do MapBiomas.

### baixar_landsat()

Baixa imagens Landsat.

### coletar_dados()

Função principal da coleta.

---

## executar_modelo.py

Responsável pelo processamento.

Funções:

### ler_raster()

Leitura dos rasters.

### preparar_entrada()

Transforma rasters em entrada para a RNA.

### inferencia()

Executa o modelo treinado.

### salvar_raster()

Salva o resultado.

### executar_modelo()

Fluxo principal.

---

## plugin.py

Integra o plugin ao QGIS.

Responsável por:

- Criar ação no menu;
- Abrir a interface;
- Gerenciar carregamento do plugin.

---

## ui/

Contém a interface gráfica.

Arquivos:

- rna_mpl.ui
- ui_rna_mpl.py

---

# Dependências

## Interface

- PyQt5

## Geoprocessamento

- rasterio
- geopandas
- shapely

## Earth Engine

- earthengine-api
- geemap

## Machine Learning

- tensorflow
- keras

## Futuro (QGIS)

- qgis.core
- qgis.gui

---

# Ambiente Conda

Exemplo:

```bash
conda create -n rna_qgis python=3.11 -y

conda activate rna_qgis

pip install pyqt5
pip install rasterio
pip install geopandas
pip install shapely
pip install earthengine-api
pip install geemap
pip install tensorflow
```

---

# Teste sem TensorFlow

A versão atual substitui a RNA por:

```python
resultado = banda1 / 10000.0
```

Isso permite validar:

- Interface
- Download
- Leitura de raster
- Escrita de raster
- Fluxo completo

sem precisar do modelo treinado.

---

# Versão Final

Na versão final:

```python
modelo = load_model("modelo_etp.h5")

y_pred = modelo.predict(X)
```

Substituirá o raster de teste.

---

# Integração com QGIS

Na versão final:

```python
QgsRasterLayer
QgsProject.instance().addMapLayer()
```

serão utilizados para adicionar automaticamente:

```text
etp_eto_ANO
```

ao canvas do QGIS.

---

# Resultado Esperado

Entrada:

- Shapefile
- Ano
- Landsat
- MapBiomas

Saída:

```text
etp_eto_2024.tif
```

representando a estimativa espacial produzida pela RNA.

---

# Status Atual

Implementado:

- Interface
- Coleta GEE
- Download MapBiomas
- Download Landsat
- Estrutura de pastas
- Execução de teste
- Geração de raster

Pendente:

- Modelo treinado (.h5)
- Inferência real
- Integração QGIS (QgsProject)
- Empacotamento final do plugin
