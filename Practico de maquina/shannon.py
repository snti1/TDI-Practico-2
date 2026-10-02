import math
from collections import Counter


def get_pairs_and_padding(data: bytes):
  """
  Toma una secuencia de bytes y devuelve una lista de pares de bytes (tuples de 2 bytes).
  Si la longitud es impar, añade un byte de relleno (0x00) al final.
  Devuelve: (lista_de_pares, hubo_padding)
  """
  has_padding = len(data) % 2 != 0
  if has_padding:
    data += b"\x00"

  # Agrupamos de a 2 bytes: cada par es un tuple (byte1, byte2)
  pairs = [
    (data[i], data[i + 1]) for i in range(0, len(data), 2)
  ]
  return pairs, has_padding


def generate_shannon_o2_codes(pairs: list):
  """
  Calcula las probabilidades de los pares de bytes y genera la tabla de códigos Shannon O(2).
  Devuelve un diccionario: {(b1, b2): "cadena_de_bits"}
  y el diccionario de frecuencias necesarias para guardar en la cabecera.
  """
  total_pairs = len(pairs)
  if total_pairs == 0:
    return {}, {}

  # 1. Contar frecuencias de cada par (b1, b2)
  freq_map = Counter(pairs)

  # 2. Ordenar pares por probabilidad/frecuencia descendente
  sorted_pairs = sorted(
    freq_map.keys(), key=lambda p: freq_map[p], reverse=True
  )

  # 3. Construir la tabla de códigos Shannon
  codes = {}
  cumulative_prob = 0.0

  for pair in sorted_pairs:
    count = freq_map[pair]
    p_i = count / total_pairs

    # Longitud en bits: l_i = ceil(-log2(p_i))
    # Si la probabilidad es 1 (un solo símbolo en todo el archivo), le asignamos 1 bit mínimo
    length = max(1, math.ceil(-math.log2(p_i)))

    # Convertir la parte fraccionaria de cumulative_prob a binario con 'length' bits
    code_bits = []
    fraction = cumulative_prob
    for _ in range(length):
        fraction *= 2
        bit = int(fraction)
        code_bits.append(str(bit))
        fraction -= bit

    codes[pair] = "".join(code_bits)

    # Sumamos la probabilidad para el siguiente símbolo
    cumulative_prob += p_i
  return codes, freq_map