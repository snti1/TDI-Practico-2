# Practico de maquina: Shannon Ext. O(2)

Implementacion en Python de un compresor propio basado en una extension de
fuente de orden 2, un descompresor y un benchmark contra 7-Zip LZMA2 y gzip-6.

## Contenido

| Archivo | Funcion |
| --- | --- |
| `compressor.py` | Cuenta pares de bytes, genera codigos Shannon y escribe TDI3. |
| `decompressor.py` | Lee TDI3, regenera los codigos, reconstruye y valida el original. |
| `shannon.py` | Agrupa bytes y calcula frecuencias y codigos de Shannon. |
| `bit_stream.py` | Empaqueta y lee codigos de longitud variable bit a bit. |
| `varint.py` | Codifica y lee frecuencias como enteros ULEB128 sin signo. |
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

## Formato TDI3

Los campos de la cabecera fija usan big-endian. TDI3 es autocontenible: el
descompresor no necesita el archivo original para reconstruir el modelo de
codigos. El cambio de TDI2 a TDI3 introduce frecuencias de longitud variable;
los contenedores TDI2 anteriores no son compatibles y deben generarse de nuevo.
Formato de la cabecera: 

| Campo | Tamano | Descripcion |
| --- | ---: | --- |
| Magic/version | 4 bytes | `TDI3`. |
| Tamano original | 8 bytes | Cantidad de bytes a reconstruir. |
| Longitud del payload | 8 bytes | Bits validos del flujo codificado. |
| Padding de pares | 1 byte | Indica si se agrego el cero final para completar un par. |
| Cantidad de pares distintos | 4 bytes | Numero de entradas de la tabla. |
| SHA-256 original | 32 bytes | Digest del contenido sin padding. |
| Entrada de frecuencia | 2 bytes + 1-10 bytes | Par de bytes y frecuencia uint64 en ULEB128. |
| Payload | Variable | Codigos Shannon concatenados; padding fisico final con ceros. |

La cabecera fija ocupa 57 bytes, antes de la tabla. Cada frecuencia se escribe
como ULEB128: los 7 bits bajos de cada byte contienen parte del valor y el bit
mas alto indica si sigue otro byte. Por tanto, frecuencias menores que 128
usan un byte, mientras que uint64 puede ocupar como maximo diez. La tabla no
tiene longitud fija por entrada; el numero de pares distintos de la cabecera
indica cuantas entradas debe leer el decoder.

El decoder comprueba
magic, padding, frecuencias, longitud del payload, bits sobrantes y SHA-256
antes de escribir la salida. Un error deja codigo de salida distinto de cero
y no escribe una salida parcial. SHA-256 detecta corrupcion accidental; no
proporciona autenticacion criptografica del contenedor.

## Implementacion

### Generacion de pares y frecuencias

`get_pairs_and_padding(data)` en `shannon.py` toma los bytes leidos y los
agrupa de a dos, sin solapamiento. Si la cantidad de bytes es impar, agrega
un `0x00` para completar el ultimo par y devuelve una bandera que indica ese
padding. Por ejemplo, `ABC` se transforma en los pares `(A, B)` y `(C, 0)`.

`generate_shannon_o2_codes(pairs)` cuenta las apariciones de cada par con
`Counter` y delega la asignacion a `generate_shannon_o2_codes_from_freq`.
Esta ultima funcion recibe solo el mapa de frecuencias, por lo que tambien
puede utilizarse al descomprimir sin expandir cada frecuencia en una lista de
simbolos.

### Asignacion de codigos Shannon

La funcion suma las frecuencias para obtener la cantidad total de pares,
ordena los simbolos por frecuencia decreciente y desempata usando el par de
bytes. Para cada par calcula `p_i = frecuencia / total_pares` y la longitud
`max(1, ceil(-log2(p_i)))`. Luego convierte a binario la probabilidad
acumulada de los simbolos anteriores: multiplica repetidamente por dos y
guarda los bits obtenidos hasta completar esa longitud. El resultado es un
diccionario `par -> cadena de bits`.

El orden de desempate y la tabla de frecuencias son importantes: el decoder
debe regenerar exactamente los mismos codigos que el encoder. La funcion usa
aritmetica de punto flotante para probabilidades y acumulados.

### Uso en el compresor

`compressor.py` lee la entrada en modo binario, calcula su SHA-256, forma los
pares y obtiene `codes` y `freq_map`. Calcula la longitud valida del payload
como la suma de `frecuencia(par) * longitud(codigo(par))`. Escribe en la
cabecera TDI3 el tamano original, esa longitud en bits, la bandera de padding,
la cantidad de pares distintos y el SHA-256; a continuacion serializa cada
par con su frecuencia.

Finalmente, recorre los pares originales en orden, busca el codigo de cada
uno y se lo entrega a `BitWriter`. Este concatena los codigos en un flujo de
bits y completa con ceros el ultimo byte fisico si no quedo lleno.

### Uso en el descompresor

`decompressor.py` lee la cabecera y la tabla de frecuencias del TDI3. Llama a
`generate_shannon_o2_codes_from_freq(freq_map)` para reconstruir el mismo
diccionario y crea su inverso `codigo -> par`. No necesita la entrada original
ni una copia expandida de los simbolos.

El decoder lee exactamente la cantidad de bits declarada en la cabecera con
`BitReader`, agrega cada bit a un codigo parcial y consulta el diccionario
inverso. Cuando encuentra un codigo completo, agrega sus dos bytes a la
salida y reinicia el acumulador. Al terminar verifica que se hayan
reconstruido todos los pares esperados, que el padding fisico sea cero y que
el byte agregado para completar un par sea el esperado. Recorta el byte de
padding cuando corresponde y compara el SHA-256 reconstruido con el guardado
en la cabecera. Solo despues de estas comprobaciones escribe el archivo de
salida.


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
SHA-256 de la salida con el digest guardado en TDI3. Magic incorrecto, datos
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

Para el overhead, TDI3 cuenta magic, cabecera fija y tabla; 7-Zip informa el
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