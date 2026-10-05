# Practico de maquina: Shannon Ext. O(2)

## Algoritmo

La solucion propia agrupa los bytes consecutivos, desde el inicio del archivo,
en pares no solapados. Cuenta la frecuencia de cada par y asigna codigos
Shannon con longitud `ceil(-log2(p))`. Los pares se ordenan por frecuencia
decreciente y, en caso de empate, por sus dos bytes. Esto es una extension de
fuente de orden 2: no es un modelo Markov condicionado por los dos bytes
anteriores.

La compresion y descompresion se implementan en Python; no se delega el nucleo
del algoritmo propio a una libreria externa. Un byte cero se agrega como
padding solo cuando el original tiene longitud impar. El tamaño original
permite retirar ese byte al reconstruir.

## Formato TDI2

Todos los enteros se guardan en big-endian. Las versiones anteriores `TDI1`
no son compatibles con este decoder; volver a comprimir los originales para
generar `TDI2`.

| Campo | Tamano | Descripcion |
| --- | ---: | --- |
| Magic | 4 bytes | `TDI2`, identificador y version del formato |
| Tamano original | 8 bytes | Numero exacto de bytes a reconstruir |
| Longitud del payload | 8 bytes | Numero exacto de bits Shannon, sin padding fisico |
| Bandera de padding | 1 byte | Debe coincidir con la paridad del tamano original |
| Cantidad de pares | 4 bytes | Entre 0 y 65.536 entradas |
| SHA-256 original | 32 bytes | Digest del contenido original |
| Tabla | 10 bytes por entrada | Byte 1, byte 2 y frecuencia de 8 bytes |
| Payload | Variable | Codigos en orden MSB-first; bits fisicos sobrantes son cero |

La tabla permite regenerar los codigos durante la descompresion. El decoder
valida la estructura, las frecuencias, la longitud en bits, el padding y
SHA-256 antes de escribir el archivo de salida. El digest detecta corrupcion
accidental; no autentica el archivo comprimido frente a modificaciones
intencionales.

## Uso

Desde esta carpeta:

```powershell
python .\compressor.py entrada.txt salida.tdi
python .\decompressor.py salida.tdi reconstruido.txt
python -m unittest discover -s tests -v
python .\benchmark.py
```

El compresor y el descompresor aceptan rutas distintas para entrada y salida.
Una entrada vacia es valida. Si el archivo comprimido es incompatible,
truncado o corrupto, el descompresor termina con codigo distinto de cero y no
escribe una salida parcial.

## Benchmark

Se comparan Shannon propio, 7-Zip 7z/LZMA2 con `-mx=5` (Normal) y gzip nivel
6. El baseline gzip omite nombre y timestamp (`-n -6`). `gzip` y `7z` se
resuelven desde `PATH`; si `7z` no esta disponible ahi, se acepta `7z.exe`
junto al codigo.

Cada medicion se repite tres veces y se informa la mediana. La salida se
descomprime y compara byte a byte antes de registrar el resultado. El CSV
incluye ratio, ahorro, tamano relativo, cabecera y overhead cuando aplican,
tiempos y throughput de compresion/descompresion. Se usa MB decimal
(1.000.000 bytes). Los tres compresores y descompresores se ejecutan por CLI
mediante la misma funcion de medicion, por lo que el tiempo incluye el inicio
del proceso. El decoder propio acepta `-q` para evitar imprimir metricas en
cada repeticion del benchmark.

El Weissman global excluye archivos menores de 1 KiB, calcula el ratio con
las sumas del corpus de rendimiento y usa la mediana de los tiempos totales
por repeticion, siempre en milisegundos y contra gzip-6. El score no reemplaza
la lectura de ratios, tiempos y throughput. Los archivos actuales de las
pruebas 2-4 tienen 100 KiB; la guia recomienda al menos 1 MiB para esas
pruebas. Para resultados oficiales se deben usar exactamente los bytes del
corpus comun publicado por la catedra.

`benchmark.py` genera `results/benchmark_results.csv` y
`results/benchmark_summary.json`, ademas de archivos temporales en
`temp_benchmark/`. Esos resultados deben regenerarse despues de cambiar el
formato o el protocolo de medicion.