import hashlib
import os
import struct
import sys
import time

from bit_stream import BitWriter
from shannon import generate_shannon_o2_codes, get_pairs_and_padding, ENTRY_FORMAT, HEADER_FORMAT, MAGIC
from varint import encode_uvarint


def _same_path(first_path: str, second_path: str) -> bool:
  return os.path.normcase(os.path.abspath(first_path)) == os.path.normcase(
    os.path.abspath(second_path)
  )


def compress(input_path: str, output_path: str, verbose: bool = True):
  """Comprime un archivo y guarda un contenedor TDI3 autocontenible."""
  if not os.path.isfile(input_path):
    raise FileNotFoundError(f"El archivo de entrada '{input_path}' no existe.")
  if _same_path(input_path, output_path):
    raise ValueError("La entrada y la salida deben ser archivos distintos.")

  start_time = time.perf_counter() # mover despues de la lectura del archivo?
  with open(input_path, "rb") as input_file:
    original_data = input_file.read()

  original_size = len(original_data)
  hash = hashlib.sha256(original_data).digest()
  
  # aplicamos shannon con extension de orden 2,
  # obtenemos los codigos y las frecuencias de 
  # los simbolos ...
  pairs, has_padding = get_pairs_and_padding(original_data)
  codes, freq_map = generate_shannon_o2_codes(pairs)

  #if len(freq_map) > 65536:
  #  raise ValueError("La tabla supera el alfabeto de pares de bytes.")

  # escribimos el header del archivo.
  # primero escribimos los magic bytes
  # y luego el resto de la cabecera ...
  bit_length = sum(freq_map[pair] * len(code) for pair, code in codes.items())
  with open(output_path, "wb") as output_file:
    output_file.write(MAGIC)
    output_file.write(
      struct.pack(
        HEADER_FORMAT,
        original_size,
        bit_length,
        int(has_padding),
        len(freq_map),
        hash,
      )
    )

    # aca escribimos las frecuencias de los simbolos...
    for (byte_1, byte_2), count in sorted(freq_map.items()):
      output_file.write(struct.pack(ENTRY_FORMAT, byte_1, byte_2)) # primero escribimos los dos simbolos
      output_file.write(encode_uvarint(count))                     # y despues el numero en ULEB128

    header_size = output_file.tell()

    # aca escribimos los codigos de los simbolos
    writer = BitWriter(output_file)
    for pair in pairs:
      writer.write_bits(codes[pair])
    writer.flush()

  # metricas ...
  elapsed_time_ms = (time.perf_counter() - start_time) * 1000
  compressed_size = os.path.getsize(output_path)
  ratio = original_size / compressed_size if compressed_size else 0
  saving_pct = (1 - compressed_size / original_size) * 100 if original_size else None
  overhead_pct = header_size / compressed_size * 100 if compressed_size else 0
  throughput = original_size / 1_000_000 / (elapsed_time_ms / 1000)
  ratio_display = f"{ratio:.4f}" if original_size else "N/A"
  saving_display = f"{saving_pct:.2f}%" if saving_pct is not None else "N/A"

  if verbose:
    print("=" * 60)
    print("             COMPRESIÓN COMPLETADA (Shannon O(2))           ")
    print("=" * 60)
    print(f"Archivo de entrada  : {input_path}")
    print(f"Archivo de salida   : {output_path}")
    print(f"Tamaño original     : {original_size:,} bytes")
    print(f"Tamaño cabecera     : {header_size:,} bytes")
    print(f"Tamaño comprimido   : {compressed_size:,} bytes")
    print(f"Ratio de compresión : {ratio_display}")
    print(f"Ahorro de espacio   : {saving_display}")
    print(f"Overhead cabecera   : {overhead_pct:.2f}%")
    print(f"Tiempo de ejecución : {elapsed_time_ms:.2f} ms")
    print(f"Throughput          : {throughput:.3f} MB/s")
    print("Parámetros          : Extensión Shannon de orden 2 (pares)")
    print("=" * 60)


if __name__ == "__main__":
  if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != "-q"):
    print("Uso: python compressor.py <archivo_entrada> <salida.tdi> [-q]")
    sys.exit(1)

  try:
    compress(sys.argv[1], sys.argv[2], verbose=len(sys.argv) == 3)
  except (OSError, ValueError, struct.error) as error:
    print(f"Error: {error}", file=sys.stderr)
    sys.exit(1)