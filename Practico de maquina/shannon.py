import math
from collections import Counter


def get_pairs_and_padding(data: bytes):
    """
    Toma una secuencia de bytes y devuelve una lista de pares de bytes (tuples de 2 bytes).
    Si la longitud es impar, añade un byte de relleno (0x00) al final.
    """
    has_padding = len(data) % 2 != 0
    if has_padding:
      data += b"\x00"

    # generamos la lista de pares (2 bytes) con un bucle for de paso 2
    # leyendo la posicion actual y la siguiente.
    pairs = [
      (data[i], data[i + 1]) for i in range(0, len(data), 2)
    ]
    return pairs, has_padding


def generate_shannon_o2_codes_from_freq(freq_map: dict):
    """
    NUEVO: Calcula la tabla de códigos Shannon O(2) directamente a partir del mapa de frecuencias.
    Evita tener que instanciar millones de elementos en memoria en el descompresor.
    Devuelve un diccionario: {(b1, b2): "cadena_de_bits"}
    """
    total_pairs = sum(freq_map.values())
    if total_pairs == 0:
        return {}

    # 1. Ordenar pares por frecuencia decreciente.
    # Desempate determinista con el par (b1, b2) para asegurar orden idéntico
    # ante pares con igual frecuencia.
    sorted_pairs = sorted(
      freq_map.keys(), key=lambda p: (-freq_map[p], p)
    )

    # GENERACION DE LOS CODIGOS:
    # Función Acumulativa (FA): Se calcula una probabilidad acumulada para cada símbolo,
    # sumando las probabilidades de los símbolos anteriores en la lista.
    # el primer símbolo tiene un FA de 0
    cumulative_prob = 0.0
    codes = {}

    for pair in sorted_pairs:
        count = freq_map[pair]
        p_i = count / total_pairs

        # longitud l_i = ceil(-log2(p_i))
        # Shannon propone asignar como longitud l_i el entero 
        # inmediato superior mediante la función techo (ceil)
        length = max(1, math.ceil(-math.log2(p_i))) # para que se usa el max?

        # Convertimos la FA de cada simbolo a Binario:
        # cumulative_prob lo pasamos a binario con el metodo
        # de multiplicar sucesivamente por 2.
        code_bits = []
        fraction = cumulative_prob
        for _ in range(length):
          fraction *= 2
          bit = int(fraction)
          code_bits.append(str(bit))
          fraction -= bit

        # adjuntamos al dict de codes el codigo binario obtenido:
        codes[pair] = "".join(code_bits)

        # Sumamos la probabilidad para el siguiente símbolo
        cumulative_prob += p_i

    return codes

# capaz que esta funcion no es necesaria, se podria combinar con la otra ...
def generate_shannon_o2_codes(pairs: list):
    """
    Calcula las frecuencias de los pares y delega la creación de códigos a la función optimizada.
    Devuelve: (codes, freq_map)
    """
    if not pairs:
      return {}, {}

    freq_map = Counter(pairs)
    codes = generate_shannon_o2_codes_from_freq(freq_map)
    return codes, freq_map