class BitWriter:
    """Acumula bits y los escribe como bytes en un archivo o buffer."""

    def __init__(self, file_object):
        self.file = file_object
        self.buffer = 0  # Entero usado como mascara para acumular bits
        self.bit_count = 0  # Cantidad de bits acumulados en el buffer

    def write_bits(self, bit_string: str):
        """Recibe una cadena de '0's y '1's y la empaqueta."""
        for bit in bit_string:
            self.buffer = (self.buffer << 1) | int(bit)
            self.bit_count += 1

            # Cuando juntamos 8 bits, escribimos un byte completo
            if self.bit_count == 8:
                self.file.write(bytes([self.buffer]))
                self.buffer = 0
                self.bit_count = 0

    def flush(self):
        """Escribe los bits sobrantes completando el ultimo byte con ceros a la derecha."""
        if self.bit_count > 0:
            self.buffer <<= 8 - self.bit_count
            self.file.write(bytes([self.buffer]))
            padding_used = 8 - self.bit_count
            self.buffer = 0
            self.bit_count = 0
            return padding_used
        return 0


class BitReader:
    """Lee un archivo byte a byte y entrega los bits de a uno por uno."""

    def __init__(self, file_object):
        self.file = file_object
        self.buffer = 0
        self.bit_count = 0

    def read_bit(self):
        """Lee y devuelve el siguiente bit ('0' o '1'). Devuelve None si llega al final del archivo."""
        if self.bit_count == 0:
            byte = self.file.read(1)
            if not byte:
                return None  # Fin del archivo (EOF)
            self.buffer = byte[0]
            self.bit_count = 8

        # Extraer el bit mas significativo
        self.bit_count -= 1
        bit = (self.buffer >> self.bit_count) & 1
        return str(bit)