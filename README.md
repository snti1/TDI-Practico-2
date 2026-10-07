# Teoría de la Información - Trabajos Prácticos y Proyecto de Compresión
**Grupo 3**
**Carrera:** Licenciatura en Ciencias de la Computación  
**Materia:** Teoría de la Información
**Proyecto:** Implementación de Algoritmos de Codificación, Análisis de Fuentes con Memoria (Markov) y Práctico de Máquina 2 (Compresor de Autoría Propia).

---
# Introduccion 
Este proyecto esta compuesto por 2 trabajos:
el primero  tiene como objetivo comparar un compresor propio con dos herramientas de compresión ampliamente utilizadas: gzip y 7-Zip.
Las pruebas se realizan utilizando los mismos archivos de texto para los tres compresores, con el objetivo de obtener una comparación reproducible.


## Contenido del Repositorio

Este repositorio reúne las resoluciones teóricas, desarrollos prácticos y la implementación del software de compresión desarrollado para la materia. El contenido está estructurado en 2 bloques principales:  
    
```
    TDI-Practico-2/ 
    ├── Practico de maquina/ 
    │   │ 
    │   ├── results/ # Salidas del benchmark (html, csv, json) 
    │   │   ├── benchmark_report.html # Reporte visual/interactivo de resultados en HTML 
    │   │   └── benchmark_results.csv # Tabla completa de mediciones (tiempos en ms, ratios y Weissman) 
    │   │ 
    │   ├── tests/ # Corpus de prueba (archivos .txt y documentación) 
    │   │   ├── prueba_1_pequena.txt # Corpus 1: Archivo reducido para control de bordes 
    │   │   ├── prueba_2_texto_natural.txt # Corpus 2: Texto plano con distribución natural 
    │   │   ├── prueba_3_alta_repeticion.txt # Corpus 3: Secuencia redundante (baja entropía) 
    │   │   ├── prueba_4_baja_repeticion.txt # Corpus 4: Secuencia compleja (alta entropía) 
    │   │   └── README_pruebas.txt # Descripción del origen y propósito de los datasets
    │   │ 
    │   ├── benchmark.py # Automatización de pruebas y métricas 
    │   │
    │   ├── bit_stream.py # Manipulación de flujos de bits (BitWriter / BitReader) 
    │   │ 
    │   ├── compressor.py # Compresor de Shannon + Markov de orden 2 (.tdi) 
    │   │ 
    │   ├── decompressor.py # Descompresor y reconstrucción de contexto 
    │   │ 
    │   ├── README.md # Guía específica de ejecución y comandos 
    │   │ 
    │   ├── shannon.py # Algoritmo de Shannon y cálculo de frecuencias
    │   │ 
    │   └── varint.py # Codificacion de enteros variables 
    │   
    ├── Practicos_Teoricos/ 
    │   │ 
    │   ├── practico_3_Markov # Resoluciones teóricas del Práctico 3 (Fuentes de Markov) 
    │   │ 
    │   └── practico_4 # Resoluciones teóricas del Práctico 4 (Extensión de fuentes) 
    │
    ├── .gitignore # Exclusiones de Git (temporales, binarios, .tdi) 
    └── README.md # Documentación general y principal del repositorio
```


# Informacion sobre los compresores 7zip(default) y gzip(nivel 6)

## 1. 7-Zip

### 1.1 Algoritmo

7-Zip es una herramienta de compresión que permite utilizar diferentes algoritmos. Para este proyecto se utiliza el formato `.7z` con la configuración predeterminada de 7-Zip.

En las configuraciones actuales, el método utilizado por defecto para el formato `.7z` es **LZMA2**. LZMA2 es un algoritmo de compresión basado en diccionario que aprovecha secuencias repetidas de datos para reducir el tamaño del archivo.

La herramienta 7-Zip construye un archivo comprimido que contiene los datos procesados y la información necesaria para poder reconstruir los archivos originales durante la descompresión.

### 1.2 Instalación

7-Zip se instala en Ubuntu mediante:

```bash
sudo apt update
sudo apt install 7zip
```

Para verificar la instalación:

```bash
7z
```

También puede utilizarse la versión de 7-Zip instalada directamente en Windows.

### 1.3 Uso

Para comprimir un archivo utilizando la configuración predeterminada:

```bash
7z a archivo.7z archivo.txt
```

La opción `a` indica que se desea agregar archivos a un archivo comprimido.

Para extraer un archivo:

```bash
7z x archivo.7z
```

### 1.3.1 Configuración utilizada

Para la comparación se utiliza la configuración predeterminada de 7-Zip, sin modificar manualmente los parámetros de compresión.

El formato `.7z` utiliza por defecto LZMA2 en las configuraciones actuales de 7-Zip. Esto permite comparar el comportamiento del compresor propio contra una configuración estándar de 7-Zip.

### 1.4 Dependencias

7-Zip se instala mediante los repositorios de Ubuntu y no requiere instalar dependencias adicionales manualmente.

Dependencias principales:

* Ubuntu/WSL
* 7-Zip
* Herramientas básicas de línea de comandos

### 1.5 Formato

7-Zip utiliza el formato:

```text
.7z
```

El formato 7z es un formato de archivo comprimido que permite utilizar diferentes métodos de compresión.

En esta prueba se utiliza la configuración predeterminada de 7-Zip, basada en LZMA2.

El formato también permite almacenar información adicional como:

* Archivos contenidos.
* Métodos de compresión.
* Metadatos.
* Información necesaria para la descompresión.
* Datos de comprobación de integridad.

### 1.6 Cabecera

Un archivo `.7z` comienza con una cabecera que identifica el formato y contiene información necesaria para interpretar el archivo.

La **cabecera inicial tiene un tamaño fijo de 32 bytes, es decir, 256 bits**.

Está formada por los siguientes campos:

| Campo              |                  Tamaño |
| ------------------ | ----------------------: |
| Signature          |       6 bytes = 48 bits |
| Major Version      |         1 byte = 8 bits |
| Minor Version      |         1 byte = 8 bits |
| Start Header CRC   |       4 bytes = 32 bits |
| Next Header Offset |       8 bytes = 64 bits |
| Next Header Size   |       8 bytes = 64 bits |
| Next Header CRC    |       4 bytes = 32 bits |
| **Total**          | **32 bytes = 256 bits** |

**Signature:** identifica que el archivo corresponde al formato 7z. Sus 6 bytes son:

```text
37 7A BC AF 27 1C
```

**Major Version:** indica la versión principal del formato. Actualmente su valor es `0`.

**Minor Version:** indica la versión secundaria del formato. La especificación actual utiliza `4`.

**Start Header CRC:** valor CRC utilizado para comprobar la integridad de la información correspondiente a la cabecera inicial.

**Next Header Offset:** indica la posición relativa donde comienza la siguiente cabecera.

**Next Header Size:** indica el tamaño de la siguiente cabecera.

**Next Header CRC:** permite comprobar la integridad de la siguiente cabecera.

La estructura de la cabecera inicial está definida por la especificación del formato 7z. Después de esta cabecera se encuentran los datos comprimidos y la información estructural del archivo. La segunda parte de la cabecera tiene tamaño variable y contiene información como los métodos utilizados, tamaños, archivos almacenados y otros datos necesarios para la descompresión.

### 1.7 Ejemplo

Ejemplo utilizado en el proyecto:

```bash
7z a benchmark/7zip/prueba_1_pequena.7z test/prueba_1_pequena.txt
```

Este comando selecciona el archivo de texto `prueba_1_pequena.txt`, ubicado en la carpeta `test` del repositorio, y el archivo comprimido generado se guarda en la carpeta `benchmark/7zip` del repositorio.

---

## 2. Baseline

### 2.1 Algoritmo

El baseline utilizado en este proyecto es **gzip con nivel de compresión 6**.

gzip utiliza el algoritmo **DEFLATE**, que combina dos técnicas principales: LZ77 para detectar secuencias repetidas y codificación Huffman para representar los datos de manera más eficiente.

El nivel `-6` determina el nivel de compresión utilizado por gzip. En este proyecto se mantiene fijo en 6 para que todas las pruebas del baseline utilicen exactamente la misma configuración.

### 2.2 Instalación

Se instala mediante el gestor de paquetes de Ubuntu:

```bash
sudo apt update
sudo apt install gzip
```

Para verificar la instalación:

```bash
gzip --version
```

### 2.3 Uso

Para realizar las pruebas se utiliza gzip con nivel de compresión 6.

El nivel se especifica mediante la opción `-6`:

```bash
gzip -6 archivo.txt
```

Para conservar el archivo original y generar el archivo comprimido en una ubicación determinada se utiliza `-c`:

```bash
gzip -6 -c archivo.txt > archivo.txt.gz
```

Ejemplo utilizado en el proyecto:

```bash
gzip -6 -c test/prueba_1_pequena.txt > benchmark/gzip/prueba_1_pequena.txt.gz
```

### 2.4 Dependencias

gzip no requiere dependencias adicionales para realizar las pruebas. Se instala directamente mediante los repositorios de Ubuntu.

Dependencias principales:

* Ubuntu/WSL
* GNU gzip
* Herramientas básicas de línea de comandos

### 2.5 Formato

gzip genera archivos con extensión:

```text
.gz
```

El formato gzip está diseñado para comprimir un flujo de datos utilizando **DEFLATE**.

El archivo `.gz` contiene los datos comprimidos junto con información necesaria para su descompresión y comprobación de integridad.

### 2.6 Cabecera

Un archivo gzip comienza con una cabecera que permite identificar el formato y contiene información sobre cómo fue generado el archivo.

La **cabecera fija de gzip tiene 10 bytes = 80 bits**.

Entre los campos principales se encuentran:

| Campo     |                 Tamaño |
| --------- | ---------------------: |
| ID1       |        1 byte = 8 bits |
| ID2       |        1 byte = 8 bits |
| CM        |        1 byte = 8 bits |
| FLG       |        1 byte = 8 bits |
| MTIME     |      4 bytes = 32 bits |
| XFL       |        1 byte = 8 bits |
| OS        |        1 byte = 8 bits |
| **Total** | **10 bytes = 80 bits** |

**ID1:** primer identificador del formato gzip. Su valor es `0x1F`.

**ID2:** segundo identificador del formato gzip. Su valor es `0x8B`.

**CM:** indica el método de compresión utilizado. Para DEFLATE su valor es `8`.

**FLG:** contiene diferentes indicadores que determinan si existen campos opcionales en la cabecera. Sus 8 bits se dividen de la siguiente manera:

| Bit | Campo     | Tamaño |
| --: | --------- | -----: |
|   0 | FTEXT     |  1 bit |
|   1 | FHCRC     |  1 bit |
|   2 | FEXTRA    |  1 bit |
|   3 | FNAME     |  1 bit |
|   4 | FCOMMENT  |  1 bit |
|   5 | Reservado |  1 bit |
|   6 | Reservado |  1 bit |
|   7 | Reservado |  1 bit |

**FTEXT:** indica que el contenido probablemente corresponde a texto.

**FHCRC:** indica la presencia de una comprobación CRC de la cabecera.

**FEXTRA:** indica que existen campos adicionales en la cabecera.

**FNAME:** indica que se almacena el nombre original del archivo.

**FCOMMENT:** indica que se almacena un comentario asociado al archivo.

Los bits reservados deben permanecer en cero.

**MTIME:** almacena la fecha y hora asociada al archivo utilizando 4 bytes = 32 bits.

**XFL:** contiene información adicional relacionada con el nivel de compresión. Para DEFLATE puede utilizarse para indicar determinadas características de compresión.

**OS:** identifica el sistema operativo utilizado para generar el archivo y ocupa 1 byte = 8 bits.

Además de la cabecera fija, gzip puede contener campos opcionales dependiendo de los bits establecidos en `FLG`:

| Campo opcional |            Tamaño |
| -------------- | ----------------: |
| XLEN           | 2 bytes = 16 bits |
| Extra Field    |          Variable |
| FNAME          |          Variable |
| FCOMMENT       |          Variable |
| FHCRC          | 2 bytes = 16 bits |

El campo `FNAME`, cuando está presente, contiene el nombre original terminado en un byte cero. `FCOMMENT` funciona de forma similar para los comentarios.

Después de los datos comprimidos, el archivo gzip contiene un **trailer**:

| Campo     |                Tamaño |
| --------- | --------------------: |
| CRC32     |     4 bytes = 32 bits |
| ISIZE     |     4 bytes = 32 bits |
| **Total** | **8 bytes = 64 bits** |

**CRC32:** permite comprobar la integridad de los datos originales después de la descompresión.

**ISIZE:** contiene el tamaño de los datos originales sin comprimir, módulo 2³².

Por lo tanto, la estructura general de un archivo gzip puede representarse como:

```text
Cabecera fija
    ↓
Campos opcionales
    ↓
Datos comprimidos mediante DEFLATE
    ↓
Trailer
    ├── CRC32
    └── ISIZE
```

### 2.7 Ejemplos

Ejemplo utilizado en el proyecto:

```bash
gzip -6 -c test/prueba_1_pequena.txt > benchmark/gzip/prueba_1_pequena.txt.gz
```

Este comando comprime `prueba_1_pequena.txt` utilizando **nivel 6**, conserva el archivo original gracias a la opción `-c` y redirige el resultado hacia `benchmark/gzip/prueba_1_pequena.txt.gz`.

El mismo procedimiento se utiliza para los demás archivos del corpus de prueba, manteniendo constante el nivel de compresión para todas las mediciones.
