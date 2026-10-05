import hashlib
import os
import struct
import sys
import time

from bit_stream import BitReader
from shannon import generate_shannon_o2_codes_from_freq, ENTRY_FORMAT, HEADER_FORMAT, MAGIC

HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
ENTRY_SIZE = struct.calcsize(ENTRY_FORMAT)

def _read_exact(file_object, size: int, description: str) -> bytes:
  data = file_object.read(size)
  if len(data) != size:
    raise ValueError(f"Archivo truncado al leer {description}.")
  return data


def _same_path(first_path: str, second_path: str) -> bool:
  return os.path.normcase(os.path.abspath(first_path)) == os.path.normcase(
    os.path.abspath(second_path)
  )


def decompress(input_path: str, output_path: str, verbose: bool = True):
  """Descomprime y valida un contenedor TDI2 antes de escribir la salida."""
  if not os.path.isfile(input_path):
    raise FileNotFoundError(f"El archivo de entrada '{input_path}' no existe.")
  if _same_path(input_path, output_path):
    raise ValueError("La entrada y la salida deben ser archivos distintos.")

  start_time = time.perf_counter()
  compressed_size = os.path.getsize(input_path)

  with open(input_path, "rb") as in_file:
    magic = in_file.read(4) # nuestro magic byte son los primeros 4 bytes
    if magic != MAGIC:
      raise ValueError("Formato incompatible: se esperaba un archivo TDI2.")

    # leemos la cabecera del archivo
    header_data = in_file.read(HEADER_SIZE)
    (
      original_size,
      bit_length,
      has_padding,
      num_entries,
      expected_hash,
    ) = struct.unpack(HEADER_FORMAT, header_data)

    expected_padding = original_size % 2
    if has_padding not in (0, 1) or has_padding != expected_padding:
      raise ValueError("La bandera de padding no coincide con el tamaño original.")

    expected_pairs = (original_size + 1) // 2
    #if num_entries > 65536:
    #  raise ValueError("La tabla contiene más pares de los permitidos.")
    if (expected_pairs == 0) != (num_entries == 0):
      raise ValueError("La cantidad de entradas no coincide con el tamaño original.")

    # leemos la tabla de frecuencias de simbolos...
    freq_map = {}
    for _ in range(num_entries):
      byte_1, byte_2, count = struct.unpack(
        ENTRY_FORMAT, in_file.read(ENTRY_SIZE)
      )
      pair = (byte_1, byte_2)
      if pair in freq_map or count == 0:
        raise ValueError("La tabla contiene pares duplicados o frecuencia cero.")
      freq_map[pair] = count

    if sum(freq_map.values()) != expected_pairs:
      raise ValueError("Las frecuencias no suman la cantidad esperada de pares.")

    # a partir de la tabla de frecuencias generamos los codigos
    codes = generate_shannon_o2_codes_from_freq(freq_map)
    reverse_codes = {code: pair for pair, code in codes.items()}
    # 'codes' tiene un formato de la forma: {(byte_1, byte_2): 'code', ...} en el cual la key es la pair de bytes,
    # en 'reverse_codes' cambiamos este formato a { 'code': (byte_1, byte_2), ...}
    # esto lo hacemos para ...
    payload_offset = in_file.tell()
    payload_size = (bit_length + 7) // 8 # calculamos la cantidad de bytes. sumamos 7 para redondear hacia arriba
    if compressed_size - payload_offset != payload_size:
      raise ValueError("La longitud del payload no coincide con la cabecera.")

    # empezamos a reconstruir el archivo original: 
    reader = BitReader(in_file)
    reconstructed = bytearray()
    current_code = ""
    decoded_pairs = 0

    for _ in range(bit_length):
      # leemos el payload bit a bit y lo adjuntamos a current_code
      bit = reader.read_bit()
      if bit is None:
        raise ValueError("Payload truncado durante la decodificación.")
      current_code += bit

      # si encontramos una coincidencia, agregamos el par de bytes (letras) a 'reconstructed'
      # como los codigos generados son instantaneos, nunca se va a dar el caso 
      # de que un codigo sea prefijo de otro.
      if current_code in reverse_codes:
        if decoded_pairs >= expected_pairs:
          raise ValueError("El payload contiene símbolos adicionales.")
        reconstructed.extend(reverse_codes[current_code])
        decoded_pairs += 1
        current_code = ""

    if current_code:
      raise ValueError("El payload termina dentro de un código Shannon.")
    if decoded_pairs != expected_pairs:
      raise ValueError("El payload no reconstruye la cantidad esperada de pares.")

    # aca chequeamos que los bits de padding sean todos 0.
    unused_bits = payload_size * 8 - bit_length
    if unused_bits:
      in_file.seek(payload_offset + payload_size - 1)
      last_byte = _read_exact(in_file, 1, "padding del payload")[0]
      if last_byte & ((1 << unused_bits) - 1):
        raise ValueError("Los bits de padding del payload no son cero.")

  if has_padding and reconstructed[-1] != 0:
    raise ValueError("El byte de padding reconstruido no es cero.")

  del reconstructed[original_size:] # eliminamos el padding
  reconstructed_size = len(reconstructed)
  
  elapsed_time_ms = (time.perf_counter() - start_time) * 1000
  throughput = reconstructed_size / 1_000_000 / (elapsed_time_ms / 1000)

  # verificamos integridad con el hash SHA256
  actual_hash = hashlib.sha256(reconstructed).digest()
  if actual_hash != expected_hash:
    raise ValueError("SHA256 no coincide: el archivo comprimido está corrupto.")

  with open(output_path, "wb") as out_file:
    out_file.write(reconstructed)

  # mostramos metricas ...
  if verbose:
    print("=" * 60)
    print("             DESCOMPRESIÓN COMPLETADA (Shannon O(2))       ")
    print("=" * 60)
    print(f"Archivo comprimido : {input_path}")
    print(f"Archivo reconstruido: {output_path}")
    print(f"Tamaño comprimido  : {compressed_size:,} bytes")
    print(f"Tamaño reconstruido: {reconstructed_size:,} bytes")
    print(f"Tiempo de ejecución: {elapsed_time_ms:.2f} ms")
    print(f"Throughput         : {throughput:.3f} MB/s")
    print("Integridad         : SHA256 coincide")
    print(f"SHA256            : {actual_hash.hex()}")
    print("=" * 60)


if __name__ == "__main__":
  if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != "-q"):
    print("Uso: python decompressor.py <salida.tdi> <reconstruido.txt> [-q]")
    sys.exit(1)

  try:
    decompress(sys.argv[1], sys.argv[2], verbose=len(sys.argv) == 3)
  except (OSError, ValueError, struct.error) as error:
    print(f"Error: {error}", file=sys.stderr)
    sys.exit(1)