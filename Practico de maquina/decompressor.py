import hashlib
import os
import struct
import sys
import time
from bit_stream import BitReader
from shannon import generate_shannon_o2_codes


def calculate_sha256(filepath: str) -> str:
    """Calcula el hash SHA-256 de un archivo para validar su integridad byte a byte."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def decompress(input_path: str, output_path: str):
    """Lee un archivo .tdi, valida la cabecera, decodifica los datos y reconstruye el original."""
    if not os.path.exists(input_path):
        print(f"Error: El archivo de entrada '{input_path}' no existe.")
        sys.exit(1)

    start_time = time.time()
    compressed_size = os.path.getsize(input_path)

    with open(input_path, "rb") as in_file:
        # 1. Validar Magic Bytes
        magic = in_file.read(4)
        if magic != b"TDI1":
            print(
                "Error: Cabecera invalida o archivo incompatible (Magic bytes incorrecots)."
            )
            sys.exit(1)

        # 2. Leer Metadatos (Tamaño original, Padding y Cantidad de Pares)
        header_data = in_file.read(11)  # 8 bytes (Q) + 1 byte (B) + 2 bytes (H)
        if len(header_data) < 11:
            print("Error: Datos insuficientes en la cabecera.")
            sys.exit(1)

        original_size, has_padding, num_entries = struct.unpack(
            ">QBH", header_data
        )

        # 3. Leer Diccionario de Frecuencias
        freq_map = {}
        for _ in range(num_entries):
            pair_bytes = in_file.read(2)
            count_bytes = in_file.read(4)
            if len(pair_bytes) < 2 or len(count_bytes) < 4:
                print(
                    "Error: Cabecera corrupta o incompleta al leer frecuencias."
                )
                sys.exit(1)

            b1, b2 = pair_bytes[0], pair_bytes[1]
            (count,) = struct.unpack(">I", count_bytes)
            freq_map[(b1, b2)] = count

        # 4. Reconstruir la Tabla de Códigos y Crear Diccionario Invertido (codigo -> par)
        # Creamos una lista ficticia con las repeticiones para regenerar exactamente la misma tabla
        pairs_reconstructed = []
        for pair, count in freq_map.items():
            pairs_reconstructed.extend([pair] * count)

        codes, _ = generate_shannon_o2_codes(pairs_reconstructed)
        reverse_codes = {code: pair for pair, code in codes.items()}

        # 5. Decodificación Bit a Bit
        reader = BitReader(in_file)
        reconstructed_bytes = bytearray()
        current_code = ""

        # Leemos bits hasta recuperar exactamente los bytes del archivo original
        while len(reconstructed_bytes) < original_size:
            bit = reader.read_bit()
            if bit is None:
                # Llegamos al final inesperado del flujo
                break

            current_code += bit

            # Si la secuencia de bits coincide con un código de la tabla
            if current_code in reverse_codes:
                b1, b2 = reverse_codes[current_code]
                reconstructed_bytes.append(b1)

                # Si aún no llegamos al límite original, agregamos el segundo byte
                if len(reconstructed_bytes) < original_size:
                    reconstructed_bytes.append(b2)

                current_code = ""  # Reiniciar acumulador de bits

    # 6. Guardar el archivo reconstruido
    with open(output_path, "wb") as out_file:
        out_file.write(reconstructed_bytes)

    elapsed_time_ms = (time.time() - start_time) * 1000
    reconstructed_size = len(reconstructed_bytes)

    # 7. Salida en Pantalla con Métricas
    print("=" * 60)
    print("            DESCOMPRESIÓN COMPLETADA (Shannon O(2))         ")
    print("=" * 60)
    print(f"Archivo comprimido : {input_path}")
    print(f"Archivo reconstruido: {output_path}")
    print(f"Tamaño comprimido  : {compressed_size:,} bytes")
    print(f"Tamaño reconstruido: {reconstructed_size:,} bytes")
    print(f"Tiempo de ejecución: {elapsed_time_ms:.2f} ms")

    if reconstructed_size == original_size:
        print("Estado de integridad: OK (Tamaño coincide perfectamente)")
    else:
        print("Estado de integridad: ERROR (El tamaño no coincide)")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python decompressor.py <salida.tdi> <reconstruido.txt>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    decompress(input_file, output_file)