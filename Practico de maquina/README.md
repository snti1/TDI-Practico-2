# Practico de maquina: Shannon Ext. O(2)

Implementacion en Python de un compresor propio basado en una extension de
fuente de orden 2, un descompresor y un benchmark contra 7-Zip LZMA2 y gzip-6.

## Contenido

| Archivo | Funcion |
| --- | --- |
| `compressor.py` | Cuenta pares de bytes, genera codigos Shannon y escribe TDI2. |
| `decompressor.py` | Lee el archivo .tdi, regenera los codigos, reconstruye y valida el original. |
| `shannon.py` | Agrupa bytes y calcula frecuencias y codigos de Shannon. |
| `bit_stream.py` | Empaqueta y lee codigos de longitud variable bit a bit. |
| `benchmark.py` | Ejecuta compresores/descompresores, mide y genera CSV. |
| `tests/` | Corpus de cuatro archivos y su documentacion. |
| `results/benchmark_results.csv` | Ultimo conjunto de resultados guardado. |
| `results/benchmark_report.html` | Vista interactiva que carga un CSV elegido por el usuario. |

## Algoritmo

La entrada se procesa en modo binario y se agrupa desde el primer byte en
pares consecutivos no solapados: `(byte[0], byte[1])`, `(byte[2], byte[3])`,
etc. Cada par es un simbolo de la fuente extendida. Se cuentan sus
frecuencias, se ordenan de mayor a menor y se desempata por los valores de
los dos bytes para que compresor y descompresor produzcan el mismo orden.

Para cada simbolo con probabilidad `p`, la longitud Shannon es
`ceil(-log2(p))`, con un minimo practico de un bit. El codigo se construye a
partir de la probabilidad acumulada de los simbolos anteriores.

Si el archivo tiene una longitud impar, se agrega un byte `0x00` (padding) solo para
formar el ultimo par. El tamaño original y la bandera de padding permiten
quitarlo al descomprimir.

La clase `BitWriter` recibe una cadena de bits y agrega cada uno de esos bits a un buffer. 
La cantidad de bits escritos en el buffer se almacena en un contador. Cuando este contador 
llega a 8, se escribe el byte en el archivo y se reinicia el buffer.
Se utiliza en el compresor para empaquetar los códigos.

La clase `BitReader` lee un archivo bit a bit. Se utiliza en el descompresor para reconstruirlos
los codigos.

Estas clases son necesarias, debido a que los códigos de Shannon tienen longitudes variables.

## Formato TDI2

Todos los enteros usan big-endian. TDI2 es autocontenible: el descompresor no
necesita el archivo original para reconstruir el modelo de codigos.
Formato de la cabecera: 

| Campo | Tamano | Descripcion |
| --- | ---: | --- |
| Magic/version | 4 bytes | `TDI2`. |
| Tamano original | 8 bytes | Cantidad de bytes a reconstruir. |
| Longitud del payload | 8 bytes | Bits validos del flujo codificado. |
| Padding de pares | 1 byte | Indica si se agrego el cero final para completar un par. |
| Cantidad de pares distintos | 4 bytes | Numero de entradas de la tabla. |
| SHA-256 original | 32 bytes | Digest del contenido sin padding. |
| Entrada de frecuencia | 10 bytes c/u | Primer byte, segundo byte y frecuencia de 8 bytes. |
| Payload | Variable | Codigos Shannon concatenados; padding fisico final con ceros. |

La cabecera fija ocupa 57 bytes, antes de la tabla. El decoder comprueba
magic, padding, frecuencias, longitud del payload, bits sobrantes y SHA-256
antes de escribir la salida. Un error deja codigo de salida distinto de cero
y no escribe una salida parcial. SHA-256 detecta corrupcion accidental; no
proporciona autenticacion criptografica del contenedor.

## Requisitos

- Python disponible como `python` en la terminal.
- Para el benchmark: los ejecutables `7z` y `gzip` deben estar en `PATH`.
- No se necesitan paquetes Python externos para comprimir o descomprimir.

## Uso

Ejecuta los comandos desde esta carpeta (`Practico de maquina`).

### Comprimir

```powershell
python .\compressor.py entrada.txt salida.tdi
python .\compressor.py entrada.txt salida.tdi -q
```
Por defecto, el compresor informa tamaños, cabecera, ratio, ahorro, overhead, tiempo y throughput.
`-q`, suprime ese resumen; el benchmark lo usa para que cada repeticion no
genere salida de consola. El programa acepta archivos vacios y exige que las
rutas de entrada y salida sean distintas.

### Descomprimir

```powershell
python .\decompressor.py salida.tdi reconstruido.txt
python .\decompressor.py salida.tdi reconstruido.txt -q
```

Por defecto, el descompresor informa tamanos, tiempo, throughput e integridad.
`-q` suprime ese resumen; el benchmark lo usa para que cada repeticion no
genere salida de consola. El programa acepta archivos vacios y exige que las
rutas de entrada y salida sean distintas.

La validacion comprueba que el tamano reconstruido sea el esperado y compara
SHA-256 de la salida con el digest guardado en TDI2. Magic incorrecto, datos
truncados, inconsistencias en la tabla, padding no valido o hash distinto
producen un error.

## Corpus

Los cuatro casos estan en `tests/` y se describen en
[`tests/README_pruebas.txt`](tests/README_pruebas.txt). El primer archivo tiene
64 bytes; los otros tres tienen 102.400 bytes (100 KiB): texto natural, alta
repeticion y baja repeticion. Los tamanos y SHA-256 esperados estan en ese
README.

## Benchmark

Ejecuta:

```powershell
python .\benchmark.py
```

El script requiere `7z` y `gzip` resolubles en `PATH`. Ejecuta por CLI estos
comandos/configuraciones:

| Solucion | Configuracion |
| --- | --- |
| Propia | `python compressor.py {input} {output} -q` / `python decompressor.py {input} {output} -q` |
| Externa | `7z a -t7z -m0=LZMA2 -mx=5`; nivel Normal. |
| Baseline | `gzip -n -6 -c`; sin nombre ni timestamp. |

Los comandos se describen en una lista de configuracion y se ejecutan con una
misma funcion generica. Cada compresion y descompresion se repite tres veces.
Se mide el tiempo end-to-end del comando, incluido el inicio del proceso,
la lectura/escritura de archivos y se realizan mediciones de ratio de compresion, ahorro de espacio, 
tamaño relativo, throughput de compresión, throughput de descompresión y overhead de cabecera. 
Todos estos datos se guardan en un archivo CSV.

### Metricas

| Metrica | Calculo |
| --- | --- |
| Ratio | `tamano original / tamano comprimido`; mayor que 1 indica reduccion. |
| Ahorro (%) | `(1 - comprimido / original) * 100`; puede ser negativo si se expande. |
| Tamano relativo (%) | `(comprimido / original) * 100`. |
| Throughput | Bytes originales / tiempo, en MB decimales por segundo (`1 MB = 1.000.000 bytes`). |
| Overhead (%) | Bytes de cabecera/framing / tamano comprimido * 100. |
| Weissman global | Ratio y mediana del tiempo total, normalizados contra gzip-6. |

Para el overhead, TDI2 cuenta magic, cabecera fija y tabla; 7-Zip informa el
tamano de sus headers; gzip se contabiliza como 18 bytes de framing (10 de
header y 8 de trailer). El overhead no es directamente comparable entre
formatos con estructuras distintas.

El Weissman usa `alpha = 1`, tiempos en milisegundos y gzip-6 como referencia.
Solo incorpora archivos mayores de 1 KiB; calcula el ratio global con la
suma de tamanos y el tiempo con la mediana de las sumas por repeticion. El
score global se repite en las filas del algoritmo en el CSV; no es un score
individual por archivo. gzip es la referencia y su score es 1.

El benchmark genera `results/benchmark_results.csv` y archivos de trabajo en `temp_benchmark/`.
Los resultados guardados corresponden a la ultima ejecucion y deben regenerarse si cambian el corpus, 
el codigo o la configuracion.

## Reporte HTML

[`results/benchmark_report.html`](results/benchmark_report.html) permite visualizar los resultados del benchmar. Se ingresa el archivo
`benchmark_results.csv`. La pagina construye tabla, graficos y resumen a partir del CSV seleccionado.