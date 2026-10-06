MAX_UINT64 = (1 << 64) - 1


def encode_uvarint(value: int) -> bytes:
    """Encode an unsigned 64-bit integer using ULEB128."""
    # validaciones iniciales: que value sea entero, pero no boolean
    # exige que sea como maximo un uint de 64 bits.
    if not isinstance(value, int) or isinstance(value, bool):
      raise TypeError("ULEB128 value must be an integer.")
    if not 0 <= value <= MAX_UINT64:
      raise ValueError("ULEB128 value must fit in uint64.")

    encoded = bytearray()
    # este bucle extrae los 7 bits menos significativos (a la derecha) con 'value & 0x7F'
    # si todavía quedan bits por codificar, les activa el bit de continuación '(| 0x80)' y 
    # desplaza el valor 7 posiciones a la derecha (value >>= 7).
    # cuando queda menos de 128, lo escribe como ultimo byte, 
    # sin activar el bit de continuación.
    while value >= 0x80:
      encoded.append((value & 0x7F) | 0x80)
      value >>= 7
    encoded.append(value)
    return bytes(encoded)


def read_uvarint(file_object) -> int:
    """Read one canonical unsigned 64-bit ULEB128 integer."""
    value = 0

    # lee 1 byte por iteracion hasta 10.
    # es hasta 10 porque un uint64 tiene 64 bits
    # y ULEB128 almacena 7 bits de informacion por byte
    for index in range(10):
      encoded_byte = file_object.read(1)
      if len(encoded_byte) != 1:
        raise ValueError("Truncated ULEB128 value.")

      byte = encoded_byte[0] # extrae bit de continuacion
      payload = byte & 0x7F  # extrae los 7 bits de valor
      # aca verificamos  que el numero codificado no exceda el rango de un uint64
      if index == 9 and (payload > 1 or byte & 0x80):
        raise ValueError("ULEB128 value exceeds uint64.")

      # reconstruye el numero: 
      # cada payload contiene un bloque de 7 bits
      # se coloca ese bloque en la posicion que le corresponde dentro del numero final con ' payload << index * 7'
      # y con el or '|=' lo agrega a los bits que ya se habían reconstruido de bytes anteriores
      value |= payload << (index * 7) 
      if byte & 0x80 == 0: # si el bit continuacion está apagado ya puede devolver el entero.
        if index > 0 and payload == 0: # pero, si
          raise ValueError("Non-canonical ULEB128 value.")
        return value
    raise ValueError("ULEB128 value is too long.")